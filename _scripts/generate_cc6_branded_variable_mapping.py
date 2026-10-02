"""Generate only the CORDEX-CMIP6 compound-to-branded-variable mapping."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

MAPPING_FILENAME = "frequency_and_variable_id_to_branded_variable.toml"
MAPPER_COMPATIBILITY_CASES = (
    (
        "tas",
        "area: mean time: maximum within days time: mean over days",
        "tas_tmaxavg-u-hxy-u",
    ),
    (
        "tas",
        "area: mean time: minimum within days time: mean over days",
        "tas_tminavg-u-hxy-u",
    ),
    (
        "prh",
        "area: mean time: mean within hours time: maximum over hours",
        "prh_tavgmax-u-hxy-u",
    ),
    (
        "sund",
        "time: sum within days time: mean over days",
        "sund_tsumavg-u-hxy-u",
    ),
)


def load_main_generator() -> ModuleType:
    """Load the full generator whose CMOR parsing and mapping logic we reuse."""
    path = (
        Path(__file__).resolve().parent
        / "generate_cc6_cv_and_universe_variables_and_known_branded_variables.py"
    )
    spec = importlib.util.spec_from_file_location("generate_cc6_cv_mapping_source", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load the CORDEX-CMIP6 generator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = load_main_generator()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_base = script_dir.parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos-base-dir",
        type=Path,
        default=default_base,
        help="Directory containing the sibling repositories.",
    )
    parser.add_argument(
        "--cordex-cmip6-cmor-tables-dir",
        type=Path,
        help=(
            "CORDEX-CMIP6 CMOR-tables repository or its Tables directory. "
            "Defaults to <repos-base-dir>/cordex-cmip6-cmor-tables."
        ),
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help=(
            "Mapping TOML to create or update. Defaults to the active "
            "cc-plugin-wcrp CORDEX-CMIP6 mapping below <repos-base-dir>."
        ),
    )
    parser.add_argument(
        "--force-conflicts",
        action="store_true",
        help="Replace an existing mapping even when mapped values conflict.",
    )
    parser.add_argument(
        "--allow-incompatible-mapper",
        action="store_true",
        help=(
            "Write even if the imported branded-variable mapper fails the "
            "CORDEX-specific compatibility probes."
        ),
    )
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    base = args.repos_base_dir.resolve()
    cmor_path = args.cordex_cmip6_cmor_tables_dir
    if cmor_path is None:
        cmor_path = base / "cordex-cmip6-cmor-tables"
    cmor_path = cmor_path.resolve()
    cmor_dir = cmor_path if cmor_path.name == "Tables" else cmor_path / "Tables"
    output_path = args.output_path or (
        base
        / "cc-plugin-wcrp"
        / "plugins"
        / "cordex_cmip6"
        / "config"
        / "wcrp"
        / "mappings"
        / MAPPING_FILENAME
    )
    return cmor_dir, output_path.resolve()


def check_mapper_compatibility() -> list[dict[str, str]]:
    """Return failures of behavior supplied by the mapper's CORDEX branch."""
    failures = []
    dimensions = ("longitude", "latitude", "time")
    for variable_name, cell_methods, expected in MAPPER_COMPATIBILITY_CASES:
        actual = generator.map_to_cmip_branded_variable(
            variable_name=variable_name,
            cell_methods=cell_methods,
            dimensions=dimensions,
        )
        if actual != expected:
            failures.append(
                {
                    "cell_methods": cell_methods,
                    "expected": expected,
                    "actual": actual,
                }
            )
    return failures


