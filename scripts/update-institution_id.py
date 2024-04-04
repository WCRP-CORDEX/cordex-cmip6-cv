import json
import pprint
import sys

print("Number of arguments:", len(sys.argv), "arguments")
print("Argument List:", str(sys.argv))


table = "CORDEX-CMIP6_institution_id.json"
table_name = "institution_id"


def update_table(entry):
    with open(table, "r") as f:
        current = json.load(f)
    new_id = entry[table_name]
    if new_id not in current[table_name]:
        current[table_name][new_id] = entry
    else:
        print(f"'{new_id}' already in table with value: '{current[table_name][new_id]}'")
        raise Exception
    pprint.pprint(current)
    current = dict(sorted(current.items()))
    with open(table, "w") as f:
        json.dump(current, f, indent=4)


def get_entries(content):
    return json.loads(content)


if __name__ == "__main__":
    content = sys.argv[1]
    entry = get_entries(content)
    print(entry)
    update_table(entry)
