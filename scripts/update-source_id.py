import json
import sys
from cordex_cv import update_table

print("Number of arguments:", len(sys.argv), "arguments")
print("Argument List:", str(sys.argv))


table = "CORDEX-CMIP6_source_id.json"
table_name = "source_id"


def update_source_id(entry):
    return update_table(entry, table, table_name)


def get_entries(content):
    return json.loads(content)


if __name__ == "__main__":
    content = sys.argv[1]
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
