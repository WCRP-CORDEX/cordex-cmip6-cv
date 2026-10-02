"""Generate CORDEX-CMIP6 and related WCRP-universe JSON-LD entries."""

from __future__ import annotations

import argparse
import csv
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmip_branded_variable_mapper import map_to_cmip_branded_variable

UNIVERSE_BASE = "https://esgvoc.ipsl.fr/resource/universe"
KNOWN_BRANDED_VARIABLE_HISTORY = "registered"
PROJECT_ONLY_FIELDS = {
    "flag_meanings",
    "flag_values",
    "cell_measures",
    "comment",
    "valid_min",
    "valid_max",
    "tolerance",
    "long_name",
    "realm",
    "table_id",
    "compound_name",
}
KNOWN_BRANDED_VARIABLE_PROJECT_ONLY_FIELDS = {"description", "frequency"}
CANONICAL_TIME_COORDINATE_BY_TEMPORAL_LABEL = {
    "tminavg": "time4",
    "tmaxavg": "time4",
    "tavgmax": "time5",
    "tsumavg": "time6",
}
UNIVERSE_TIME_COORDINATES = {
    "time5": "Time coordinate for data reported as the daily maximum hourly mean.",
    "time6": "Time coordinate for data reported as the mean of daily sums.",
}
OPTIONAL_NON_EMPTY_TEXT_FIELDS = {
    "data_coordinate": {
        "long_name",
        "cf_standard_name",
        "units",
        "positive",
        "stored_direction",
        "coordinate_values",
    },
    "formula_term": {"long_name", "cf_standard_name", "units"},
    "grid_axis": {
        "axis",
        "data_type",
        "long_name",
        "cf_standard_name",
        "out_name",
        "units",
    },
    "grid_variable": {"long_name", "cf_standard_name"},
    "model_level_coordinate": {
        "long_name",
        "cf_standard_name",
        "computed_standard_name",
        "units",
        "formula",
    },
    "known_branded_variable": {
        "long_name",
        "units",
        "realm",
        "cell_methods",
        "cell_measures",
        "var_def_qualifier",
        "bn_status",
        "cf_sn_status",
        "history",
    },
}
COORDINATE_TYPES = {
    "standard_1d": (
        "1-D coordinate variable whose name matches its dimension. The most common type. "
        "Examples include plev19, time, and spectral-band coordinates. Parametric vertical "
        "coordinates with formulas also use this type. QA/QC verifies the coordinate variable, "
        "matching dimension, units, requested values, bounds, and formula terms when specified."
    ),
    "scalar": (
        "Single-valued coordinate listed in the coordinates attribute rather than used as a "
        "dimension. Its value may be numeric or character. QA/QC verifies the requested value, "
        "the coordinates attribute, and requested bounds when specified."
    ),
    "auxiliary": (
        "Auxiliary 1-D coordinate with a simple index dimension. Values are character labels "
        "identifying categories. QA/QC verifies that the character coordinate variable exists "
        "and is associated with the expected index dimension."
    ),
    "generic_vertical": (
        "Abstract model-level vertical coordinate whose values are model-dependent. QA/QC "
        "verifies a dimension with output name 'lev' without requiring specific level values. "
        "Concrete model-level coordinates reference it through generic_level_name."
    ),
    "generic_horizontal": (
        "Longitude or latitude used as a generic horizontal coordinate. It may be a regular "
        "1-D coordinate or be represented by grid indices and auxiliary geographic variables. "
        "The axis field distinguishes X from Y."
    ),
    "site": (
        "Site or station index dimension with longitude and latitude supplied as auxiliary "
        "coordinates. QA/QC verifies the geographic auxiliary coordinates and dimension length."
    ),
}
GENERIC_LEVEL_METADATA = {
    "alevel": (
        "Atmospheric Model Level",
        (
            "Generic atmospheric model vertical coordinate (nondimensional or dimensional). Use "
            "the CF standard name appropriate for the model vertical coordinate, for example "
            "model_level_number or atmosphere_sigma_coordinate."
        ),
    ),
    "alevhalf": (
        "Atmospheric Model Half-level",
        (
            "Generic atmospheric model vertical half-level coordinate (nondimensional or dimensional)."
            " Use the CF standard name appropriate for the model vertical coordinate, for example "
            "model_level_number or atmosphere_sigma_coordinate."
        ),
    ),
    "olevel": (
        "Ocean Model Level",
        (
            "Generic ocean model vertical coordinate (nondimensional or dimensional). "
            "Use the CF standard name appropriate for the model vertical coordinate."
        ),
    ),
    "olevhalf": (
        "Ocean Model Half Level",
        (
            "Generic ocean model vertical half-level coordinate (nondimensional or dimensional). "
            "Use the CF standard name appropriate for the model vertical coordinate."
        ),
    ),
}
DESCRIPTOR_REFERENCES = {
    "data_coordinate": {"coordinate_type": "coordinate_type"},
    "formula_term": {"dimensions": "data_coordinate"},
    "grid_variable": {"dimensions": "data_coordinate"},
    "model_level_coordinate": {
        "generic_level_name": "data_coordinate",
        "z_factors": "formula_term",
        "z_bounds_factors": "formula_term",
    },
    "known_branded_variable": {
        "variable_root_name": "variable",
        "dimensions": "data_coordinate",
        "temporal_label": "temporal_label",
        "vertical_label": "vertical_label",
        "horizontal_label": "horizontal_label",
        "area_label": "area_label",
        "realm": "realm",
        "table_id": "table",
        "frequency": "frequency",
    },
}
REFERENCE_PROPERTY_IDS = {
    ("model_level_coordinate", "z_factors"): f"{UNIVERSE_BASE}/z_factors",
    ("model_level_coordinate", "z_bounds_factors"): f"{UNIVERSE_BASE}/z_bounds_factors",
}


