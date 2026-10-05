"""Focused regression tests for the CORDEX-CMIP6 variable generator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def load_generator() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "_scripts"
        / "generate_cc6_cv_and_universe_variables_and_known_branded_variables.py"
    )
    spec = importlib.util.spec_from_file_location("generate_cc6_variables", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load generator from {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = load_generator()


def test_unreferenced_formula_terms_are_skipped() -> None:
    report = {"warnings": []}
    selected = generator.select_referenced_formula_entries(
        {
            "a": {"out_name": "a"},
            "a_time1": {"out_name": "a"},
            "a_bnds": {"out_name": "a_bnds"},
            "unused": {"out_name": "unused"},
        },
        {"lev": {"z_factors": ["a"], "z_bounds_factors": ["a_bnds"]}},
        report,
    )

    assert selected == {
        "a": {"out_name": "a"},
        "a_time1": {"out_name": "a"},
        "a_bnds": {"out_name": "a_bnds"},
    }
    assert report["unreferenced_formula_terms"] == ["unused"]
    assert report["warnings"] == [
        (
            "formula_term 'unused' is not referenced by any "
            "model_level_coordinate entry and therefore skipped"
        )
    ]


def test_unreferenced_data_coordinates_are_skipped_by_id_not_out_name() -> None:
    report = {"warnings": []}

    selected = generator.select_referenced_coordinate_entries(
        {
            "time": {"out_name": "time"},
            "timefxc": {"out_name": "time"},
            "depth_coord": {"out_name": "lev"},
        },
        {"time", "depth_coord"},
        report,
    )

    assert set(selected) == {"time", "depth_coord"}
    assert report["unreferenced_data_coordinates"] == ["timefxc"]
    assert "data_coordinate 'timefxc'" in report["warnings"][0]


def test_coordinate_references_include_indirect_dimensions() -> None:
    references = generator.collect_referenced_coordinate_ids(
        [
            generator.CmorVariable(
                "mon",
                "tas",
                {"dimensions": ["longitude", "latitude", "time"]},
            )
        ],
        {"tas": {"dimensions": ["longitude", "latitude", "time"]}},
        {"depth": {"generic_level_name": "depth_coord"}},
        {"a": {"dimensions": "depth_coord"}},
        {"variable_entry": {"bounds": {"dimensions": "vertices latitude"}}},
    )

    assert {
        "depth_coord",
        "latitude",
        "longitude",
        "time",
        "vertices",
    } <= references


def test_resolve_paths_uses_active_qa_mapping(tmp_path: Path) -> None:
    args = SimpleNamespace(
        repos_base_dir=tmp_path,
        cordex_cmip6_cmor_tables_dir=None,
        wcrp_universe_dir=None,
        cordex_cmip6_cv_dir=None,
        branded_variable_mapping_path=None,
        dataset_metadata_path=None,
        known_branded_variable_metadata_dir=None,
    )

    assert generator.resolve_paths(args)["mapping"] == (
        tmp_path / "cc-plugin-wcrp/plugins/cordex_cmip6/config/wcrp/mappings/"
        "frequency_and_variable_id_to_branded_variable.toml"
    )


def test_project_overlay_omits_missing_variable_metadata() -> None:
    payload = generator.build_variable_payload(
        "hus",
        {
            "comment": "",
            "standard_name": "specific_humidity",
            "units": "1",
        },
    )
    universe_payload = {
        **payload,
        "description": "Specific humidity.",
        "long_name": "Specific Humidity",
    }

    generator.validate_payload("variable", payload)
    overlay, differences = generator.project_overlay(payload, universe_payload)

    assert "description" not in overlay
    assert "long_name" not in overlay
    assert "description" not in differences
    assert "long_name" not in differences


def test_derived_variable_root_is_universe_only() -> None:
    records = [
        generator.CmorVariable(
            "3hr",
            "zg300",
            {
                "out_name": "zg300",
                "standard_name": "geopotential_height",
                "units": "m",
                "long_name": "Geopotential Height at 300 hPa",
            },
        )
    ]

    payloads, project_variable_ids = generator.build_variable_payloads(records)

    assert set(payloads) == {"zg", "zg300"}
    assert project_variable_ids == {"zg300"}
    assert payloads["zg"]["drs_name"] == "zg"


def test_find_missing_universe_realm_ids(tmp_path: Path) -> None:
    universe_root = tmp_path / "universe"
    generator.write_json(
        universe_root / "realm" / "atmos.json",
        {"id": "atmos"},
    )

    assert generator.find_missing_universe_realm_ids(
        {"atmos", "river", "unregistered"}, universe_root
    ) == ["river", "unregistered"]


def test_known_branded_universe_payload_omits_optional_empty_values() -> None:
    payload = generator.universe_base_payload(
        {
            "@context": "000_context.jsonld",
            "id": "tas_tavg-h2m-hxy-u",
            "type": "known_branded_variable",
            "description": "",
            "units": None,
            "cell_methods": "",
            "var_def_qualifier": None,
        }
    )

    assert "description" not in payload
    assert "units" not in payload
    assert "cell_methods" not in payload
    assert payload["var_def_qualifier"] is None


@pytest.mark.parametrize(
    ("temporal_label", "expected_time"),
    [
        ("tminavg", "time4"),
        ("tmaxavg", "time4"),
        ("tavgmax", "time5"),
        ("tsumavg", "time6"),
    ],
)
def test_universe_uses_canonical_aggregate_time_coordinate(
    temporal_label: str, expected_time: str
) -> None:
    full_payload = {
        "@context": "000_context.jsonld",
        "id": f"example_{temporal_label}-u-hxy-u",
        "type": "known_branded_variable",
        "temporal_label": temporal_label,
        "dimensions": ["longitude", "latitude", "time"],
    }

    universe_payload = generator.universe_base_payload(full_payload)
    project_payload, _ = generator.project_overlay(full_payload, universe_payload)

    assert universe_payload["dimensions"] == [
        "longitude",
        "latitude",
        expected_time,
    ]
    assert project_payload["dimensions"] == ["longitude", "latitude", "time"]


def test_load_dataset_realms_collects_unique_normalized_values(tmp_path: Path) -> None:
    metadata = tmp_path / "datasets.csv"
    metadata.write_text(
        "out_name,realm\n"
        "tas,atmos\n"
        "tas,atmos\n"
        "od550aer,aerosol\n"
        "od550aer,atmos\n"
        "siconc,seaICE\n",
        encoding="utf-8",
    )

    assert generator.load_dataset_realms(metadata) == {
        "tas": ["atmos"],
        "od550aer": ["aerosol", "atmos"],
        "siconc": ["seaice"],
    }


def test_infer_dataset_realms_uses_every_record_in_group() -> None:
    records = [
        generator.CmorVariable("A", "entry_a", {"out_name": "od550aer"}),
        generator.CmorVariable("B", "entry_b", {"out_name": "tas"}),
    ]

    assert generator.infer_dataset_realms(
        records,
        {"od550aer": ["aerosol", "atmos"], "tas": ["atmos"]},
    ) == ["aerosol", "atmos"]


def test_load_dataset_realms_rejects_missing_columns(tmp_path: Path) -> None:
    metadata = tmp_path / "datasets.csv"
    metadata.write_text("out_name,frequency\ntas,mon\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required column.*realm"):
        generator.load_dataset_realms(metadata)


def test_known_branded_references_use_ids_but_drs_name_keeps_label_case() -> None:
    record = generator.CmorVariable(
        "6hr",
        "zg300",
        {
            "out_name": "zg300",
            "standard_name": "geopotential_height",
            "units": "m",
            "dimensions": "longitude latitude time p300",
        },
    )

    payload = generator.build_known_payload(
        "zg_tpt-300hPa-hxy-u", "zg", [record], ["atmos"]
    )

    assert payload["drs_name"] == "zg_tpt-300hPa-hxy-u"
    assert payload["branding_suffix_name"] == "tpt-300hPa-hxy-u"
    assert payload["vertical_label"] == "300hpa"
    assert payload["out_name"] == "zg"


def test_known_branded_variable_preserves_unique_cell_method_variants() -> None:
    records = [
        generator.CmorVariable(
            "day",
            "example",
            {
                "out_name": "example",
                "standard_name": "example_standard_name",
                "units": "1",
                "dimensions": "longitude latitude time",
                "cell_methods": "area: mean time: mean",
            },
        ),
        generator.CmorVariable(
            "mon",
            "example",
            {
                "out_name": "example",
                "standard_name": "example_standard_name",
                "units": "1",
                "dimensions": "longitude latitude time",
                "cell_methods": "time: mean",
            },
        ),
        generator.CmorVariable(
            "sem",
            "example",
            {
                "out_name": "example",
                "standard_name": "example_standard_name",
                "units": "1",
                "dimensions": "longitude latitude time",
                "cell_methods": "area: mean time: mean",
            },
        ),
    ]

    payload = generator.build_known_payload(
        "example_tavg-u-hxy-u", "example", records, ["atmos"]
    )

    assert payload["cell_methods"] == ["area: mean time: mean", "time: mean"]


@pytest.mark.parametrize(
    ("table_id", "cell_methods", "dimensions", "expected"),
    [
        (
            "3hr",
            "area: mean time: point",
            "longitude latitude time1 p300",
            "zg_tpt-300hPa-hxy-u",
        ),
        (
            "6hr",
            "area: mean time: point",
            "longitude latitude time1 p300",
            "zg_tpt-300hPa-hxy-u",
        ),
        (
            "day",
            "area: time: mean",
            "longitude latitude time p300",
            "zg_tavg-300hPa-hxy-u",
        ),
        (
            "mon",
            "area: time: mean",
            "longitude latitude time p300",
            "zg_tavg-300hPa-hxy-u",
        ),
    ],
)
def test_zg300_mapping_uses_canonical_zg_root(
    table_id: str, cell_methods: str, dimensions: str, expected: str
) -> None:
    record = generator.CmorVariable(
        table_id,
        "zg300",
        {
            "out_name": "zg300",
            "cell_methods": cell_methods,
            "dimensions": dimensions,
        },
    )

    assert generator.branded_name_for_record(record) == expected


def test_within_days_statistics_keep_cordex_time_coordinate() -> None:
    entry = {
        "dimensions": "longitude latitude time height2m",
        "cell_methods": "time: minimum within days time: mean over days",
    }

    assert generator.canonical_branded_dimensions(entry) == [
        "longitude",
        "latitude",
        "time",
        "height2m",
    ]


def test_legacy_ice_sheet_axes_use_cmip7_coordinate_ids() -> None:
    assert generator.canonical_branded_dimensions({"dimensions": "xant yant time"}) == [
        "longitude",
        "latitude",
        "time",
    ]
