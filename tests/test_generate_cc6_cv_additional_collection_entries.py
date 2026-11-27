"""Regression tests for the CORDEX-CMIP6 additional collection generator."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pyld import jsonld


def load_generator() -> ModuleType:
    """Load the repository script, with an override for transitional checkouts."""
    repository_root = Path(__file__).resolve().parents[1]
    default_path = (
        repository_root
        / "_scripts"
        / "generate_cc6_cv_additional_collection_entries.py"
    )
    generator_path = Path(
        os.environ.get("CC6_ADDITIONAL_GENERATOR_PATH", default_path)
    ).resolve()
    if not generator_path.is_file():
        raise FileNotFoundError(
            f"CORDEX-CMIP6 additional collection generator not found: {generator_path}"
        )

    spec = importlib.util.spec_from_file_location(
        "generate_cc6_cv_additional_collection_entries",
        generator_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load generator from {generator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = load_generator()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")


def test_load_conventional_cv_reproduces_combined_cv_transformations(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "CORDEX-CMIP6_source_id.json",
        {
            "source_id": {
                "Model-A": {
                    "label_extended": "Model A regional climate model",
                    "release_year": "2026",
                    "source_type": "ARCM",
                    "activity_participation": ["DD"],
                    "license": "Registration-form license text",
                }
            }
        },
    )
    write_json(
        tmp_path / "CORDEX-CMIP6_license.json",
        {"license": [generator.CORDEX_CMIP6_LICENSE]},
    )
    write_json(
        tmp_path / "CORDEX-CMIP6_driving_source_id.json",
        {
            "driving_source_id": {
                "ERA5": {
                    "driving_source": "ECMWF Reanalysis v5",
                    "driving_experiment_id": ["evaluation"],
                }
            }
        },
    )
    write_json(
        tmp_path / "CORDEX-CMIP6_institution_id.json",
        {"institution_id": {"Institute-A": "Institute A description"}},
    )
    write_json(
        tmp_path / "CORDEX-CMIP6_domain_id.json",
        {
            "domain_id": {
                "CEUX-3": {
                    "domain": "Central Europe Extended",
                    "domain_id": "CEUX-3",
                }
            }
        },
    )
    write_json(
        tmp_path / "CORDEX-CMIP6_driving_experiment_id.json",
        {
            "driving_experiment_id": {
                "evaluation": "reanalysis simulation of the recent past"
            }
        },
    )

    cv = generator.load_conventional_cv(tmp_path)

    assert cv["source_id"]["Model-A"] == {
        "source": [
            "Model A regional climate model (2026)",
            "Model A regional climate model",
        ],
        "source_type": "ARCM",
        "activity_participation": ["DD"],
        "license": generator.CORDEX_CMIP6_LICENSE,
    }
    assert cv["driving_source_id"]["ERA5"]["driving_experiment_id"] == ["evaluation"]
    assert cv["driving_experiment_id"]["evaluation"] == {
        "driving_experiment_id": "evaluation",
        "driving_experiment": "reanalysis simulation of the recent past",
    }


@pytest.mark.parametrize(
    ("spec", "identifier", "raw_entry", "expected_fields"),
    (
        (
            generator.COLLECTION_SPECS[0],
            "Model-A",
            {
                "source": ["Model A description", "Alternate description"],
                "source_type": "ARCM",
                "activity_participation": ["DD"],
                "license": generator.CORDEX_CMIP6_LICENSE,
            },
            {
                "source": ["Model A description", "Alternate description"],
                "source_type": "ARCM",
                "activity_participation": ["DD"],
                "license": {
                    "id": generator.CORDEX_CMIP6_LICENSE_ID,
                    "exceptions-contact": None,
                    "source-specific-info": "",
                },
            },
        ),
        (
            generator.COLLECTION_SPECS[1],
            "Model-B",
            {"driving_source": "Model B description"},
            {"driving_source": "Model B description"},
        ),
        (
            generator.COLLECTION_SPECS[2],
            "Institute-A",
            "Institute A description",
            {"institution": "Institute A description"},
        ),
        (
            generator.COLLECTION_SPECS[3],
            "CEUX-3",
            {
                "domain": "Central Europe Extended",
                "domain_id": "CEUX-3",
            },
            {"description": "Central Europe Extended"},
        ),
        (
            generator.COLLECTION_SPECS[4],
            "historical",
            {
                "driving_experiment": "all-forcing simulation of the recent past",
                "driving_experiment_id": "historical",
            },
            {"experiment": "all-forcing simulation of the recent past"},
        ),
    ),
)
def test_generation_augments_context_and_preserves_existing_metadata(
    tmp_path: Path,
    spec: Any,
    identifier: str,
    raw_entry: Any,
    expected_fields: dict[str, Any],
) -> None:
    project_root = tmp_path / "project"
    output_dir = project_root / spec.collection_id
    context_path = output_dir / "000_context.jsonld"
    output_path = output_dir / f"{identifier.lower()}.json"
    context_marker = "https://example.org/retained"
    write_json(
        context_path,
        {
            "@context": {
                "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
                "id": "@id",
                "type": "@type",
                "retained": context_marker,
            },
            "retained_top_level": True,
        },
    )
    write_json(
        output_path,
        {
            "@context": "000_context.jsonld",
            "id": identifier.lower(),
            "type": spec.term_type,
            "retained": "metadata",
        },
    )

    counts = generator.generate_collection(
        {spec.collection_id: {identifier: raw_entry}},
        project_root,
        spec,
        dry_run=False,
    )

    assert counts == {"created": 0, "updated": 1, "unchanged": 0}
    context_payload = generator.read_json(context_path)
    output_payload = generator.read_json(output_path)
    assert context_payload["retained_top_level"] is True
    assert context_payload["@context"]["retained"] == context_marker
    assert output_payload["retained"] == "metadata"
    for field, expected_value in expected_fields.items():
        assert output_payload[field] == expected_value

    expanded_input = dict(output_payload)
    expanded_input["@context"] = context_payload["@context"]
    expanded = jsonld.expand(expanded_input)[0]
    for field in spec.fields:
        if field.output_field in expected_fields:
            assert field.property_iri in expanded
            if field.json_literal:
                expanded_value = expanded[field.property_iri][0]
                assert expanded_value["@type"] == "@json"
                assert expanded_value["@value"] == expected_fields[field.output_field]

    second_counts = generator.generate_collection(
        {spec.collection_id: {identifier: raw_entry}},
        project_root,
        spec,
        dry_run=False,
    )
    assert second_counts == {"created": 0, "updated": 0, "unchanged": 1}


def test_conflicting_context_mapping_is_not_overwritten(tmp_path: Path) -> None:
    spec = generator.COLLECTION_SPECS[2]
    output_field = spec.fields[0].output_field
    context_path = tmp_path / spec.collection_id / "000_context.jsonld"
    original = {
        "@context": {
            "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
            "id": "@id",
            "type": "@type",
            output_field: "https://example.org/conflicting-property",
        }
    }
    write_json(context_path, original)

    with pytest.raises(ValueError, match="Refusing to overwrite context term"):
        generator.augment_context(tmp_path / spec.collection_id, spec, dry_run=False)

    assert generator.read_json(context_path) == original


def _source_project(tmp_path: Path, existing_fields: dict[str, Any]) -> Path:
    """Project with one source_id term and a context without generated fields."""
    project_root = tmp_path / "project"
    write_json(
        project_root / "source_id" / "000_context.jsonld",
        {
            "@context": {
                "@base": f"{generator.UNIVERSE_BASE}/source/",
                "id": "@id",
                "type": "@type",
                "source": f"{generator.UNIVERSE_BASE}/source",
            }
        },
    )
    write_json(
        project_root / "source_id" / "model.json",
        {
            "@context": "000_context.jsonld",
            "id": "model",
            "type": "source",
            **existing_fields,
        },
    )
    return project_root


SOURCE_ENTRY = {
    "source": ["Model description"],
    "source_type": "ARCM",
    "activity_participation": ["DD"],
    "license": generator.CORDEX_CMIP6_LICENSE,
}


@pytest.mark.parametrize(
    ("universe_participation", "existing_fields", "expected"),
    (
        # Universe equals CORDEX-CMIP6 -> no project override
        (["DD"], {}, None),
        # Universe gets DD appended, but also lists CMIP -> project override
        (["CMIP"], {}, ["DD"]),
        # Identical copies already in the project are kept
        (["DD"], {"activity_participation": ["DD"]}, ["DD"]),
        # Outdated project copies are corrected
        (["DD"], {"activity_participation": ["DD", "ESD"]}, ["DD"]),
    ),
)
def test_shared_fields_are_only_written_when_they_differ_from_universe(
    tmp_path: Path,
    universe_participation: list[str],
    existing_fields: dict[str, Any],
    expected: list[str] | None,
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    universe_root = tmp_path / "universe"
    write_json(
        universe_root / "source" / "model.json",
        {"id": "model", "activity_participation": universe_participation},
    )
    project_root = _source_project(tmp_path, existing_fields)

    generator.generate_collection(
        {spec.collection_id: {"Model": SOURCE_ENTRY}},
        project_root,
        spec,
        dry_run=False,
        universe_root=universe_root,
    )

    payload = generator.read_json(project_root / "source_id" / "model.json")
    assert payload.get("activity_participation") == expected
    assert payload["source_type"] == "ARCM"


def test_missing_universe_term_is_assumed_to_get_the_cordex_value(
    tmp_path: Path,
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    universe_root = tmp_path / "universe"
    (universe_root / "source").mkdir(parents=True)
    project_root = _source_project(tmp_path, {})

    generator.generate_collection(
        {spec.collection_id: {"Model": SOURCE_ENTRY}},
        project_root,
        spec,
        dry_run=False,
        universe_root=universe_root,
    )

    payload = generator.read_json(project_root / "source_id" / "model.json")
    assert "activity_participation" not in payload


def test_universe_only_activities_are_reported_not_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    universe_root = tmp_path / "universe"
    universe_term = universe_root / "source" / "model.json"
    write_json(universe_term, {"id": "model", "activity_participation": ["CMIP", "DD"]})
    project_root = _source_project(tmp_path, {})

    generator.generate_collection(
        {spec.collection_id: {"Model": SOURCE_ENTRY}},
        project_root,
        spec,
        dry_run=False,
        universe_root=universe_root,
    )

    assert (
        "NOTICE: source/model: Universe activity_participation also lists ['CMIP']"
        in (capsys.readouterr().out)
    )
    assert generator.read_json(universe_term)["activity_participation"] == [
        "CMIP",
        "DD",
    ]


def test_context_gets_only_present_fields_in_alphabetical_order(
    tmp_path: Path,
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    universe_root = tmp_path / "universe"
    write_json(
        universe_root / "source" / "model.json",
        {"id": "model", "activity_participation": ["DD"]},
    )
    project_root = _source_project(tmp_path, {})

    generator.generate_collection(
        {spec.collection_id: {"Model": SOURCE_ENTRY}},
        project_root,
        spec,
        dry_run=False,
        universe_root=universe_root,
    )

    context = generator.read_json(project_root / "source_id" / "000_context.jsonld")
    assert list(context["@context"]) == [
        "@base",
        "id",
        "type",
        "source",
        "license",
        "source_type",
    ]


def test_dry_run_does_not_modify_context_or_entries(tmp_path: Path) -> None:
    spec = generator.COLLECTION_SPECS[1]
    project_root = tmp_path / "project"
    output_dir = project_root / spec.collection_id
    context_path = output_dir / "000_context.jsonld"
    output_path = output_dir / "model.json"
    write_json(
        context_path,
        {
            "@context": {
                "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
                "id": "@id",
                "type": "@type",
            }
        },
    )
    write_json(
        output_path,
        {
            "@context": "000_context.jsonld",
            "id": "model",
            "type": spec.term_type,
        },
    )
    original_context = context_path.read_bytes()
    original_entry = output_path.read_bytes()

    counts = generator.generate_collection(
        {spec.collection_id: {"Model": {"driving_source": "Description"}}},
        project_root,
        spec,
        dry_run=True,
    )

    assert counts == {"created": 0, "updated": 1, "unchanged": 0}
    assert context_path.read_bytes() == original_context
    assert output_path.read_bytes() == original_entry


def test_conflicting_entry_identity_is_not_overwritten(tmp_path: Path) -> None:
    spec = generator.COLLECTION_SPECS[2]
    output_path = tmp_path / "institute.json"
    existing = {
        "@context": "000_context.jsonld",
        "id": "different-id",
        "type": spec.term_type,
    }

    with pytest.raises(ValueError, match="identity field 'id'"):
        generator.merge_payload(
            existing,
            generator.build_payload("Institute", "Description", spec),
            spec,
            output_path,
        )

    assert existing["id"] == "different-id"


def test_driving_experiment_restriction_is_generated(tmp_path: Path) -> None:
    spec = generator.COLLECTION_SPECS[1]
    payload = generator.build_payload(
        "ERA5",
        {
            "driving_source": "ECMWF Reanalysis v5",
            "driving_experiment_id": ["evaluation"],
        },
        spec,
    )

    assert payload["driving_experiment_id"] == ["evaluation"]


def test_absent_driving_experiment_restriction_removes_stale_value() -> None:
    spec = generator.COLLECTION_SPECS[1]
    existing = {
        "@context": "000_context.jsonld",
        "id": "model",
        "type": "source",
        "driving_source": "Old description",
        "driving_experiment_id": ["evaluation"],
        "retained": "metadata",
    }
    generated = generator.build_payload(
        "Model",
        {"driving_source": "Current description"},
        spec,
    )

    merged = generator.merge_payload(
        existing,
        generated,
        spec,
        Path("driving_source_id/model.json"),
    )

    assert "driving_experiment_id" not in merged
    assert merged["driving_source"] == "Current description"
    assert merged["retained"] == "metadata"


def test_empty_driving_experiment_restriction_is_rejected() -> None:
    spec = generator.COLLECTION_SPECS[1]

    with pytest.raises(ValueError, match="Expected a non-empty list"):
        generator.build_payload(
            "ERA5",
            {
                "driving_source": "ECMWF Reanalysis v5",
                "driving_experiment_id": [],
            },
            spec,
        )


def test_checked_in_driving_experiment_restrictions_are_valid() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    known_experiments = {
        path.stem for path in (repository_root / "driving_experiment_id").glob("*.json")
    }

    for path in (repository_root / "driving_source_id").glob("*.json"):
        payload = generator.read_json(path)
        if "driving_experiment_id" not in payload:
            continue

        restrictions = payload["driving_experiment_id"]
        assert isinstance(
            restrictions, list
        ), f"{path}: driving_experiment_id must be a list"
        assert (
            restrictions
        ), f"{path}: omit driving_experiment_id instead of defining an empty list"
        assert all(
            isinstance(restriction, str) and restriction.strip()
            for restriction in restrictions
        ), f"{path}: driving_experiment_id must contain non-empty strings"
        assert len(restrictions) == len(
            set(restrictions)
        ), f"{path}: driving_experiment_id contains duplicate values"
        assert set(restrictions) <= known_experiments, (
            f"{path}: unresolved driving_experiment_id value(s): "
            f"{sorted(set(restrictions) - known_experiments)}"
        )


def test_unknown_source_license_is_rejected() -> None:
    spec = generator.COLLECTION_SPECS[0]

    with pytest.raises(ValueError, match="Add a project license term"):
        generator.build_payload(
            "Model",
            {
                "source": "Model description",
                "source_type": "ARCM",
                "activity_participation": ["DD"],
                "license": "https://example.org/unregistered-license",
            },
            spec,
        )
