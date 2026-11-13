"""Generate descriptive CORDEX-CMIP6 project collection metadata.

The CORDEX-CMIP6 project collections reference terms from WCRP-universe, but
the project CV additionally needs the exact strings used by selected NetCDF
global attributes. These values are copied from the CORDEX-CMIP6 CMOR-table
CV, while unrelated project metadata is preserved.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UNIVERSE_BASE = "https://esgvoc.ipsl.fr/resource/universe"
PROPERTY_BASE = "https://esgvoc.ipsl.fr/property"


@dataclass(frozen=True)
class FieldSpec:
    """Describe one field copied into an ESGVoc project term."""

    output_field: str
    property_iri: str
    source_field: str | None = None
    required: bool = True
    raw_entry_is_value: bool = False
    json_literal: bool = False
    previous_context_definitions: tuple[Any, ...] = ()


@dataclass(frozen=True)
class CollectionSpec:
    """Describe one CMOR CV collection and its generated project fields."""

    collection_id: str
    term_type: str
    fields: tuple[FieldSpec, ...]

    @property
    def owned_fields(self) -> tuple[str, ...]:
        """Fields that are authoritatively maintained by this generator."""
        return tuple(field.output_field for field in self.fields)


COLLECTION_SPECS = (
    # ``source`` is both the descriptor name and the custom property name.
    # Mapping both uses of that compact term to the Source descriptor IRI is
    # consistent with the legacy CMIP project contexts.
    CollectionSpec(
        "source_id",
        "source",
        (
            FieldSpec("source", f"{UNIVERSE_BASE}/source"),
            FieldSpec(
                "source_type",
                f"{PROPERTY_BASE}/source_type",
                previous_context_definitions=("http://schema.org/source_type",),
            ),
            FieldSpec(
                "activity_participation",
                f"{PROPERTY_BASE}/activity_participation",
                previous_context_definitions=(
                    "http://schema.org/activity_participation",
                ),
            ),
            FieldSpec(
                "license",
                "http://schema.org/license",
                json_literal=True,
                previous_context_definitions=("http://schema.org/license",),
            ),
        ),
    ),
    CollectionSpec(
        "driving_source_id",
        "source",
        (
            FieldSpec("driving_source", f"{PROPERTY_BASE}/driving_source"),
            FieldSpec(
                "driving_experiment_id",
                f"{PROPERTY_BASE}/driving_experiment_id",
                required=False,
            ),
        ),
    ),
    CollectionSpec(
        "institution_id",
        "organisation",
        (
            FieldSpec(
                "institution",
                f"{PROPERTY_BASE}/institution",
                raw_entry_is_value=True,
            ),
        ),
    ),
    CollectionSpec(
        "domain_id",
        "region",
        (
            FieldSpec(
                "description",
                "https://schema.org/description",
                source_field="domain",
            ),
        ),
    ),
    CollectionSpec(
        "driving_experiment_id",
        "experiment",
        (
            FieldSpec(
                "experiment",
                f"{UNIVERSE_BASE}/experiment",
                source_field="driving_experiment",
            ),
        ),
    ),
)

CORDEX_CMIP6_LICENSE = (
    "https://cordex.org/data-access/cordex-cmip6-data/"
    "cordex-cmip6-terms-of-use"
)
CORDEX_CMIP6_LICENSE_ID = "cordex-cmip6-terms-of-use"


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos-base-dir",
        type=Path,
        default=script_dir.parents[1],
        help="Directory containing the CMOR-table and project-CV repositories.",
    )
    parser.add_argument(
        "--cordex-cmip6-cmor-tables-dir",
        type=Path,
        help="CORDEX-CMIP6 CMOR-table repository (defaults below repos-base-dir).",
    )
    parser.add_argument(
        "--cordex-cmip6-cv-dir",
        type=Path,
        help="CORDEX-CMIP6 ESGVoc project repository (defaults below repos-base-dir).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files that differ without writing them.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object in {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)
        handle.write("\n")


def require_non_empty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected a non-empty string at {location}, got {value!r}")
    return value


def desired_context_terms(spec: CollectionSpec) -> dict[str, Any]:
    """Return the JSON-LD terms required by one generated collection."""
    terms: dict[str, Any] = {
        "@base": f"{UNIVERSE_BASE}/{spec.term_type}/",
        "id": "@id",
        "type": "@type",
        spec.term_type: f"{UNIVERSE_BASE}/{spec.term_type}",
    }
    for field in spec.fields:
        terms[field.output_field] = (
            {"@id": field.property_iri, "@type": "@json"}
            if field.json_literal
            else field.property_iri
        )
    return terms


def augment_context(
    output_dir: Path,
    spec: CollectionSpec,
    *,
    dry_run: bool,
) -> str:
    """Add missing context terms without replacing existing definitions."""
    context_path = output_dir / "000_context.jsonld"
    existing = read_json(context_path) if context_path.is_file() else None
    payload = dict(existing) if existing is not None else {}
    raw_context = payload.get("@context", {})
    if not isinstance(raw_context, dict):
        raise TypeError(
            f"Expected a JSON object at {context_path}['@context'], "
            f"got {raw_context!r}"
        )

    context = dict(raw_context)
    fields_by_name = {field.output_field: field for field in spec.fields}
    for term, definition in desired_context_terms(spec).items():
        current = context.get(term)
        if term in context and current != definition:
            field = fields_by_name.get(term)
            if field is None or current not in field.previous_context_definitions:
                raise ValueError(
                    f"Refusing to overwrite context term {term!r} in "
                    f"{context_path}: existing value {current!r} differs from "
                    f"required value {definition!r}"
                )
        context[term] = definition
    payload["@context"] = context

    if payload == existing:
        return "unchanged"
    action = "created" if existing is None else "updated"
    print(f"{action.upper()}: {context_path}")
    if not dry_run:
        write_json(context_path, payload)
    return action


def validate_metadata_value(value: Any, location: str) -> str | list[str]:
    """Validate a scalar or nonempty list of metadata strings."""
    if isinstance(value, list):
        if not value:
            raise ValueError(f"Expected a non-empty list at {location}")
        return [
            require_non_empty_string(item, f"{location}[{index}]")
            for index, item in enumerate(value)
        ]
    return require_non_empty_string(value, location)


def normalize_license(value: Any, location: str) -> dict[str, Any]:
    """Convert the CMOR license value to the legacy Source license shape."""
    license_value = require_non_empty_string(value, location).rstrip("/")
    if license_value != CORDEX_CMIP6_LICENSE:
        raise ValueError(
            f"Unsupported CORDEX-CMIP6 source license at {location}: {value!r}. "
            "Add a project license term before mapping this value."
        )
    return {
        "id": CORDEX_CMIP6_LICENSE_ID,
        "exceptions-contact": None,
        "source-specific-info": "",
    }


def extract_field_value(
    identifier: str,
    raw_entry: Any,
    spec: CollectionSpec,
    field: FieldSpec,
) -> str | list[str] | dict[str, Any] | None:
    """Extract and validate one generated field from a CMOR CV entry."""
    location = f"CV.{spec.collection_id}.{identifier}"
    if field.raw_entry_is_value:
        return validate_metadata_value(raw_entry, location)

    if not isinstance(raw_entry, dict):
        raise TypeError(f"Expected an object at {location}, got {raw_entry!r}")
    source_field = field.source_field or field.output_field
    if source_field not in raw_entry:
        if field.required:
            raise ValueError(f"Missing {source_field!r} at {location}")
        return None

    value = raw_entry[source_field]
    field_location = f"{location}.{source_field}"
    if field.output_field == "license":
        return normalize_license(value, field_location)
    return validate_metadata_value(value, field_location)


def build_payload(
    identifier: str,
    raw_entry: Any,
    spec: CollectionSpec,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": spec.term_type,
    }
    for field in spec.fields:
        value = extract_field_value(identifier, raw_entry, spec, field)
        if value is not None:
            payload[field.output_field] = value
    return payload


def merge_payload(
    existing: dict[str, Any] | None,
    generated: dict[str, Any],
    spec: CollectionSpec,
    output_path: Path,
) -> dict[str, Any]:
    """Update generator-owned fields while retaining unrelated metadata."""
    if existing is None:
        return generated

    merged = dict(existing)
    for field in ("@context", "id", "type"):
        expected = generated[field]
        current = merged.get(field)
        if field in merged and current != expected:
            raise ValueError(
                f"Refusing to overwrite identity field {field!r} in {output_path}: "
                f"existing value {current!r} differs from required value {expected!r}"
            )
        merged[field] = expected
    for field in spec.owned_fields:
        if field in generated:
            merged[field] = generated[field]
        else:
            # An absent optional upstream field means that no restriction is
            # defined. Remove stale generator-owned metadata accordingly.
            merged.pop(field, None)
    return merged


def generate_collection(
    cv: dict[str, Any],
    project_root: Path,
    spec: CollectionSpec,
    *,
    dry_run: bool,
) -> dict[str, int]:
    raw_collection = cv.get(spec.collection_id)
    if raw_collection is None or raw_collection == {}:
        raise ValueError(f"CV collection {spec.collection_id!r} is missing or empty")
    if not isinstance(raw_collection, dict):
        raise TypeError(
            f"Expected CV collection {spec.collection_id!r} to be a JSON object"
        )

    normalized_ids: dict[str, str] = {}
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    expected_files: set[str] = set()
    output_dir = project_root / spec.collection_id
    augment_context(output_dir, spec, dry_run=dry_run)

    for identifier, raw_entry in sorted(raw_collection.items()):
        normalized_id = str(identifier).lower()
        previous = normalized_ids.get(normalized_id)
        if previous is not None:
            raise ValueError(
                f"Case-insensitive identifier collision in {spec.collection_id}: "
                f"{previous!r} and {identifier!r}"
            )
        normalized_ids[normalized_id] = str(identifier)

        output_path = output_dir / f"{normalized_id}.json"
        expected_files.add(output_path.name)
        existing = read_json(output_path) if output_path.is_file() else None
        generated = build_payload(str(identifier), raw_entry, spec)
        payload = merge_payload(existing, generated, spec, output_path)
        if existing == payload:
            counts["unchanged"] += 1
            continue

        action = "created" if existing is None else "updated"
        counts[action] += 1
        print(f"{action.upper()}: {output_path}")
        if not dry_run:
            write_json(output_path, payload)

    if output_dir.is_dir():
        stale = sorted(
            path.name
            for path in output_dir.glob("*.json")
            if path.name != "000_context.jsonld" and path.name not in expected_files
        )
        if stale:
            print(
                f"WARNING: {spec.collection_id} contains {len(stale)} JSON file(s) "
                "not represented in the CMOR CV; they were left unchanged: "
                + ", ".join(stale)
            )

    return counts


def main() -> None:
    args = parse_args()
    base = args.repos_base_dir.resolve()
    cmor_repo = (
        args.cordex_cmip6_cmor_tables_dir or base / "cordex-cmip6-cmor-tables"
    ).resolve()
    project_root = (args.cordex_cmip6_cv_dir or base / "cordex-cmip6-cv").resolve()
    cv_path = cmor_repo / "Tables" / "CORDEX-CMIP6_CV.json"

    content = read_json(cv_path)
    cv = content.get("CV")
    if cv is None:
        raise ValueError(f"Missing JSON object 'CV' in {cv_path}")
    if not isinstance(cv, dict):
        raise TypeError(f"Expected 'CV' in {cv_path} to be a JSON object")

    totals = {"created": 0, "updated": 0, "unchanged": 0}
    for spec in COLLECTION_SPECS:
        counts = generate_collection(
            cv,
            project_root,
            spec,
            dry_run=args.dry_run,
        )
        for action, count in counts.items():
            totals[action] += count
        print(
            f"{spec.collection_id}: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['unchanged']} unchanged"
        )

    print(
        f"Total: {totals['created']} created, {totals['updated']} updated, "
        f"{totals['unchanged']} unchanged "
        f"({'dry-run' if args.dry_run else 'written'})"
    )


if __name__ == "__main__":
    main()
