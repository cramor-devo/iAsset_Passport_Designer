"""Look up iAsset API operations without loading the full specification into the conversation.

Zoek iAsset API-operaties op zonder de volledige specificatie in het gesprek te laden.

Usage / Gebruik:
    python iasset_spec.py info                      # versions, source, release, peculiarities
    python iasset_spec.py find passport             # operations whose path/summary/tag matches
    python iasset_spec.py op POST /passport-tabs     # one V2 operation: params, body, notes
    python iasset_spec.py v1 getobjectslist          # one V1 endpoint
    python iasset_spec.py changelog [N]             # newest N V2 changelog sections (default 3)

Spec location, first match wins / Locatie van de spec, eerste treffer telt:
    --docs <dir>, env IASSET_API_DOCS, ./docs/api, ../iAsset_Syncer/docs/api,
    then a cached download of the public V2 OpenAPI file (V2 only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

V2_FILE = Path("v2/iasset-api-v2.openapi.json")
V1_FILE = Path("v1/iasset-api-v1.json")
CHANGELOG_FILE = Path("v2/CHANGELOG.md")
V2_PUBLIC_URL = "https://apiv2.iasset.nl/docs/v2?api-docs-v2.json"
CACHE_DIR = Path.home() / ".cache" / "iasset-api"
METHODS = ("get", "post", "put", "patch", "delete")


def find_docs(explicit: str | None) -> Path | None:
    """Return the first docs/api folder with the V2 spec. / Eerste docs/api-map met de V2-spec."""
    candidates = [explicit, os.environ.get("IASSET_API_DOCS"), "docs/api", "../iAsset_Syncer/docs/api"]
    for candidate in candidates:
        if candidate and (Path(candidate) / V2_FILE).is_file():
            return Path(candidate)
    return None


def load_v2(docs: Path | None) -> dict[str, Any]:
    """Load the V2 spec; download the public copy if there is no local one.

    Laad de V2-spec; download de publieke versie als er geen lokale kopie is.
    """
    if docs:
        return json.loads((docs / V2_FILE).read_text("utf-8"))
    cached = CACHE_DIR / V2_FILE.name
    if not cached.is_file():
        print(f"# No local docs/api found; downloading {V2_PUBLIC_URL}", file=sys.stderr)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(V2_PUBLIC_URL, timeout=30) as response:
            cached.write_bytes(response.read())
    return json.loads(cached.read_text("utf-8"))


def compact_schema(schema: dict[str, Any], depth: int = 0) -> list[str]:
    """Flatten a body schema to one line per property. / Body-schema plat naar één regel per eigenschap."""
    lines: list[str] = []
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        bits = [str(prop.get("type", "?"))]
        for key in ("enum", "maxLength", "minimum", "nullable", "example"):
            if key in prop:
                bits.append(f"{key}={prop[key]!r}")
        mark = "*" if name in required else " "
        desc = prop.get("description", "")
        lines.append(f"{'  ' * depth}{mark} {name}: {', '.join(bits)}{' - ' + desc if desc else ''}")
        items = prop.get("items")
        if isinstance(items, dict) and items.get("properties"):
            lines.extend(compact_schema(items, depth + 1))
        elif prop.get("properties"):
            lines.extend(compact_schema(prop, depth + 1))
    return lines


def cmd_info(spec: dict[str, Any], docs: Path | None) -> None:
    meta = spec.get("info", {}).get("x-iasset-syncer", {})
    print(f"source: {docs or CACHE_DIR}")
    if not meta:
        print("public copy without iAsset Syncer notes/peculiarities: see the iasset-api skill for those")
    print(f"V2 spec_version: {spec.get('info', {}).get('version')}  api_release: {meta.get('api_release', '?')}")
    print(f"retrieved: {meta.get('retrieved', '?')}  operations: {meta.get('operations', '?')}")
    for note in meta.get("peculiarities", []):
        print(f"- {note}")


def cmd_find(spec: dict[str, Any], term: str) -> None:
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    for path, item in spec.get("paths", {}).items():
        for method in METHODS:
            op = item.get(method)
            if not op:
                continue
            haystack = " ".join([path, op.get("summary", ""), " ".join(op.get("tags", []))])
            if pattern.search(haystack):
                flag = "" if method == "get" else "  [MAY CHANGE DATA]"
                print(f"{method.upper():6} {path}  - {op.get('summary', '')}{flag}")


def cmd_op(spec: dict[str, Any], method: str, path: str) -> int:
    op = spec.get("paths", {}).get(path, {}).get(method.lower())
    if not op:
        print(f"NOT FOUND: {method.upper()} {path}. Try: find {path.strip('/').split('/')[0]}")
        return 1
    print(f"{method.upper()} {path}  - {op.get('summary', '')}  tags={op.get('tags', [])}")
    if method.lower() != "get":
        print("!! May change live data: needs a preview/confirmation naming the domain before sending.")
    if op.get("description"):
        print(f"description: {op['description']}")
    for param in op.get("parameters", []):
        schema = param.get("schema", {})
        req = "*" if param.get("required") else " "
        example = param.get("example", schema.get("example"))
        extra = f" example={example!r}" if example is not None else ""
        desc = f" - {param['description']}" if param.get("description") else ""
        print(f"{req} {param.get('in')}:{param['name']} {schema.get('type', '')}{extra}{desc}")
    for content_type, content in op.get("requestBody", {}).get("content", {}).items():
        print(f"body ({content_type}), * = required:")
        print("\n".join(compact_schema(content.get("schema", {}), 1)))
    codes = ", ".join(op.get("responses", {}).keys())
    print(f"responses: {codes} (response bodies are rarely documented: verify in debug mode)")
    for note in op.get("x-iasset-syncer-notes", []):
        print(f"note: {note}")
    return 0


def cmd_v1(docs: Path | None, name: str) -> int:
    if not docs or not (docs / V1_FILE).is_file():
        print("NOT AVAILABLE: V1 docs need a local docs/api (iAsset_Syncer) or IASSET_API_DOCS.")
        return 1
    v1 = json.loads((docs / V1_FILE).read_text("utf-8"))
    endpoints = v1.get("endpoints", [])
    hits = [e for e in endpoints if name.lower() in f"{e.get('name', '')} {e.get('path', '')}".lower()]
    if not hits:
        print(f"NOT FOUND: {name}")
        return 1
    for endpoint in hits[:3]:
        print(json.dumps(endpoint, ensure_ascii=False, indent=1)[:2500])
    if len(hits) > 3:
        print(f"... {len(hits) - 3} more; use a more specific name.")
    return 0


def cmd_changelog(docs: Path | None, count: int) -> int:
    if not docs or not (docs / CHANGELOG_FILE).is_file():
        print("NOT AVAILABLE locally: see https://apiv2.iasset.nl/changelog")
        return 1
    text = (docs / CHANGELOG_FILE).read_text("utf-8")
    sections = [s for s in re.split(r"(?m)^(?=## )", text) if s.startswith("## ")]
    print("".join(sections[:count]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="iAsset API spec lookup")
    parser.add_argument("--docs", help="folder that contains v2/ and v1/ (default: auto-detect)")
    parser.add_argument("command", choices=["info", "find", "op", "v1", "changelog"])
    parser.add_argument("args", nargs="*")
    ns = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    docs = find_docs(ns.docs)
    if ns.command == "v1":
        return cmd_v1(docs, " ".join(ns.args))
    if ns.command == "changelog":
        return cmd_changelog(docs, int(ns.args[0]) if ns.args else 3)
    spec = load_v2(docs)
    if ns.command == "info":
        cmd_info(spec, docs)
        return 0
    if ns.command == "find":
        cmd_find(spec, " ".join(ns.args))
        return 0
    if len(ns.args) != 2:
        parser.error("op needs METHOD PATH, e.g. op POST /passport-tabs")
    return cmd_op(spec, ns.args[0], ns.args[1])


if __name__ == "__main__":
    sys.exit(main())
