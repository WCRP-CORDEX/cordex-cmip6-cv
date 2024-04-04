import json
import pprint


def update_table(entry, filename, table_name):
    with open(filename, "r", encoding="utf8") as f:
        current = json.load(f)
    new_id = entry[table_name]
    if new_id not in current[table_name]:
        current[table_name][new_id] = entry
    else:
        print(f"'{new_id}' already in table with value: '{current[table_name][new_id]}'")
        raise Exception
    pprint.pprint(current)
    with open(filename, "w", encoding="utf8") as f:
        json.dump(current, f, indent=4)
