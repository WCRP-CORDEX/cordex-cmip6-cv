import json
import pytest
from .tools import update_table


def test_update_table():

    text = '{"institution_id": "GERICS", "institution": "Climate Service Center"}'
    entry = json.loads(text)
    with pytest.raises(Exception) as e_info:
        update_table(entry, "CORDEX-CMIP6_institution_id.json", "institution_id")
    
    text = '{"institution_id": "INSTITUTE", "institution": "My institute"}'
    entry = json.loads(text)
    update_table(entry, "CORDEX-CMIP6_institution_id.json", "institution_id")

    text = (
        '{"activity_participation": ["DD"], "cohort": '
        '["Registered"], "further_info_url": "https://www.remo-rcm.de", '
        '"institution_id": ["GERICS"], "label": "REMO2020", "label_extended": "REMO '
        'regional model 2020", "license": "Creative Commons Attribution 4.0 '
        "International License (CC BY 4.0; "
        'https://creativecommons.org/licenses/by/4.0/).", "release_year": "2022", '
        '"source_id": "REMO2020", "source_type": "ARCM"}'
    )
    entry = json.loads(text)
    with pytest.raises(Exception) as e_info:
        update_table(entry, "CORDEX-CMIP6_source_id.json", "source_id")
    
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
    update_table(entry, "CORDEX-CMIP6_source_id.json", "source_id")