@dataclass(frozen=True)
class CmorVariable:
    table_id: str
    variable_entry: str
    entry: dict[str, Any]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos-base-dir", type=Path, default=script_dir.parents[1])
    parser.add_argument("--cordex-cmip6-cmor-tables-dir", type=Path)
    parser.add_argument("--wcrp-universe-dir", type=Path)
    parser.add_argument("--cordex-cmip6-cv-dir", type=Path)
    parser.add_argument("--branded-variable-mapping-path", type=Path)
    parser.add_argument(
        "--dataset-metadata-path",
        type=Path,
        help=(
            "Path to data-request-table/cmor-table/datasets.csv, used as the "
            "CORDEX-CMIP6 realm metadata source."
        ),
    )
    parser.add_argument(
        "--known-branded-variable-metadata-dir",
        type=Path,
        help=(
            "Optional directory of existing known-branded-variable JSON files used "
            "to recover project-specific realm metadata."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=script_dir / "cc6_cv_universe_overlay_report.json",
    )
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    base = args.repos_base_dir
    cmor_repo = args.cordex_cmip6_cmor_tables_dir or base / "cordex-cmip6-cmor-tables"
    return {
        "cmor": cmor_repo / "Tables",
        "universe": args.wcrp_universe_dir or base / "WCRP-universe",
        "project": args.cordex_cmip6_cv_dir or base / "cordex-cmip6-cv",
        "mapping": args.branded_variable_mapping_path
        or base
        / "cc-plugin-wcrp/plugins/cordex_cmip6/config/wcrp/mappings/"
        "frequency_and_variable_id_to_branded_variable.toml",
        "dataset_metadata": args.dataset_metadata_path
        or base / "data-request-table" / "cmor-table" / "datasets.csv",
        "known_metadata": args.known_branded_variable_metadata_dir
        or base / "WCRP-universe" / "known_branded_variable",
    }


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.exists() else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)
        handle.write("\n")


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return not value
    return False


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def split_words(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if not is_empty(item)]
    text = str(value).strip()
    return text.split() if text else []


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def audit_compound_mapping(
    generated: dict[str, str],
    mapping_path: Path,
    report: dict[str, Any],
) -> None:
    """Compare generated compound-name mappings with the compliance-checker map."""
    if not mapping_path.is_file():
        warning = f"Branded-variable verification mapping not found: {mapping_path}"
        report["compound_mapping_verification"] = {
            "status": "mapping_not_found",
            "path": str(mapping_path),
        }
        report["warnings"].append(warning)
        print(f"WARNING: {warning}")
        return

    with mapping_path.open("rb") as handle:
        content = tomllib.load(handle)
    raw_reference = content.get("mapping_variables")
    if not isinstance(raw_reference, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_reference.items()
    ):
        raise ValueError(f"Invalid mapping_variables table in {mapping_path}")
    reference = dict(raw_reference)
    missing_from_reference = sorted(generated.keys() - reference.keys())
    missing_from_generated = sorted(reference.keys() - generated.keys())
    mismatches = {
        compound: {
            "generated": generated[compound],
            "reference": reference[compound],
        }
        for compound in sorted(generated.keys() & reference.keys())
        if generated[compound] != reference[compound]
    }
    difference_count = (
        len(missing_from_reference) + len(missing_from_generated) + len(mismatches)
    )
    report["compound_mapping_verification"] = {
        "status": "matches" if difference_count == 0 else "differences_found",
        "path": str(mapping_path),
        "generated_count": len(generated),
        "reference_count": len(reference),
        "generated_compounds_missing_from_reference": missing_from_reference,
        "reference_compounds_missing_from_generated": missing_from_generated,
        "branded_variable_mismatches": mismatches,
    }
    if difference_count:
        warning = (
            f"Branded-variable mapping verification found {difference_count} difference(s): "
            f"{len(mismatches)} mismatched value(s), "
            f"{len(missing_from_reference)} generated compound(s) absent from the reference, "
            f"and {len(missing_from_generated)} reference compound(s) absent from the CMOR tables"
        )
        report["warnings"].append(warning)
        print(f"WARNING: {warning}")


def parse_number(value: Any, data_type: str) -> int | float:
    number = float(value)
    if data_type == "integer":
        if not number.is_integer():
            raise ValueError(f"Expected integer value, got {value!r}")
        return int(number)
    return number


def parse_numeric_values(value: Any, data_type: str) -> list[int | float] | None:
    words = split_words(value)
    return [parse_number(word, data_type) for word in words] if words else None


def parse_optional_float(value: Any) -> float | None:
    return None if is_empty(value) else float(value)


def yes_no(value: Any) -> bool | None:
    text = optional_text(value)
    if text is None:
        return None
    if text.lower() == "yes":
        return True
    if text.lower() == "no":
        return False
    raise ValueError(f"Expected 'yes' or 'no', got {value!r}")


def add_optional(payload: dict[str, Any], key: str, value: Any) -> None:
    if not is_empty(value):
        payload[key] = value


