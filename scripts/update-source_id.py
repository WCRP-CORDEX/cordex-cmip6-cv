import json
import sys
from collections import OrderedDict
from cordex_cv import update_table

table = "CORDEX-CMIP6_source_id.json"
table_name = "source_id"


licenses = {
    "CC BY 4.0": "Creative Commons Attribution 4.0 International License (CC BY 4.0; https://creativecommons.org/licenses/by/4.0).",
    "CC0": "Creative Commons 1.0 Universal (CC0; https://creativecommons.org/publicdomain/zero/1.0).",
}


def update_source_id(entry):
    entry["license"] = licenses[entry["license"]]
    # entry["institution_id"] = [entry["institution_id"]]
    entry["cohort"] = ["Registered"]
    sorted_entry = OrderedDict(sorted(entry.items()))
    return update_table(sorted_entry, table, table_name)


def get_entries(content):
    return json.loads(content)


if __name__ == "__main__":
    content = sys.argv[1]
    # content = (
    #    '{"activity_participation": ["DD"], "cohort": '
    #    '["Registered"], "further_info_url": "https://www.remo-rcm.de", '
    #    '"institution_id": ["GERICS"], "label": "REMO2020", "label_extended": "REMO '
    #    'regional model 2020", "license": "CC BY 4.0", '
    #    '"source_id": "SUPER-RCM", "source_type": "ARCM"}'
    # )
    # content = (
    #    '{"activity_participation": ["DD"], "cohort": '
    #    '["Registered"], "further_info_url": "https://www.remo-rcm.de", '
    #    '"institution_id": ["GERICS"], "label": "REMO2020", "label_extended": "REMO '
    #    'regional model 2020", "license": "Creative Commons Attribution 4.0 '
    #    "International License (CC BY 4.0; "
    #    'https://creativecommons.org/licenses/by/4.0/).", "release_year": "2022", '
    #    '"source_id": "SUPER-RCM", "source_type": "ARCM"}'
    # )
    entry = get_entries(content)
    new_id = update_source_id(entry)
    print(new_id)
