"""Adviseert welke paspoorten (filters) samengevoegd kunnen worden, op basis van groep en overeenkomstige attributen.
Advises which passports (filters) can be merged, based on management group and similar attributes.

NL: Een samengevoegd paspoort bevat alle attributen van de objecttypen van de samengevoegde filters. Attributen die
niet voor alle objecttypen gelden krijgen een voetnoot: dat zijn de velden die je in iAsset per subthema aan/uit zet.
EN: A merged passport contains all attributes of the object types of the merged filters. Attributes that do not apply
to all object types get a footnote: those are the fields you enable/disable per sub-theme in iAsset.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from .design_rules import SECTION_OBJECT
from .layout_engine import LayoutEngine
from .models import ObjectType, PassportTab, SpecModel

DEFAULT_THRESHOLD = 0.6
LOW_FIT = 0.5
MAX_NAME = 50


@dataclass(frozen=True)
class MemberFit:
    """Hoeveel van het samengevoegde paspoort is relevant voor één oorspronkelijk filter.
    How much of the merged passport is relevant to one original filter."""

    filter: str
    object_types: int
    fields: int
    fit: float


@dataclass
class MergeSuggestion:
    members: list[str]
    name: str
    group: str
    similarity: float
    object_type_count: int
    total_fields: int
    partial_fields: int
    fits: list[MemberFit] = field(default_factory=list)
    tab: PassportTab | None = None  # het samengevoegde paspoort / the merged passport

    @property
    def common_fields(self) -> int:
        return self.total_fields - self.partial_fields

    @property
    def passports_saved(self) -> int:
        return len(self.members) - 1

    @property
    def lowest_fit(self) -> float:
        return min((f.fit for f in self.fits), default=1.0)

    @property
    def low_fit(self) -> bool:
        return self.lowest_fit < LOW_FIT


@dataclass(frozen=True)
class FilterProfile:
    name: str
    group: str
    object_types: list[ObjectType]
    attributes: frozenset[str]


def jaccard(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def profiles(spec: SpecModel, engine: LayoutEngine) -> list[FilterProfile]:
    result = []
    for name, types in spec.filters().items():
        per_type, _ = engine.attribute_sets(types)
        attributes = frozenset(key for keys in per_type.values() for key in keys)
        groups = Counter(o.group for o in types if o.group)
        result.append(FilterProfile(name, groups.most_common(1)[0][0] if groups else "", types, attributes))
    return result


def _average_similarity(left: list[FilterProfile], right: list[FilterProfile]) -> float:
    pairs = [jaccard(a.attributes, b.attributes) for a in left for b in right]
    return sum(pairs) / len(pairs)


def _cluster(items: list[FilterProfile], threshold: float, same_group: bool) -> list[list[FilterProfile]]:
    """Gemiddelde-koppeling clustering: voeg steeds de meest gelijkende twee clusters samen (>= drempel).
    Average-linkage clustering: repeatedly merge the two most similar clusters (>= threshold)."""
    clusters = [[p] for p in items]
    while True:
        best: tuple[float, int, int] | None = None
        for i, j in combinations(range(len(clusters)), 2):
            if same_group and {p.group for p in clusters[i] + clusters[j]} != {clusters[i][0].group}:
                continue
            score = _average_similarity(clusters[i], clusters[j])
            if score >= threshold and (best is None or score > best[0]):
                best = (score, i, j)
        if best is None:
            return clusters
        _, i, j = best
        clusters[i] = clusters[i] + clusters[j]
        del clusters[j]


def _cluster_similarity(cluster: list[FilterProfile]) -> float:
    pairs = [jaccard(a.attributes, b.attributes) for a, b in combinations(cluster, 2)]
    return sum(pairs) / len(pairs) if pairs else 1.0


def _unique_types(cluster: list[FilterProfile]) -> list[ObjectType]:
    seen: set[str] = set()
    result: list[ObjectType] = []
    for profile in cluster:
        for object_type in profile.object_types:
            if object_type.name not in seen:
                seen.add(object_type.name)
                result.append(object_type)
    return result


def suggest_name(cluster: list[FilterProfile], taken: set[str]) -> str:
    """Naam van het samengevoegde paspoort: de gedeelde groep, anders het grootste filter; altijd uniek.
    Name of the merged passport: the shared group, else the largest filter; always unique."""
    largest = max(cluster, key=lambda p: (len(p.object_types), p.name)).name
    groups = {p.group for p in cluster if p.group}
    base = next(iter(groups)) if len(groups) == 1 else largest
    for candidate in (base, f"{base} ({largest})", f"{base} (samengevoegd)"):
        name = candidate[:MAX_NAME]
        if name.casefold() not in taken:
            return name
    return f"{base} ({len(taken)})"[:MAX_NAME]


def merged_tab(spec: SpecModel, engine: LayoutEngine, members: list[str], name: str) -> PassportTab:
    """Bouw het samengevoegde paspoort; voetnoten tonen per veld voor welke objecttypen (subthema's) het geldt.
    Build the merged passport; footnotes show per field which object types (sub-themes) it applies to."""
    filters = spec.filters()
    cluster = [FilterProfile(m, "", filters[m], frozenset()) for m in members if m in filters]
    tab = engine.build(name, _unique_types(cluster), source_filters=[p.name for p in cluster])
    tab.merged_from = [p.name for p in cluster]
    return tab


@dataclass
class ManualMergeInfo:
    """Gegevens voor het handmatig samenvoegen van gekozen filters (los van drempel en groep).
    Data for manually merging chosen filters (independent of threshold and group)."""

    members: list[str]
    name: str
    groups: dict[str, str]  # filter -> beheergroep / management group
    similarity: float
    total_fields: int
    partial_fields: int
    fits: list[MemberFit] = field(default_factory=list)

    @property
    def groups_differ(self) -> bool:
        return len({g for g in self.groups.values() if g}) > 1

    @property
    def filters_differ(self) -> bool:
        return len(self.members) > 1  # elk paspoort is een eigen filter / each passport is its own filter

    @property
    def needs_confirmation(self) -> bool:
        return self.groups_differ or self.filters_differ


def manual_merge_info(spec: SpecModel, engine: LayoutEngine, members: list[str], taken: set[str]) -> ManualMergeInfo:
    """Beschrijf een handmatige samenvoeging; ``taken`` bevat bestaande namen (casefold) die niet gebruikt mogen worden.
    Describe a manual merge; ``taken`` holds existing (casefolded) names that must not be reused."""
    known = {p.name: p for p in profiles(spec, engine)}
    cluster = [known[m] for m in members if m in known]
    total = len(union_keys(cluster))
    names = [p.name for p in cluster]
    fits = [
        MemberFit(p.name, len(p.object_types), len(p.attributes), len(p.attributes) / total if total else 1.0)
        for p in cluster
    ]
    name = suggest_name(cluster, {t.casefold() for t in taken}) if cluster else ""
    partial = len(merged_tab(spec, engine, names, name or "-").footnotes) if cluster else 0
    return ManualMergeInfo(
        names, name, {p.name: p.group for p in cluster},
        _cluster_similarity(cluster), total, partial, fits,
    )


def validate_merge_name(name: str, existing: set[str]) -> str | None:
    """Geef een i18n-sleutel met de fout, of None als de naam geldig is (bestaande namen: hoofdletterongevoelig).
    Return an i18n key describing the error, or None if the name is valid (existing names: case-insensitive)."""
    stripped = name.strip()
    if not stripped:
        return "merge.name_empty"
    if len(stripped) > MAX_NAME:
        return "merge.name_too_long"
    if stripped.casefold() in {e.casefold() for e in existing}:
        return "merge.name_duplicate"
    return None


def apply_merges(
    spec: SpecModel, engine: LayoutEngine, tabs: list[PassportTab], merges: list[tuple[str, list[str]]],
) -> list[PassportTab]:
    """Vervang de samengevoegde filters in ``tabs`` door één paspoort (op de plek van het eerste filter).
    Replace the merged filters in ``tabs`` with one passport (at the position of the first filter)."""
    result = list(tabs)
    for name, members in merges:
        names = [t.name for t in result]
        if not all(m in names for m in members):
            continue
        position = min(names.index(m) for m in members)
        merged = merged_tab(spec, engine, members, name)
        result = [t for t in result if t.name not in members]
        result.insert(min(position, len(result)), merged)
    return result


def suggest_merges(
    spec: SpecModel,
    engine: LayoutEngine,
    threshold: float = DEFAULT_THRESHOLD,
    same_group: bool = True,
) -> list[MergeSuggestion]:
    """Geef samenvoegsuggesties (clusters van minstens twee filters), beste eerst.
    Return merge suggestions (clusters of at least two filters), best first."""
    all_profiles = profiles(spec, engine)
    clusters = [c for c in _cluster(all_profiles, threshold, same_group) if len(c) > 1]
    taken = {p.name.casefold() for p in all_profiles if not any(p in c for c in clusters)}
    suggestions: list[MergeSuggestion] = []
    for cluster in sorted(clusters, key=lambda c: (-len(c), -_cluster_similarity(c))):
        name = suggest_name(cluster, taken)
        taken.add(name.casefold())
        members = [p.name for p in cluster]
        tab = merged_tab(spec, engine, members, name)
        total = len(union_keys(cluster))
        fits = [
            MemberFit(p.name, len(p.object_types), len(p.attributes), len(p.attributes) / total if total else 1.0)
            for p in cluster
        ]
        groups = {p.group for p in cluster if p.group}
        suggestions.append(
            MergeSuggestion(
                members, tab.name, groups.pop() if len(groups) == 1 else "", _cluster_similarity(cluster),
                len(_unique_types(cluster)), total, len(tab.footnotes), fits, tab,
            ),
        )
    return suggestions


def union_keys(cluster: list[FilterProfile]) -> frozenset[str]:
    return frozenset().union(*(p.attributes for p in cluster))


def field_matrix(tab: PassportTab) -> list[tuple[str, list[str], bool]]:
    """(veld, objecttypen waarvoor het geldt, geldt voor alle?) voor 'Object informatie'.
    (field, object types it applies to, applies to all?) for 'Object informatie'."""
    all_types = [o.name for o in tab.object_types]
    rows: list[tuple[str, list[str], bool]] = []
    for section in (s for s in tab.sections if s.title == SECTION_OBJECT):
        for row in section.rows:
            for cell in row:
                types = tab.footnotes.get(cell.footnote, all_types) if cell.footnote else all_types
                rows.append((cell.label, types, cell.footnote is None))
    return rows
