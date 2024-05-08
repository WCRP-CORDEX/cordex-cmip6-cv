import json
from os import path as op
import pytest
from cordex_cv import update_table


table_dir = op.dirname(op.dirname(op.dirname(op.abspath(__file__))))


def test_update_table():

    text = '{"institution_id": "GERICS", "institution": "Climate Service Center"}'
    entry = json.loads(text)
    table_file = op.join(table_dir, "CORDEX-CMIP6_institution_id.json")
    with pytest.raises(Exception):
        update_table(entry, table_file, "institution_id")

    text = '{"institution_id": "INSTITUTE", "institution": "My institute"}'
    entry = json.loads(text)
    update_table(entry, table_file, "institution_id", sort=True)

    text = (
        '{"activity_participation": ["DD"], "cohort": '
        '["Registered"], "further_info_url": "https://www.remo-rcm.de", '
        '"institution_id": ["GERICS"], "label": "REMO2020", "label_extended": "REMO '
        'regional model 2020", "license": "Creative Commons Attribution 4.0 '
        "International License (CC BY 4.0; "
        'https://creativecommons.org/licenses/by/4.0/).", "release_year": "2022", '
        '"source_id": "REMO2020", "source_type": "ARCM"}'
    )
    table_file = op.join(table_dir, "CORDEX-CMIP6_source_id.json")
    entry = json.loads(text)
    with pytest.raises(Exception):
        update_table(entry, table_file, "source_id")

    text = (
        '{"activity_participation": ["DD"], "cohort": '
        '["Registered"], "further_info_url": "https://www.remo-rcm.de", '
        '"institution_id": ["GERICS"], "label": "REMO2020", "label_extended": "REMO '
        'regional model 2020", "license": "Creative Commons Attribution 4.0 '
        "International License (CC BY 4.0; "
        'https://creativecommons.org/licenses/by/4.0/).", "release_year": "2022", '
        '"source_id": "SUPERMODEL", "source_type": "ARCM"}'
    )
    entry = json.loads(text)
    update_table(entry, table_file, "source_id", sort=True)
