import yaml
import json
from icecream import ic


def get_field(file_label, field, is_map=False, is_cohort=False):
    with open(f"../CORDEX-CMIP6_{file_label}.json", "r") as file:
        data = json.load(file)
    rval = data[field]
    if isinstance(rval, dict):
        if is_map:
            if is_cohort:
                return [f"    {x[0]:<27} | Registered\n" for x in rval.items()]
            else:
                return [f"    {x[0]:<27} | {x[1]}\n" for x in rval.items()]
        else:
            return ", ".join(sorted(rval.keys()))
    elif isinstance(rval, list):
        return rval[0]


def read_map(map_file):
    with open(map_file, "r") as file:
        return yaml.load(file, Loader=yaml.FullLoader)


def update_ini_file(ini_content, map_data):
    """
    Update the ini content by replacing the value of fields as indicated
    in the YAML config file
    """
    updated_ini = []
    skip_map = False
    for line in ini_content:
        if "=" in line:
            skip_map = False
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key in map_data.keys():
                ic(key)
                is_map = map_data[key].get("is_map", False)
                is_cohort = map_data[key].get("is_cohort", False)
                new_value = get_field(
                    map_data[key]["file_label"],
                    map_data[key].get("field", map_data[key]["file_label"]),
                    is_map,
                    is_cohort,
                )
                if is_map:
                    updated_ini.append(line)
                    updated_ini.extend(new_value)
                    skip_map = True
                else:
                    updated_ini.append(f"{key} = {new_value}\n")
            else:
                updated_ini.append(line)
        elif "|" in line and skip_map:
            continue
        else:
            updated_ini.append(line)
    return updated_ini


if __name__ == "__main__":
    ini_file = "../docs/esg.cordex-cmip6.ini"
    with open(ini_file, "r") as file:
        ini_content = file.readlines()
    map_data = read_map("esg-ini-sources.yaml")
    updated_ini_content = update_ini_file(ini_content, map_data)
    with open(ini_file, "w") as file:
        file.writelines(updated_ini_content)
