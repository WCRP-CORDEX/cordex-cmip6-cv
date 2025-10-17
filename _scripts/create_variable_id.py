import json
import os
from pathlib import Path

import esgvoc.api as ev

# URLs of the JSON files on GitHub
json_folder = "_scripts/cordex-cmip6-cmor-tables/Tables"

# Directory where the JSON files will be saved
save_dir = "variable_id"

# Create the directory if it doesn't exist
os.makedirs(save_dir, exist_ok=True)

json_files = [f for f in Path(json_folder).glob("*.json")]
print("Found JSON files:", json_files)

known_variables_in_universe = ev.get_all_terms_in_data_descriptor("variable")

for json_file in json_files:
    print("Processing file:", json_file)
    with open(json_file, "r") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Erreur de lecture JSON pour {json_file}, fichier ignoré")
            continue

    data = raw_data.get("variable_entry")
    if data is None:
        print(f"{json_file} n'a pas de clé 'variable_entry', fichier ignoré")
        continue

    for item in data:
        found_item = None
        for variable in known_variables_in_universe:
            if variable.drs_name == item:
                found_item = variable
                break

        if found_item is None:
            print(item, "not found in universe")
        else:
            # Create json file
            dict_to_save = {
                "@context": "000_context.jsonld",
                "id": found_item.id,
                "type": "variable",
            }
            # print(dict_to_save)
            with open(Path(save_dir) / f"{found_item.id}.json", "w") as f:
                json.dump(dict_to_save, f, indent=4)
