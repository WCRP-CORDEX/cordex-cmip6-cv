import json
import pprint
from .common import table_prefix

filelist = [
    f"{table_prefix}_required_global_attributes.json",
    f"{table_prefix}_activity_id.json",
    f"{table_prefix}_project_id.json",
    f"{table_prefix}_domain_id.json",
    # f"{table_prefix}_domain.json",
    f"{table_prefix}_institution_id.json",
    f"{table_prefix}_driving_source_id.json",
    f"{table_prefix}_source_id.json",
    f"{table_prefix}_source_type.json",
    f"{table_prefix}_frequency.json",
    f"{table_prefix}_native_resolution.json",
    f"{table_prefix}_realm.json",
    f"{table_prefix}_license.json",
    f"{table_prefix}_DRS.json",
    f"{table_prefix}_driving_experiment_id.json",
    "mip_era.json",
]


def create_cv_statics():
    cv_statics = {
        "mip_era": ["CMIP6"],
        "product": ["model-output"],
        "tracking_id": [
            "hdl:21.14103/.*"
        ],  # see https://github.com/WCRP-CORDEX/cordex-cmip6-cv/issues/51
        "variant_label": [
            "r[[:digit:]]\\{1,\\}i[[:digit:]]\\{1,\\}p[[:digit:]]\\{1,\\}f[[:digit:]]\\{1,\\}$"
        ],
        "Conventions": ["CF-1.8", "CF-1.10", "CF-1.11"],
    }
    return cv_statics


def read_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def write_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def read_tables():
    tables = {}
    for f in filelist:
        table = read_json(f)
        key = list(table.keys())[0]
        tables[key] = table.get(key)
    return tables


def create_cv(filename=None):
    if filename is None:
        filename = f"{table_prefix}_CV.json"

    cv_tables = read_tables()
    cv_statics = create_cv_statics()

    cv = {"CV": cv_tables | cv_statics}

    write_json(filename, cv)


def update_table(entry, filename, table_name):
    with open(filename, "r", encoding="utf8") as f:
        current = json.load(f)
    new_id = entry[table_name]
    if new_id not in current[table_name]:
        current[table_name][new_id] = entry
    else:
        print(
            f"'{new_id}' already in table with value: '{current[table_name][new_id]}'"
        )
        raise Exception
    pprint.pprint(current)
    with open(filename, "w", encoding="utf8") as f:
        json.dump(current, f, indent=4)
