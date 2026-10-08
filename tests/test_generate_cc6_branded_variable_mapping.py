"""Regression tests for the CORDEX-CMIP6 mapping-only generator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def load_mapping_generator() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "_scripts"
        / "generate_cc6_branded_variable_mapping.py"
    )
    spec = importlib.util.spec_from_file_location("generate_cc6_mapping", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load mapping generator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mapping_generator = load_mapping_generator()


def test_mapper_has_required_cordex_behavior() -> None:
    assert mapping_generator.check_mapper_compatibility() == []


def test_build_mapping_reuses_full_generator_functions(
    monkeypatch, tmp_path: Path
) -> None:
    records = [
        SimpleNamespace(table_id="day", variable_entry="tasmax"),
        SimpleNamespace(table_id="day", variable_entry="tasmin"),
    ]
    monkeypatch.setattr(
        mapping_generator.generator, "load_cmor_variables", lambda path: records
    )
    monkeypatch.setattr(
        mapping_generator.generator,
        "branded_name_for_record",
        lambda record: f"mapped_{record.variable_entry}",
    )

    mapping, conflicts = mapping_generator.build_mapping(tmp_path)

    assert mapping == {
        "day.tasmax": "mapped_tasmax",
        "day.tasmin": "mapped_tasmin",
    }
    assert conflicts == {}


def test_compare_mappings_reports_each_difference_category() -> None:
    generated = {
        "day.new": "new_tavg-u-hxy-u",
        "day.changed": "changed_tavg-u-hxy-u",
        "day.same": "same_tavg-u-hxy-u",
    }
    existing = {
        "day.changed": "changed_tpt-u-hxy-u",
        "day.old": "old_tavg-u-hxy-u",
        "day.same": "same_tavg-u-hxy-u",
    }

    new, conflicts, obsolete = mapping_generator.compare_mappings(generated, existing)

    assert new == {"day.new": "new_tavg-u-hxy-u"}
    assert conflicts == {
        "day.changed": {
            "existing": "changed_tpt-u-hxy-u",
            "generated": "changed_tavg-u-hxy-u",
        }
    }
    assert obsolete == {"day.old": "old_tavg-u-hxy-u"}


def test_mapping_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "mapping.toml"
    expected = {
        "day.tasmax": "tas_tmaxavg-h2m-hxy-u",
        "fx.orog": "orog_ti-u-hxy-u",
    }

    mapping_generator.write_mapping(path, expected)

    assert mapping_generator.load_mapping(path) == expected


def test_updated_mapping_preserves_existing_order_and_appends_new_entries(
    tmp_path: Path,
) -> None:
    existing = {
        "mon.b": "b_tavg-u-hxy-u",
        "mon.a": "a_tavg-u-hxy-u",
        "mon.obsolete": "obsolete_tavg-u-hxy-u",
    }
    generated = {
        "day.d": "d_tavg-u-hxy-u",
        "mon.a": "a_tavg-u-hxy-u",
        "mon.b": "b_tavg-u-hxy-u",
        "day.c": "c_tavg-u-hxy-u",
    }

    updated = mapping_generator.order_mapping_for_update(generated, existing)
    output = tmp_path / "mapping.toml"
    mapping_generator.write_mapping(output, updated)
    entry_lines = [
        line for line in output.read_text().splitlines() if line.startswith('"')
    ]

    assert list(updated) == ["mon.b", "mon.a", "day.c", "day.d"]
    assert [line.split('"', 2)[1] for line in entry_lines] == list(updated)


def test_default_paths_use_sibling_repositories(tmp_path: Path) -> None:
    args = SimpleNamespace(
        repos_base_dir=tmp_path,
        cordex_cmip6_cmor_tables_dir=None,
        output_path=None,
    )

    cmor_dir, output_path = mapping_generator.resolve_paths(args)

    assert cmor_dir == (tmp_path / "cordex-cmip6-cmor-tables" / "Tables")
    assert output_path == (
        tmp_path
        / "cc-plugin-wcrp"
        / "plugins"
        / "cordex_cmip6"
        / "config"
        / "wcrp"
        / "mappings"
        / mapping_generator.MAPPING_FILENAME
    )
