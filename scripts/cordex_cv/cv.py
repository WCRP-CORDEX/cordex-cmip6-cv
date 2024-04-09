import json
import pprint
from .common import table_prefix, read_json, write_json

filelist = [
    f"{table_prefix}_required_global_attributes.json",
    f"{table_prefix}_activity_id.json",
    f"{table_prefix}_project_id.json",
    f"{table_prefix}_domain_id.json",
    f"{table_prefix}_institution_id.json",
    f"{table_prefix}_driving_source_id.json",
    f"{table_prefix}_source_id.json",
    f"{table_prefix}_source_type.json",
    f"{table_prefix}_frequency.json",
    f"{table_prefix}_native_resolution.json",
    f"{table_prefix}_DRS.json",
    f"{table_prefix}_driving_experiment_id.json",
    f"{table_prefix}_fixed.json",
]


def process_source_id(entry):
    source = f"{entry['label_extended']} ({entry['release_year']})"
    entry["source"] = source
    del entry["label_extended"]
    del entry["release_year"]
    return entry


def process_driving_experiment_id(expid, value):
    return {
        "driving_experiment_id": expid,
        "driving_experiment": value,
    }


def read_tables():
    tables = {}
    for f in filelist:
        print(f"reading: {f}")
        table = read_json(f)
        key = list(table.keys())[0]
        tables[key] = table.get(key)
    return tables


def create_cv(filename=None):
    if filename is None:
        filename = f"{table_prefix}_CV.json"

    cv_tables = read_tables()
    cv_tables["source_id"] = {
        k: process_source_id(v) for k, v in cv_tables["source_id"].items()
    }
    cv_tables["driving_experiment_id"] = {
        k: process_driving_experiment_id(k, v)
        for k, v in cv_tables["driving_experiment_id"].items()
    }

    cv_fixed = cv_tables["fixed"]

    cv = {"CV": cv_tables | cv_fixed}

    print(f"writing: {filename}")
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