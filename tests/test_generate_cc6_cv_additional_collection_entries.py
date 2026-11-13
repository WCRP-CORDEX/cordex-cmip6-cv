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


def test_license_context_upgrades_previous_generator_mapping(
    tmp_path: Path,
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    context_path = tmp_path / spec.collection_id / "000_context.jsonld"
    write_json(
        context_path,
        {
            "@context": {
                "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
                "id": "@id",
                "type": "@type",
                "license": "http://schema.org/license",
            }
        },
    )

    generator.augment_context(
        tmp_path / spec.collection_id,
        spec,
        dry_run=False,
    )

    context = generator.read_json(context_path)["@context"]
    assert context["license"] == {
        "@id": "http://schema.org/license",
        "@type": "@json",
    }


def test_custom_properties_upgrade_previous_schema_org_mappings(
    tmp_path: Path,
) -> None:
    spec = generator.COLLECTION_SPECS[0]
    context_path = tmp_path / spec.collection_id / "000_context.jsonld"
    write_json(
        context_path,
        {
            "@context": {
                "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
                "id": "@id",
                "type": "@type",
                "source_type": "http://schema.org/source_type",
                "activity_participation": (
                    "http://schema.org/activity_participation"
                ),
            }
        },
    )

    generator.augment_context(
        tmp_path / spec.collection_id,
        spec,
        dry_run=False,
    )

    context = generator.read_json(context_path)["@context"]
    assert context["source_type"] == f"{generator.PROPERTY_BASE}/source_type"
    assert context["activity_participation"] == (
        f"{generator.PROPERTY_BASE}/activity_participation"
    )


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
        path.stem
        for path in (repository_root / "driving_experiment_id").glob("*.json")
    }

    for path in (repository_root / "driving_source_id").glob("*.json"):
        payload = generator.read_json(path)
        if "driving_experiment_id" not in payload:
            continue

        restrictions = payload["driving_experiment_id"]
        assert isinstance(restrictions, list), (
            f"{path}: driving_experiment_id must be a list"
        )
        assert restrictions, (
            f"{path}: omit driving_experiment_id instead of defining an empty list"
        )
        assert all(
            isinstance(restriction, str) and restriction.strip()
            for restriction in restrictions
        ), f"{path}: driving_experiment_id must contain non-empty strings"
        assert len(restrictions) == len(set(restrictions)), (
            f"{path}: driving_experiment_id contains duplicate values"
        )
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