def build_mapping(cmor_dir: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Build the mapping with the full generator's loaders and mapping function."""
    mapping: dict[str, str] = {}
    source_conflicts: dict[str, list[str]] = {}
    for record in generator.load_cmor_variables(cmor_dir):
        compound_name = f"{record.table_id}.{record.variable_entry}"
        branded_name = generator.branded_name_for_record(record)
        previous = mapping.get(compound_name)
        if previous is not None and previous != branded_name:
            values = source_conflicts.setdefault(compound_name, [previous])
            if branded_name not in values:
                values.append(branded_name)
            continue
        mapping[compound_name] = branded_name
    return dict(sorted(mapping.items())), source_conflicts


def load_mapping(path: Path) -> dict[str, str]:
    """Load and validate an existing mapping, or return an empty mapping."""
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    raw_mapping = payload.get("mapping_variables")
    if not isinstance(raw_mapping, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_mapping.items()
    ):
        raise ValueError(f"Invalid mapping_variables table in {path}")
    return dict(raw_mapping)


def compare_mappings(
    generated: dict[str, str], existing: dict[str, str]
) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    """Return new, conflicting, and obsolete entries, each sorted by key."""
    new = {
        key: generated[key] for key in sorted(generated.keys() - existing.keys())
    }
    conflicts = {
        key: {"existing": existing[key], "generated": generated[key]}
        for key in sorted(generated.keys() & existing.keys())
        if generated[key] != existing[key]
    }
    obsolete = {
        key: existing[key] for key in sorted(existing.keys() - generated.keys())
    }
    return new, conflicts, obsolete


def toml_string(value: str) -> str:
    """Encode a TOML basic string using JSON's compatible escaping rules."""
    return json.dumps(value, ensure_ascii=False)


def write_mapping(path: Path, mapping: dict[str, str]) -> None:
    """Write a deterministic mapping file compatible with cc-plugin-wcrp."""
    lines = [
        "# ==============================================================================",
        "# == Mappings to get branded_variable from table_id + variable_id",
        "# ==============================================================================",
        "",
        "[mapping_variables]",
    ]
    lines.extend(
        f"{toml_string(key)} = {toml_string(value)}"
        for key, value in mapping.items()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def order_mapping_for_update(
    generated: dict[str, str], existing: dict[str, str]
) -> dict[str, str]:
    """Preserve surviving existing entries and append new ones deterministically."""
    ordered = {key: generated[key] for key in existing if key in generated}
    ordered.update(
        (key, generated[key]) for key in sorted(generated.keys() - existing.keys())
    )
    return ordered


def print_changes(
    new: dict[str, str],
    conflicts: dict[str, dict[str, str]],
    obsolete: dict[str, str],
    source_conflicts: dict[str, list[str]],
) -> None:
    """Print every mapping difference separately for review."""
    for key, value in new.items():
        print(f"NEW: {toml_string(key)} = {toml_string(value)}")
    for key, values in conflicts.items():
        print(
            f"CONFLICT: {key}: existing={values['existing']!r}, "
            f"generated={values['generated']!r}"
        )
    for key, value in obsolete.items():
        print(f"OBSOLETE: {toml_string(key)} = {toml_string(value)}")
    for key, values in source_conflicts.items():
        print(f"SOURCE CONFLICT: {key}: generated values={values!r}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cmor_dir, output_path = resolve_paths(args)
    if not cmor_dir.is_dir():
        raise FileNotFoundError(f"CMOR Tables directory not found: {cmor_dir}")

    mapper_path = Path(inspect.getfile(generator.map_to_cmip_branded_variable)).resolve()
    mapper_failures = check_mapper_compatibility()
    generated, source_conflicts = build_mapping(cmor_dir)
    output_existed = output_path.is_file()
    existing = load_mapping(output_path)
    new, conflicts, obsolete = compare_mappings(generated, existing)
    print(f"Mapper implementation: {mapper_path}")
    print_changes(new, conflicts, obsolete, source_conflicts)
    print(
        "Summary: "
        f"{len(generated)} generated; {len(new)} new; "
        f"{len(conflicts)} conflict(s); {len(obsolete)} obsolete; "
        f"{len(source_conflicts)} source conflict(s)."
    )

    if mapper_failures:
        print("ERROR: the imported mapper lacks required CORDEX-CMIP6 behavior:")
        for failure in mapper_failures:
            print(
                f"- {failure['cell_methods']!r}: expected "
                f"{failure['expected']!r}, got {failure['actual']!r}"
            )
        print(
            "Install CMIP-branded-variable-mapper from the cordex-cmip6 branch "
            "of https://github.com/sol1105/CMIP-branded-variable-mapper."
        )
        if not args.allow_incompatible_mapper:
            print("Mapping was not written.")
            return 2

    if source_conflicts:
        print("ERROR: the CMOR sources generated conflicting values for the same key.")
        print("Mapping was not written.")
        return 2
    if conflicts and not args.force_conflicts:
        print("ERROR: existing mapping conflicts require review.")
        print("Mapping was not written; pass --force-conflicts after review to replace it.")
        return 2

    if output_existed and not new and not conflicts and not obsolete:
        print(f"Mapping is already up to date: {output_path}")
        return 0

    mapping_to_write = order_mapping_for_update(generated, existing)
    write_mapping(output_path, mapping_to_write)
    action = "Updated" if output_existed else "Created"
    print(f"{action} mapping: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