def omit_blank_optional_text(
    descriptor: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Omit blank strings where the descriptor schema permits absence."""
    normalized = dict(payload)
    for field_name in OPTIONAL_NON_EMPTY_TEXT_FIELDS.get(descriptor, set()):
        value = normalized.get(field_name)
        if isinstance(value, str) and not value.strip():
            normalized.pop(field_name)
    return normalized


def build_context(descriptor: str, *, include_vocab: bool) -> dict[str, Any]:
    """Build a context; only the Universe layer owns the fallback vocabulary."""
    references = DESCRIPTOR_REFERENCES.get(descriptor, {})
    context: dict[str, Any] = {"@base": f"{UNIVERSE_BASE}/{descriptor}/"}
    if include_vocab:
        context["@vocab"] = "http://schema.org/"
    context.update(
        {
            "id": "@id",
            "type": "@type",
            descriptor: f"{UNIVERSE_BASE}/{descriptor}/",
        }
    )
    for field_name, target in references.items():
        context[field_name] = {
            "@id": REFERENCE_PROPERTY_IDS.get(
                (descriptor, field_name), f"{UNIVERSE_BASE}/{target}/"
            ),
            "@type": "@id",
            "@context": {"@base": f"{UNIVERSE_BASE}/{target}/"},
        }
    payload: dict[str, Any] = {"@context": context}
    if references:
        payload["esgvoc_resolve_modes"] = dict.fromkeys(references, "full")
    return payload


def emit(
    path: Path,
    payload: dict[str, Any],
    *,
    dry_run: bool,
    report: dict[str, Any],
    category: str,
) -> None:
    existing = read_json_if_exists(path)
    if existing == payload:
        return
    action = "created" if existing is None else "updated"
    report[f"{action}_entries"].setdefault(category, []).append(path.stem)
    if not dry_run:
        write_json(path, payload)


def project_overlay(
    full_payload: dict[str, Any],
    universe_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    identity = {"@context", "id", "type"}
    overlay = {key: full_payload[key] for key in identity if key in full_payload}
    differences = {}
    for key, project_value in full_payload.items():
        if key in identity:
            continue
        # Project files are sparse overlays. Missing source metadata must
        # inherit from the Universe rather than mask it with null/blank values.
        if is_empty(project_value):
            continue
        universe_value = universe_payload.get(key)
        is_known_project_field = (
            full_payload.get("type") == "known_branded_variable"
            and key in KNOWN_BRANDED_VARIABLE_PROJECT_ONLY_FIELDS
        )
        if (
            key in PROJECT_ONLY_FIELDS
            or is_known_project_field
            or project_value != universe_value
        ):
            overlay[key] = project_value
            differences[key] = {
                "universe": universe_value,
                "cordex_cmip6": project_value,
            }
    return overlay, differences


def universe_base_payload(full_payload: dict[str, Any]) -> dict[str, Any]:
    excluded = set(PROJECT_ONLY_FIELDS)
    is_known_branded_variable = full_payload.get("type") == "known_branded_variable"
    if is_known_branded_variable:
        excluded.update(KNOWN_BRANDED_VARIABLE_PROJECT_ONLY_FIELDS)
    payload = {
        key: value
        for key, value in full_payload.items()
        if key not in excluded
        and (
            not is_known_branded_variable
            or key == "var_def_qualifier"
            or not is_empty(value)
        )
    }
    if is_known_branded_variable:
        canonical_time = CANONICAL_TIME_COORDINATE_BY_TEMPORAL_LABEL.get(
            str(payload.get("temporal_label", "")).lower()
        )
        dimensions = payload.get("dimensions")
        if canonical_time is not None and isinstance(dimensions, list):
            payload["dimensions"] = [
                canonical_time if dimension == "time" else dimension
                for dimension in dimensions
            ]
    return payload


def preserve_existing_universe_payload(
    candidate: dict[str, Any], existing: dict[str, Any] | None
) -> dict[str, Any]:
    """Return an existing Universe term unchanged, or a new candidate term."""
    return candidate if existing is None else existing


def build_universe_time_coordinate_payload(
    identifier: str, description: str
) -> dict[str, Any]:
    """Build a canonical aggregate-time coordinate used by branded variables."""
    return {
        "@context": "000_context.jsonld",
        "id": identifier,
        "type": "data_coordinate",
        "description": description,
        "drs_name": identifier,
        "coordinate_type": "standard_1d",
        "data_type": "double",
        "out_name": "time",
        "cf_standard_name": "time",
        "units": "days since ?",
        "axis": "T",
        "stored_direction": "increasing",
        "bounds_required": True,
        "is_climatology": True,
        "is_generic_model_level_coordinate": False,
    }


def load_cmor_variables(cmor_dir: Path) -> list[CmorVariable]:
    records = []
    excluded = {"coordinate", "formula_terms", "grids", "remo_example", "CV"}
    for table_path in sorted(cmor_dir.glob("CORDEX-CMIP6_*.json")):
        table_id = table_path.stem.removeprefix("CORDEX-CMIP6_")
        if table_id in excluded:
            continue
        for variable_entry, raw_entry in (
            read_json(table_path).get("variable_entry", {}).items()
        ):
            entry = dict(raw_entry)
            if entry.get("out_name") == "od550aer":
                entry["comment"] = (
                    "AOD from ambient aerosols, including aerosol water. It excludes prescribed "
                    "stratospheric aerosol but includes other background aerosol types. The file "
                    "needs a wavelength: 550nm comment attribute."
                )
            records.append(CmorVariable(table_id, variable_entry, entry))
    return records


def load_table_payloads(cmor_dir: Path) -> dict[str, dict[str, Any]]:
    payloads = {}
    excluded = {"coordinate", "formula_terms", "grids", "CV"}
    for table_path in sorted(cmor_dir.glob("CORDEX-CMIP6_*.json")):
        table_id = table_path.stem.removeprefix("CORDEX-CMIP6_")
        if table_id in excluded:
            continue
        content = read_json(table_path)
        header = content.get("Header", {})
        variable_entries = content.get("variable_entry")
        if not header or not isinstance(variable_entries, dict):
            continue
        payloads[table_id] = {
            "@context": "000_context.jsonld",
            "id": table_id.lower(),
            "type": "table",
            "description": f"CORDEX-CMIP6 {table_id} CMOR table.",
            "drs_name": table_id,
            "product": optional_text(header.get("product")),
            "table_date": optional_text(header.get("table_date")),
            "variable_entry": sorted(variable_entries),
        }
    return payloads


def build_variable_payload(out_name: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "@context": "000_context.jsonld",
        "id": out_name.lower(),
        "type": "variable",
        "description": str(entry.get("comment", "")),
        "drs_name": out_name,
        "long_name": optional_text(entry.get("long_name")),
        "standard_name": optional_text(entry.get("standard_name")),
        "units": str(entry.get("units", "")),
    }


def merge_variable_payloads(
    existing: dict[str, Any], candidate: dict[str, Any], identifier: str
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in candidate.items():
        if is_empty(merged.get(key)) and not is_empty(value):
            merged[key] = value
        elif not is_empty(value) and merged.get(key) != value:
            print(
                f"WARNING: variable {identifier!r} has conflicting {key}: "
                f"{merged.get(key)!r} versus {value!r}; keeping the first value."
            )
    return merged


def build_variable_payloads(
    records: list[CmorVariable],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Build all Universe variables and return the actual project variable IDs."""
    payloads: dict[str, dict[str, Any]] = {}
    project_variable_ids: set[str] = set()
    for record in records:
        out_name = str(record.entry.get("out_name", record.variable_entry))
        candidate = build_variable_payload(out_name, record.entry)
        identifier = out_name.lower()
        project_variable_ids.add(identifier)
        if identifier in payloads:
            payloads[identifier] = merge_variable_payloads(
                payloads[identifier], candidate, identifier
            )
        else:
            payloads[identifier] = candidate

    # Canonical branded-variable roots belong in Universe even when the legacy
    # project only exposes a level- or statistic-qualified output name.
    for record in records:
        out_name = str(record.entry.get("out_name", record.variable_entry))
        root_drs_name = adjust_out_name(out_name)
        root_id = root_drs_name.lower()
        if root_id not in payloads:
            root_payload = build_variable_payload(root_drs_name, record.entry)
            root_payload["long_name"] = None
            payloads[root_id] = root_payload
    return payloads, project_variable_ids


def classify_coordinate(identifier: str, entry: dict[str, Any]) -> str:
    data_type = optional_text(entry.get("type")) or "double"
    if (
        len(split_words(entry.get("value"))) == 1
        or len(split_words(entry.get("requested"))) == 1
    ):
        return "scalar"
    if (
        len(split_words(entry.get("bounds_values"))) == 2
        or len(split_words(entry.get("requested_bounds"))) == 2
    ):
        return "scalar"
    if data_type == "character":
        return "auxiliary"
    if identifier in {"latitude", "longitude"}:
        return "generic_horizontal"
    return "standard_1d"


def build_data_coordinate_payload(
    identifier: str, entry: dict[str, Any]
) -> dict[str, Any]:
    data_type = optional_text(entry.get("type")) or "double"
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": "data_coordinate",
        "description": "",
        "drs_name": identifier,
        "coordinate_type": classify_coordinate(identifier, entry),
        "data_type": data_type,
        "long_name": str(entry["long_name"]),
        "out_name": str(entry["out_name"]),
    }
    for source_key, target_key in (
        ("standard_name", "cf_standard_name"),
        ("units", "units"),
        ("axis", "axis"),
        ("positive", "positive"),
        ("stored_direction", "stored_direction"),
    ):
        add_optional(payload, target_key, optional_text(entry.get(source_key)))
    if data_type == "character":
        values = split_words(entry.get("value")) or split_words(entry.get("requested"))
        if values:
            payload["coordinate_values"] = values[0] if len(values) == 1 else values
    else:
        values = parse_numeric_values(entry.get("value"), data_type)
        values = values or parse_numeric_values(entry.get("requested"), data_type)
        if values is not None:
            payload["coordinate_values"] = values
        bounds = parse_numeric_values(entry.get("bounds_values"), data_type)
        bounds = bounds or parse_numeric_values(
            entry.get("requested_bounds"), data_type
        )
        if bounds is not None:
            payload["coordinate_bounds"] = bounds
        for key in ("tolerance", "valid_min", "valid_max"):
            value = parse_optional_float(entry.get(key))
            if value is not None:
                payload[key] = value
    bounds_required = yes_no(entry.get("must_have_bounds"))
    if bounds_required is not None:
        payload["bounds_required"] = bounds_required
    payload["is_climatology"] = yes_no(entry.get("climatology")) or False
    payload["is_generic_model_level_coordinate"] = False
    return payload


