"""Tests for DRS template transformation for CMOR 3.12+ compatibility."""
import json
import os
from os import path as op
import pytest
from cordex_cv import create_cv


table_dir = op.dirname(op.dirname(op.dirname(op.abspath(__file__))))


@pytest.fixture
def change_to_table_dir(monkeypatch):
    """Fixture to change to the table directory for test execution."""
    monkeypatch.chdir(table_dir)


@pytest.fixture
def generated_cv(change_to_table_dir):
    """Fixture to generate the CV file and return its contents."""
    cv_file = op.join(table_dir, "CORDEX-CMIP6_CV.json")
    create_cv(cv_file)
    with open(cv_file, "r", encoding="utf8") as f:
        return json.load(f)


def test_drs_transformation(generated_cv):
    """Test that DRS templates are transformed correctly for CMOR 3.12+."""
    cv = generated_cv
    
    # Verify DRS section exists
    assert "CV" in cv
    assert "DRS" in cv["CV"]
    
    drs = cv["CV"]["DRS"]
    
    # Check directory_path_template
    assert "directory_path_template" in drs
    dir_template = drs["directory_path_template"]
    
    # Should not contain forward slashes (separators removed)
    assert "/" not in dir_template, "Directory template should not contain separators"
    
    # Should contain all expected placeholders
    expected_dir_placeholders = [
        "<project_id>", "<activity_id>", "<domain_id>", "<institution_id>",
        "<driving_source_id>", "<driving_experiment_id>", "<driving_variant_label>",
        "<source_id>", "<version_realization>", "<frequency>", "<variable_id>", "<version>"
    ]
    for placeholder in expected_dir_placeholders:
        assert placeholder in dir_template, f"Missing {placeholder} in directory template"
    
    # Check filename_template
    assert "filename_template" in drs
    file_template = drs["filename_template"]
    
    # Should not contain underscores BETWEEN placeholders (but underscores within placeholders are ok)
    # Check for pattern >_< which indicates a separator between placeholders
    assert ">_<" not in file_template, "Filename template should not contain underscore separators between placeholders"
    
    # Should not contain [_<time_range>] (CMOR adds this)
    assert "[_<time_range>]" not in file_template, "Filename template should not contain [_<time_range>]"
    assert "<time_range>" not in file_template, "Filename template should not contain <time_range>"
    
    # Should not contain .nc extension (CMOR adds this)
    assert ".nc" not in file_template, "Filename template should not contain .nc extension"
    
    # Should contain all expected placeholders
    expected_file_placeholders = [
        "<variable_id>", "<domain_id>", "<driving_source_id>",
        "<driving_experiment_id>", "<driving_variant_label>", "<institution_id>",
        "<source_id>", "<version_realization>", "<frequency>"
    ]
    for placeholder in expected_file_placeholders:
        assert placeholder in file_template, f"Missing {placeholder} in filename template"


def test_drs_expected_format(generated_cv):
    """Test that DRS templates match the expected CMOR 3.12 format."""
    cv = generated_cv
    drs = cv["CV"]["DRS"]
    
    # Expected templates according to the issue
    expected_dir_template = (
        "<project_id><activity_id><domain_id><institution_id>"
        "<driving_source_id><driving_experiment_id><driving_variant_label>"
        "<source_id><version_realization><frequency><variable_id><version>"
    )
    
    expected_file_template = (
        "<variable_id><domain_id><driving_source_id><driving_experiment_id>"
        "<driving_variant_label><institution_id><source_id><version_realization>"
        "<frequency>"
    )
    
    assert drs["directory_path_template"] == expected_dir_template, (
        f"Directory template mismatch.\nExpected: {expected_dir_template}\n"
        f"Got: {drs['directory_path_template']}"
    )
    
    assert drs["filename_template"] == expected_file_template, (
        f"Filename template mismatch.\nExpected: {expected_file_template}\n"
        f"Got: {drs['filename_template']}"
    )
