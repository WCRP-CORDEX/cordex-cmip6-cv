import json
from .common import sort_dict, table_prefix, read_json, write_json

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
    f"{table_prefix}_DRS.json",
    f"{table_prefix}_driving_experiment_id.json",
    f"{table_prefix}_fixed.json",
]


def process_source_id(entry, license):
    source = [
        f"{entry['label_extended']} ({entry['release_year']})",
        entry["label_extended"],
    ]
    entry["source"] = source
    entry["license"] = license
    del entry["label_extended"]
    del entry["release_year"]
    del entry["further_info_url"]
    return entry


def process_driving_experiment_id(expid, value):
    return {
        "driving_experiment_id": expid,
        "driving_experiment": value,
    }


def read_tables():
    table = {}
    for f in filelist:
        print(f"reading: {f}")
        table = table | read_json(f)
        # key = list(table.keys())[0]
        # tables[key] = table.get(key)
    return table


def create_cv(filename=None):
    if filename is None:
        filename = f"{table_prefix}_CV.json"

    cv_table = read_tables()
    cv_table["source_id"] = {
        k: process_source_id(v, license=cv_table["license"][0])
        for k, v in cv_table["source_id"].items()
    }
    cv_table["driving_experiment_id"] = {
        k: process_driving_experiment_id(k, v)
        for k, v in cv_table["driving_experiment_id"].items()
    }

    cv = {"CV": cv_table}

    print(f"writing: {filename}")
    write_json(filename, cv)


def update_table(entry, filename, table_name, style=None, sort=False):
    with open(filename, "r", encoding="utf8") as f:
        current = json.load(f)
    new_id = entry[table_name]
    if new_id not in current[table_name]:
        if style == "flat":
            current[table_name][new_id] = entry[table_name.replace("_id", "")]
        else:
            current[table_name][new_id] = entry
    else:
        print(
            f"'{new_id}' already in table with value: '{current[table_name][new_id]}'"
        )
        raise Exception

    if sort is True:
        current[table_name] = sort_dict(current[table_name])

    with open(filename, "w", encoding="utf8") as f:
        json.dump(current, f, indent=4)
    return new_id
