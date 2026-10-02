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
    ("spec", "identifier", "raw_entry", "expected_value"),
    (
        (
            generator.COLLECTION_SPECS[0],
            "Model-A",
            {"source": ["Model A description", "Alternate description"]},
            ["Model A description", "Alternate description"],
        ),
        (
            generator.COLLECTION_SPECS[1],
            "Model-B",
            {"driving_source": "Model B description"},
            "Model B description",
        ),
        (
            generator.COLLECTION_SPECS[2],
            "Institute-A",
            "Institute A description",
            "Institute A description",
        ),
    ),
)
def test_generation_augments_context_and_preserves_existing_metadata(
    tmp_path: Path,
    spec: Any,
    identifier: str,
    raw_entry: Any,
    expected_value: str | list[str],
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
    assert output_payload[spec.output_field] == expected_value

    expanded_input = dict(output_payload)
    expanded_input["@context"] = context_payload["@context"]
    expanded = jsonld.expand(expanded_input)[0]
    assert spec.property_iri in expanded

    second_counts = generator.generate_collection(
        {spec.collection_id: {identifier: raw_entry}},
        project_root,
        spec,
        dry_run=False,
    )
    assert second_counts == {"created": 0, "updated": 0, "unchanged": 1}


def test_conflicting_context_mapping_is_not_overwritten(tmp_path: Path) -> None:
    spec = generator.COLLECTION_SPECS[2]
    context_path = tmp_path / spec.collection_id / "000_context.jsonld"
    original = {
        "@context": {
            "@base": f"{generator.UNIVERSE_BASE}/{spec.term_type}/",
            "id": "@id",
            "type": "@type",
            spec.output_field: "https://example.org/conflicting-property",
        }
    }
    write_json(context_path, original)

    with pytest.raises(ValueError, match="Refusing to overwrite context term"):
        generator.augment_context(tmp_path / spec.collection_id, spec, dry_run=False)

    assert generator.read_json(context_path) == original


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
