---
name: iasset-api
description: Facts, safety rules and a token-cheap lookup tool for the Visma iAsset V1 and V2 APIs (apiv2.iasset.nl, api.iasset.nl). USE FOR - designing, coding, testing or reviewing anything that calls iAsset or builds iAsset payloads (objects, filters, passport-tabs, diverse-fields, oauth/token, V1 getobjectslist), checking parameters, bodies, Api-Version, paging, errors or recent API changes. Used in iAsset Syncer and iAsset Passport Designer. DO NOT USE FOR - generic HTTP questions unrelated to iAsset.
---

# iAsset API

iAsset (Visma) is a Dutch asset-management SaaS used by municipalities and contractors. **Every iAsset domain is
production data of a customer.** The specifications describe the API; the server can behave differently.

## Safety rules (non-negotiable)

- NEVER call the live APIs from an agent, a test or a script. Code against the specification, test with debug mode
  or fixtures, and leave live checks to the user on a **non-production** domain.
- Only `GET` is read-only. Treat every other method as changing data, even POSTs documented as reads
  (e.g. `/filters/results-count`). A write path needs a preview/confirmation that names the domain and shows live vs
  debug, with Cancel as the default.
- Never log, show or store `password`, `client_secret`, `access_token`, `refresh_token`, `authorization` (iAsset
  Syncer: `SENSITIVE_FIELDS` + `redact`).
- Never guess undocumented behaviour (response formats, enum meanings). Mark it **Unverified** and add an open
  question with a suggested default.

## Look things up cheaply

Do not open the 742 KB V2 spec or the 556 KB V1 file. Use the lookup script in this skill's `scripts/` folder
(`.github/skills/iasset-api/scripts/iasset_spec.py` in the repo, or `~/.copilot/skills/iasset-api/scripts/`):

```text
python <skill>/scripts/iasset_spec.py find passport          # list matching operations, writes flagged
python <skill>/scripts/iasset_spec.py op POST /passport-tabs  # params, body schema (* = required), notes
python <skill>/scripts/iasset_spec.py v1 getobjectslist       # one V1 endpoint (needs local docs/api)
python <skill>/scripts/iasset_spec.py changelog 2             # newest V2 changelog sections
python <skill>/scripts/iasset_spec.py info                    # versions, release, peculiarities
```

It finds the docs in `--docs`, `$IASSET_API_DOCS`, `./docs/api`, `../iAsset_Syncer/docs/api`, else downloads the
public V2 spec to `~/.cache/iasset-api/` (V2 only, without the project notes below). A **Scout** subagent can run
it for you. The source of truth is iAsset Syncer's `docs/api/` (regenerated with `tools/update_api_specs.py`; never
edit those files by hand).

## V1 vs V2 at a glance

| | V1 `https://api.iasset.nl/` | V2 `https://apiv2.iasset.nl/` |
|---|---|---|
| Docs | HTML page converted to `docs/api/v1/iasset-api-v1.json` (142 endpoints) | OpenAPI 3.0 `docs/api/v2/iasset-api-v2.openapi.json` (151 operations) + `v2/CHANGELOG.md` |
| Login | `POST login/` with MD5 of the password, domain, device_id | `POST /oauth/token`, password grant, multipart: grant_type, client_id, client_secret, domain_name, username, password |
| Calls | always `POST` form data with `access_token` and `version=9.8` (without `version`: HTTP 500 or empty body) | REST, `Authorization: Bearer <token>`, `Api-Version` header (send `1` unless a feature needs `2`) |
| Errors | `error`/`error_msg` in the body, often with HTTP 200 | HTTP status + Laravel `{"message", "errors"}` |
| Data | `returndata`, sometimes keyed `I0`, `I1`, ... | `data` |
| Paging | `page` param, page count in `paged` | Laravel `last_page` at top level |
| Arrays | indexed form fields `filter[0]`, `filter[1]` | `[]` suffix in names (`object_id[]`); nested Laravel brackets `sort[0][field]` |

Both: on HTTP 401 log in once more; on HTTP 429 retry with `Retry-After` (bounded). Large domains have 40,000+
objects: always page and allow cancelling.

## V2 peculiarities that bite

- No reusable schemas and almost no documented response bodies (7 of 976): check formats in debug mode.
- Request bodies are mostly `multipart/form-data`. Laravel parses multipart only on POST, so send
  PUT/PATCH/DELETE-with-multipart as **POST with `_method=PUT|PATCH|DELETE`** (method spoofing).
- Some behaviour only applies with `Api-Version: 2` (e.g. `POST /objects` with `match_by`); read the operation's
  `x-iasset-syncer-notes`.
- The top-level `security` block is invalid OpenAPI; strict validators reject the file. Ignore it.
- A required `filter_id` error comes from server validation, not from the spec.

## Passport tabs and diverse fields

- `POST /passport-tabs` (multipart, changes data): required `name` (max 50), `theme` (-1 = all themes), `fields`.
  Fields use bracket notation `fields[0][label]`, `fields[0][field_type]`, `fields[0][field_id]`, `fields[0][order]`,
  children `fields[0][children][1][label]`. `PUT /passport-tabs/{id}` = POST with `_method=PUT`. The spec declares
  no `Api-Version` here; send `1`.
- `field_type ∈ {0, 1, 2}` is **undocumented**. Working assumption (Passport Designer defaults, unverified): row
  (top level) = `1`, field (child) = `0`, a row's `field_id` = `0`, `order` starts at `1`, untitled rows get the
  invisible label U+FE0F as iAsset itself does. Keep these configurable.
- Field IDs come from `GET /fields` (all fields) or `GET /diverse-fields` (`ids[]` filter); Passport Designer
  loads an export of either. `POST /diverse-fields` is JSON (not multipart):
  required `label`, `name`, `field_type`; optional `id` must be unused.
- Hand-off between the tools: Passport Designer generates the JSON; the user sends it with iAsset Syncer
  → API Explorer → V2 → `POST /passport-tabs`, which converts it to multipart and asks for confirmation.

## Where it lives in the code

- **iAsset Syncer:** `iasset/client.py` (`IAssetClient.request_v2`, `get_v2_all_pages`, `_authenticate_v2`,
  `_process_response`, `_debug_payload`), `iasset/catalog.py` (`V1_TARGETS`, `may_change_data`), `iasset/forms.py`
  (`strip_array_suffix`), `iasset/config.py` (`V1_VERSION`, `SENSITIVE_FIELDS`), `docs/ARCHITECTURE.md` ("Writing to
  iAsset and confirmations", "iAsset API facts"). New calls need a matching `_debug_payload` response.
- **iAsset Passport Designer:** builds payloads only and never calls the API (`passport_designer/payload.py`,
  `field_map.py` for the `GET /fields` / `GET /diverse-fields` export). Keep it that way unless the user decides otherwise.

## When the spec changes

Run `changelog 2` before designing a feature on a recently changed area. If the spec and the code disagree, report
both with sources; do not "fix" either silently.