def build_generic_coordinate_payload(identifier: str) -> dict[str, Any]:
    long_name, description = GENERIC_LEVEL_METADATA[identifier]
    return {
        "@context": "000_context.jsonld",
        "id": identifier,
        "type": "data_coordinate",
        "description": description,
        "drs_name": identifier,
        "coordinate_type": "generic_vertical",
        "axis": "Z",
        "data_type": "double",
        "long_name": long_name,
        "out_name": "lev",
        "is_climatology": False,
        "is_generic_model_level_coordinate": True,
    }


def build_vertices_coordinate_payload() -> dict[str, Any]:
    return {
        "@context": "000_context.jsonld",
        "id": "vertices",
        "type": "data_coordinate",
        "description": "Index dimension enumerating the vertices of a grid cell.",
        "drs_name": "vertices",
        "coordinate_type": "standard_1d",
        "data_type": "integer",
        "long_name": "Grid Cell Vertex Index",
        "out_name": "vertices",
        "units": "1",
        "is_climatology": False,
        "is_generic_model_level_coordinate": False,
    }


def build_model_level_payload(identifier: str, entry: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": "model_level_coordinate",
        "description": "",
        "drs_name": identifier,
        "axis": "Z",
        "data_type": optional_text(entry.get("type")) or "double",
        "long_name": str(entry["long_name"]),
        "out_name": str(entry["out_name"]),
        "positive": str(entry["positive"]),
        "stored_direction": str(entry["stored_direction"]),
        "generic_level_name": str(entry["generic_level_name"]),
    }
    for source_key, target_key in (
        ("standard_name", "cf_standard_name"),
        ("computed_standard_name", "computed_standard_name"),
        ("units", "units"),
        ("formula", "formula"),
    ):
        add_optional(payload, target_key, optional_text(entry.get(source_key)))
    for key in ("z_factors", "z_bounds_factors"):
        values = split_words(entry.get(key))
        if values:
            payload[key] = values
    bounds_required = yes_no(entry.get("must_have_bounds"))
    if bounds_required is not None:
        payload["bounds_required"] = bounds_required
    for key in ("valid_min", "valid_max"):
        value = parse_optional_float(entry.get(key))
        if value is not None:
            payload[key] = value
    return payload


def select_referenced_formula_entries(
    formula_entries: dict[str, dict[str, Any]],
    model_level_payloads: dict[str, dict[str, Any]],
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Keep formula terms referenced by at least one model-level coordinate."""
    referenced = {
        reference.lower()
        for payload in model_level_payloads.values()
        for field in ("z_factors", "z_bounds_factors")
        for reference in split_words(payload.get(field))
    }
    selected: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    for identifier, entry in sorted(formula_entries.items()):
        out_name = optional_text(entry.get("out_name")) or identifier
        if {identifier.lower(), out_name.lower()} & referenced:
            selected[identifier] = entry
            continue
        skipped.append(identifier.lower())
        warning = (
            f"formula_term {identifier!r} is not referenced by any "
            "model_level_coordinate entry and therefore skipped"
        )
        report["warnings"].append(warning)
        print(f"WARNING: {warning}")
    report["unreferenced_formula_terms"] = skipped
    return selected


def build_formula_term_payload(
    identifier: str, entry: dict[str, Any]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": "formula_term",
        "description": "",
        "drs_name": identifier,
        "data_type": str(entry["type"]),
        "long_name": str(entry["long_name"]),
        "out_name": str(entry["out_name"]),
    }
    add_optional(payload, "cf_standard_name", optional_text(entry.get("standard_name")))
    add_optional(payload, "units", optional_text(entry.get("units")))
    dimensions = split_words(entry.get("dimensions"))
    if dimensions:
        payload["dimensions"] = dimensions
    return payload


def build_grid_axis_payload(identifier: str, entry: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": "grid_axis",
        "description": "",
        "drs_name": identifier,
    }
    for source_key, target_key in (
        ("axis", "axis"),
        ("type", "data_type"),
        ("long_name", "long_name"),
        ("standard_name", "cf_standard_name"),
        ("out_name", "out_name"),
        ("units", "units"),
    ):
        add_optional(payload, target_key, optional_text(entry.get(source_key)))
    return payload


def build_grid_variable_payload(
    identifier: str, entry: dict[str, Any]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": identifier.lower(),
        "type": "grid_variable",
        "description": "",
        "drs_name": identifier,
        "data_type": str(entry["type"]),
        "out_name": str(entry["out_name"]),
        "units": str(entry["units"]),
        "dimensions": [value.lower() for value in split_words(entry.get("dimensions"))],
    }
    add_optional(payload, "long_name", optional_text(entry.get("long_name")))
    add_optional(payload, "cf_standard_name", optional_text(entry.get("standard_name")))
    for key in ("valid_min", "valid_max"):
        value = parse_optional_float(entry.get(key))
        if value is not None:
            payload[key] = value
    return payload


def adjust_out_name(out_name: str) -> str:
    invariant = {
        "abs1000nh4",
        "abs1000no3",
        "abs1000so4",
        "abs350nh4",
        "abs350no3",
        "abs350so4",
        "abs440nh4",
        "abs440no3",
        "abs440so4",
        "abs550nh4",
        "abs550no3",
        "abs550so4",
        "abs870nh4",
        "abs870no3",
        "abs870so4",
        "cheaqpso4",
        "chegpso4",
        "chepnh4",
        "chepno3",
        "concnh4",
        "concno3",
        "concso4",
        "drynh4",
        "dryno3",
        "dryso4",
        "eminh3",
        "emiso2",
        "emiso4",
        "ext550nh4",
        "ext550no3",
        "ext550so4",
        "od1000nh4",
        "od1000no3",
        "od1000so4",
        "od350nh4",
        "od350no3",
        "od350so4",
        "od440nh4",
        "od440no3",
        "od440so4",
        "od550nh4",
        "od550no3",
        "od550so4",
        "od870nh4",
        "od870no3",
        "od870so4",
        "scat550nh4",
        "scat550no3",
        "scat550so4",
        "sconcnh4",
        "sconcno3",
        "sconcso4",
        "sednh4",
        "sedno3",
        "sedso4",
        "wetnh4",
        "wetno3",
        "wetso4",
        "z0",
    }
    if out_name in invariant:
        return out_name
    if re.fullmatch(r".*\d(?:m)?", out_name):
        return out_name.rstrip("0123456789m")
    return re.sub(r"(?:max|min)$", "", out_name)


def infer_realms(existing_universe: dict[str, Any] | None) -> list[str]:
    if existing_universe is None:
        return []
    realm_values = existing_universe.get("realm")
    if not isinstance(realm_values, list):
        realm_values = [realm_values]
    # References are stored as vocabulary IDs, not as potentially mixed-case
    # DRS display names such as ``atmosChem`` or ``seaIce``.
    return unique(
        [
            realm.lower()
            for value in realm_values
            if (realm := optional_text(value)) is not None
        ]
    )


def load_realm_metadata(
    directory: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load exact and root-level realm fallbacks from generated DReq metadata."""
    exact: dict[str, list[str]] = {}
    by_root: dict[str, list[str]] = {}
    if not directory.is_dir():
        return exact, by_root
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        realms = infer_realms(payload)
        if not realms:
            continue
        identifier = str(payload.get("id", path.stem)).lower()
        exact[identifier] = realms
        root = identifier.split("_", 1)[0]
        by_root.setdefault(root, realms)
    return exact, by_root


def load_dataset_realms(path: Path) -> dict[str, list[str]]:
    """Load unique realm IDs by CMOR ``out_name`` from datasets.csv."""
    if not path.is_file():
        return {}

    realms_by_out_name: dict[str, list[str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"out_name", "realm"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"Dataset metadata {path} is missing required column(s): "
                f"{', '.join(sorted(missing))}"
            )
        for row in reader:
            out_name = optional_text(row.get("out_name"))
            realm = optional_text(row.get("realm"))
            if out_name is None or realm is None:
                continue
            key = out_name.lower()
            realms_by_out_name[key] = unique(
                [*realms_by_out_name.get(key, []), realm.lower()]
            )
    return realms_by_out_name


def infer_dataset_realms(
    records: list[CmorVariable], realms_by_out_name: dict[str, list[str]]
) -> list[str]:
    """Return all dataset realms associated with a branded-variable group."""
    return unique(
        [
            realm
            for record in records
            for realm in realms_by_out_name.get(
                str(record.entry.get("out_name", record.variable_entry)).lower(), []
            )
        ]
    )


def find_missing_universe_realm_ids(
    referenced_realms: set[str], universe_root: Path
) -> list[str]:
    """Return referenced realm IDs absent from WCRP-universe."""
    available: set[str] = set()
    realm_dir = universe_root / "realm"
    if realm_dir.is_dir():
        for path in realm_dir.glob("*.json"):
            if path.name == "000_context.jsonld":
                continue
            payload = read_json(path)
            identifier = optional_text(payload.get("id"))
            if identifier is not None:
                available.add(identifier.lower())
    return sorted(
        realm.lower() for realm in referenced_realms if realm.lower() not in available
    )


def canonical_branded_dimensions(entry: dict[str, Any]) -> list[str]:
    """Translate legacy CMOR axes to the coordinate IDs used by CMIP7 branding."""
    aliases = {
        "xant": "longitude",
        "yant": "latitude",
        "xgre": "longitude",
        "ygre": "latitude",
    }
    return [
        aliases.get(dimension.lower(), dimension.lower())
        for dimension in split_words(entry.get("dimensions"))
    ]


def branded_name_for_record(record: CmorVariable) -> str:
    """Return the CMIP7-compatible branded name for a legacy CMOR record."""
    out_name = str(record.entry.get("out_name", record.variable_entry))
    return map_to_cmip_branded_variable(
        variable_name=adjust_out_name(out_name),
        cell_methods=record.entry.get("cell_methods"),
        dimensions=tuple(canonical_branded_dimensions(record.entry)),
    )


def build_known_payload(
    branded_name: str,
    root_drs_name: str,
    records: list[CmorVariable],
    realms: list[str],
) -> dict[str, Any]:
    first = records[0]
    entry = first.entry
    suffix = branded_name.split("_", 1)[1]
    parts = suffix.split("-")
    comments = unique(
        [
            comment
            for record in records
            if (comment := optional_text(record.entry.get("comment")))
        ]
    )
    long_names = unique(
        [
            long_name
            for record in records
            if (long_name := optional_text(record.entry.get("long_name")))
        ]
    )
    cell_measures = unique(
        [
            measure
            for record in records
            if (measure := optional_text(record.entry.get("cell_measures")))
        ]
    )
    frequencies = unique(
        [
            frequency.lower()
            for record in records
            for frequency in split_words(record.entry.get("frequency"))
        ]
    )
    payload: dict[str, Any] = {
        "@context": "000_context.jsonld",
        "id": branded_name.lower(),
        "type": "known_branded_variable",
        "drs_name": f"{root_drs_name}_{suffix}",
        "variable_root_name": branded_name.split("_", 1)[0].lower(),
        "branding_suffix_name": suffix,
        "cf_standard_name": str(entry["standard_name"]),
        "out_name": root_drs_name,
        "units": optional_text(entry.get("units")),
        "dimensions": canonical_branded_dimensions(entry),
        # Label properties contain vocabulary IDs. Their possibly mixed-case
        # DRS names are retained in ``branding_suffix_name`` and ``drs_name``.
        "temporal_label": parts[0].lower(),
        "vertical_label": parts[1].lower(),
        "horizontal_label": parts[2].lower(),
        "area_label": "-".join(parts[3:]).lower(),
        "var_def_qualifier": None,
        "history": KNOWN_BRANDED_VARIABLE_HISTORY,
        "bn_status": "accepted",
        "cf_sn_status": "approved",
        "table_id": unique([record.table_id.lower() for record in records]),
        "compound_name": unique(
            [f"{record.table_id}.{record.variable_entry}" for record in records]
        ),
        "frequency": frequencies or None,
    }
    add_optional(payload, "long_name", long_names)
    add_optional(payload, "comment", comments)
    add_optional(payload, "cell_methods", optional_text(entry.get("cell_methods")))
    add_optional(payload, "cell_measures", cell_measures)
    add_optional(payload, "realm", realms)
    for record in records[1:]:
        candidate = record.entry
        for key in (
            "standard_name",
            "units",
            "out_name",
            "cell_methods",
        ):
            if optional_text(entry.get(key)) != optional_text(candidate.get(key)):
                print(
                    f"WARNING: {branded_name!r} has conflicting {key} in "
                    f"{first.table_id}.{first.variable_entry} and "
                    f"{record.table_id}.{record.variable_entry}; keeping the first value."
                )
        candidate_dimensions = canonical_branded_dimensions(candidate)
        if candidate_dimensions != payload["dimensions"]:
            print(
                f"WARNING: {branded_name!r} has differing dimensions; keeping "
                f"{first.table_id}.{first.variable_entry}."
            )
    return payload


def ensure_labels(
    known_payloads: dict[str, dict[str, Any]],
    universe_root: Path,
    *,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    definitions = (
        ("temporal_label", False),
        ("vertical_label", False),
        ("horizontal_label", False),
        ("area_label", True),
    )
    for payload in known_payloads.values():
        for field_name, is_area in definitions:
            label = str(payload[field_name])
            path = universe_root / field_name / f"{label.lower()}.json"
            if path.exists():
                continue
            description = ""
            if field_name == "vertical_label":
                pressure = re.fullmatch(r"(\d+)hpa", label, flags=re.IGNORECASE)
                height = re.fullmatch(r"h(\d+)m", label, flags=re.IGNORECASE)
                if pressure:
                    description = f"Data is reported at an atmospheric pressure of {pressure.group(1)} hPa."
                elif height:
                    description = (
                        f"Data is reported at a vertical height of {height.group(1)} m."
                    )
            label_payload: dict[str, Any] = {
                "@context": "000_context.jsonld",
                "id": label.lower(),
                "type": field_name,
                "description": description,
                "drs_name": label,
            }
            if is_area:
                label_payload["cf_area_type"] = None
            emit(
                path,
                label_payload,
                dry_run=dry_run,
                report=report,
                category=f"universe_{field_name}",
            )
            print(
                f"WARNING: created missing {field_name} {label!r}; please review it manually."
            )


def validate_payload(descriptor: str, payload: dict[str, Any]) -> None:
    from esgvoc.api.pydantic_handler import get_pydantic_class
    from pydantic import TypeAdapter

    TypeAdapter(get_pydantic_class(descriptor)).validate_python(payload)


def generate_contexts(
    universe_root: Path,
    project_root: Path,
    *,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    universe_descriptors = {
        "coordinate_type",
        "data_coordinate",
        "formula_term",
        "grid_axis",
        "grid_variable",
        "model_level_coordinate",
        "known_branded_variable",
        "table",
    }
    project_descriptors = universe_descriptors - {"coordinate_type"}
    for descriptor in sorted(universe_descriptors):
        emit(
            universe_root / descriptor / "000_context.jsonld",
            build_context(descriptor, include_vocab=True),
            dry_run=dry_run,
            report=report,
            category=f"universe_{descriptor}_context",
        )
    for descriptor in sorted(project_descriptors):
        emit(
            project_root / descriptor / "000_context.jsonld",
            build_context(descriptor, include_vocab=False),
            dry_run=dry_run,
            report=report,
            category=f"project_{descriptor}_context",
        )


def emit_layered_payload(
    descriptor: str,
    full_payload: dict[str, Any],
    universe_root: Path,
    project_root: Path,
    *,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    full_payload = omit_blank_optional_text(descriptor, full_payload)
    identifier = str(full_payload["id"]).lower()
    validate_payload(descriptor, full_payload)
    universe_path = universe_root / descriptor / f"{identifier}.json"
    existing_universe = read_json_if_exists(universe_path)
    if (
        descriptor == "known_branded_variable"
        and existing_universe is None
        and full_payload.get("history") != KNOWN_BRANDED_VARIABLE_HISTORY
    ):
        raise ValueError(
            f"New Universe known branded variable {identifier!r} must have history "
            f"{KNOWN_BRANDED_VARIABLE_HISTORY!r}"
        )
    universe_payload = preserve_existing_universe_payload(
        universe_base_payload(full_payload), existing_universe
    )
    if existing_universe is None:
        validate_payload(descriptor, universe_payload)
    emit(
        universe_path,
        universe_payload,
        dry_run=dry_run,
        report=report,
        category=f"universe_{descriptor}",
    )
    overlay, differences = project_overlay(full_payload, universe_payload)
    report["overlay_differences"].setdefault(descriptor, {})[identifier] = differences
    emit(
        project_root / descriptor / f"{identifier}.json",
        overlay,
        dry_run=dry_run,
        report=report,
        category=f"project_{descriptor}",
    )


def main() -> None:
    args = parse_args()
    paths = resolve_paths(args)
    cmor_dir = paths["cmor"]
    universe_root = paths["universe"]
    project_root = paths["project"]
    report: dict[str, Any] = {
        "dry_run": args.dry_run,
        "created_entries": {},
        "updated_entries": {},
        "overlay_differences": {},
        "warnings": [],
    }
    generate_contexts(universe_root, project_root, dry_run=args.dry_run, report=report)

    for identifier, description in COORDINATE_TYPES.items():
        candidate = {
            "@context": "000_context.jsonld",
            "id": identifier,
            "type": "coordinate_type",
            "description": description,
            "drs_name": identifier,
        }
        path = universe_root / "coordinate_type" / f"{identifier}.json"
        payload = preserve_existing_universe_payload(
            candidate, read_json_if_exists(path)
        )
        validate_payload("coordinate_type", payload)
        emit(
            path,
            payload,
            dry_run=args.dry_run,
            report=report,
            category="universe_coordinate_type",
        )

    for identifier, description in UNIVERSE_TIME_COORDINATES.items():
        path = universe_root / "data_coordinate" / f"{identifier}.json"
        payload = preserve_existing_universe_payload(
            build_universe_time_coordinate_payload(identifier, description),
            read_json_if_exists(path),
        )
        validate_payload("data_coordinate", payload)
        emit(
            path,
            payload,
            dry_run=args.dry_run,
            report=report,
            category="universe_data_coordinate",
        )

    cmor_variables = load_cmor_variables(cmor_dir)
    variables_by_id, project_variable_ids = build_variable_payloads(cmor_variables)
    for identifier, full_payload in sorted(variables_by_id.items()):
        universe_path = universe_root / "variable" / f"{identifier}.json"
        existing_universe = read_json_if_exists(universe_path)
        universe_payload = existing_universe or full_payload
        validate_payload("variable", universe_payload)
        if existing_universe is None:
            emit(
                universe_path,
                universe_payload,
                dry_run=args.dry_run,
                report=report,
                category="universe_variable",
            )
        if identifier in project_variable_ids:
            overlay, differences = project_overlay(full_payload, universe_payload)
            report["overlay_differences"].setdefault("variable", {})[identifier] = (
                differences
            )
            emit(
                project_root / "variable_id" / f"{identifier}.json",
                overlay,
                dry_run=args.dry_run,
                report=report,
                category="project_variable_id",
            )

    coordinate_content = read_json(cmor_dir / "CORDEX-CMIP6_coordinate.json")
    axis_entries = coordinate_content.get("axis_entry", {})
    model_level_entries = {
        identifier: entry
        for identifier, entry in axis_entries.items()
        if not is_empty(entry.get("generic_level_name"))
    }
    data_entries = {
        identifier: entry
        for identifier, entry in axis_entries.items()
        if identifier not in model_level_entries
    }
    generic_ids = {
        generic_id
        for entry in model_level_entries.values()
        for generic_id in split_words(entry.get("generic_level_name"))
    }
    formula_content = read_json(cmor_dir / "CORDEX-CMIP6_formula_terms.json")
    formula_entries = formula_content.get("formula_entry", {})
    model_level_payloads = {
        identifier: build_model_level_payload(identifier, entry)
        for identifier, entry in model_level_entries.items()
    }
    referenced_formula_entries = select_referenced_formula_entries(
        formula_entries, model_level_payloads, report
    )
    generic_ids.update(
        dimension
        for entry in referenced_formula_entries.values()
        for dimension in split_words(entry.get("dimensions"))
        if dimension in GENERIC_LEVEL_METADATA
    )
    data_payloads = {
        identifier: build_data_coordinate_payload(identifier, entry)
        for identifier, entry in data_entries.items()
    }
    for generic_id in sorted(generic_ids):
        if generic_id not in GENERIC_LEVEL_METADATA:
            raise ValueError(f"No generic coordinate metadata for {generic_id!r}")
        data_payloads[generic_id] = build_generic_coordinate_payload(generic_id)
    data_payloads["vertices"] = build_vertices_coordinate_payload()
    for payload in data_payloads.values():
        emit_layered_payload(
            "data_coordinate",
            payload,
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )
    for payload in model_level_payloads.values():
        emit_layered_payload(
            "model_level_coordinate",
            payload,
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )
    for identifier, entry in referenced_formula_entries.items():
        emit_layered_payload(
            "formula_term",
            build_formula_term_payload(identifier, entry),
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )

    grid_content = read_json(cmor_dir / "CORDEX-CMIP6_grids.json")
    for identifier, entry in grid_content.get("axis_entry", {}).items():
        emit_layered_payload(
            "grid_axis",
            build_grid_axis_payload(identifier, entry),
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )
    for identifier, entry in grid_content.get("variable_entry", {}).items():
        emit_layered_payload(
            "grid_variable",
            build_grid_variable_payload(identifier, entry),
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )

    for table_id, project_table in load_table_payloads(cmor_dir).items():
        universe_path = universe_root / "table" / f"{table_id.lower()}.json"
        existing_universe = read_json_if_exists(universe_path)
        universe_table = existing_universe or {
            "@context": "000_context.jsonld",
            "id": table_id.lower(),
            "type": "table",
            "description": f"Table identifier used by CORDEX-CMIP6 {table_id}.",
            "drs_name": table_id,
            "product": None,
            "table_date": None,
            "variable_entry": [],
        }
        validate_payload("table", universe_table)
        if existing_universe is None:
            emit(
                universe_path,
                universe_table,
                dry_run=args.dry_run,
                report=report,
                category="universe_table",
            )
        table_overlay, differences = project_overlay(project_table, universe_table)
        report["overlay_differences"].setdefault("table", {})[table_id] = differences
        emit(
            project_root / "table" / f"{table_id.lower()}.json",
            table_overlay,
            dry_run=args.dry_run,
            report=report,
            category="project_table",
        )

    known_groups: dict[str, list[CmorVariable]] = {}
    generated_compound_mapping: dict[str, str] = {}
    for record in cmor_variables:
        branded_name = branded_name_for_record(record)
        known_groups.setdefault(branded_name.lower(), []).append(record)
        generated_compound_mapping[f"{record.table_id}.{record.variable_entry}"] = (
            branded_name
        )
    audit_compound_mapping(
        generated_compound_mapping,
        paths["mapping"],
        report,
    )
    realm_by_id, realm_by_root = load_realm_metadata(paths["known_metadata"])
    dataset_realms = load_dataset_realms(paths["dataset_metadata"])
    if not dataset_realms:
        warning = (
            f"Dataset realm metadata not found or empty: {paths['dataset_metadata']}"
        )
        report["warnings"].append(warning)
        print(f"WARNING: {warning}")
    known_payloads = {}
    referenced_realms: set[str] = set()
    for identifier, records in sorted(known_groups.items()):
        branded_name = branded_name_for_record(records[0])
        root_id = branded_name.split("_", 1)[0].lower()
        root_payload = read_json_if_exists(
            universe_root / "variable" / f"{root_id}.json"
        )
        root_payload = root_payload or variables_by_id.get(root_id)
        if root_payload is None:
            raise ValueError(
                f"{branded_name!r} references missing variable root {root_id!r}"
            )
        existing_known = read_json_if_exists(
            universe_root / "known_branded_variable" / f"{identifier}.json"
        )
        realms = infer_realms(existing_known)
        realms = (
            realms
            or realm_by_id.get(identifier)
            or realm_by_root.get(root_id, [])
            or infer_dataset_realms(records, dataset_realms)
        )
        payload = build_known_payload(
            branded_name, str(root_payload["drs_name"]), records, realms
        )
        if not realms:
            warning = f"No realm could be inferred for {identifier}"
            report["warnings"].append(warning)
            print(f"WARNING: {warning}")
        referenced_realms.update(realms)
        known_payloads[identifier] = payload
        emit_layered_payload(
            "known_branded_variable",
            payload,
            universe_root,
            project_root,
            dry_run=args.dry_run,
            report=report,
        )
    for realm in find_missing_universe_realm_ids(referenced_realms, universe_root):
        warning = (
            f"Realm {realm!r} is referenced but missing from WCRP-universe; "
            "create it manually."
        )
        report["warnings"].append(warning)
        print(f"WARNING: {warning}")
    ensure_labels(
        known_payloads,
        universe_root,
        dry_run=args.dry_run,
        report=report,
    )
    write_json(args.report_path, report)
    print("#" * 60)
    print(f"CMOR variable records processed: {len(cmor_variables)}")
    print(f"Unique variable roots: {len(variables_by_id)}")
    print(f"Unique known branded variables: {len(known_payloads)}")
    print(f"Data coordinates: {len(data_payloads)}")
    print(f"Run mode: {'dry-run' if args.dry_run else 'write'}")
    print(f"Report: {args.report_path}")


if __name__ == "__main__":
    main()
