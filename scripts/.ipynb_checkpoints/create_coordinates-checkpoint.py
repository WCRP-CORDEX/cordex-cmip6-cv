import json
from os import path as op
import re

path = op.join(op.dirname(__file__), "../Tables")

tables = ["1hr", "6hr", "day", "mon"]

files = [op.join(path, f"CORDEX-CMIP6_{t}.json") for t in tables]

height = {
    "standard_name": "height",
    "units": "m",
    "axis": "Z",
    "long_name": "height",
    "climatology": "",
    "formula": "",
    "must_have_bounds": "no",
    "out_name": "height",
    "positive": "up",
    "requested": "",
    "requested_bounds": "",
    "stored_direction": "increasing",
    "tolerance": "",
    "type": "double",
    "valid_max": "",
    "valid_min": "",
    "value": "",
    "z_bounds_factors": "",
    "z_factors": "",
    "bounds_values": "",
    "generic_level_name": "",
}


pressure = {
    "standard_name": "air_pressure",
    "units": "Pa",
    "axis": "Z",
    "long_name": "pressure",
    "climatology": "",
    "formula": "",
    "must_have_bounds": "no",
    "out_name": "plev",
    "positive": "down",
    "requested": "",
    "requested_bounds": "",
    "stored_direction": "",
    "tolerance": "",
    "type": "double",
    "valid_max": "",
    "valid_min": "",
    "value": "",
    "z_bounds_factors": "",
    "z_factors": "",
    "bounds_values": "",
    "generic_level_name": "",
}


longitude = {
    "standard_name": "longitude",
    "units": "degrees_east",
    "axis": "X",
    "long_name": "Longitude",
    "climatology": "",
    "formula": "",
    "must_have_bounds": "yes",
    "out_name": "lon",
    "positive": "",
    "requested": "",
    "requested_bounds": "",
    "stored_direction": "increasing",
    "tolerance": "",
    "type": "double",
    "valid_max": "360.0",
    "valid_min": "0.0",
    "value": "",
    "z_bounds_factors": "",
    "z_factors": "",
    "bounds_values": "",
    "generic_level_name": "",
}

latitude = {
    "standard_name": "latitude",
    "units": "degrees_north",
    "axis": "Y",
    "long_name": "Latitude",
    "climatology": "",
    "formula": "",
    "must_have_bounds": "yes",
    "out_name": "lat",
    "positive": "",
    "requested": "",
    "requested_bounds": "",
    "stored_direction": "increasing",
    "tolerance": "",
    "type": "double",
    "valid_max": "90.0",
    "valid_min": "-90.0",
    "value": "",
    "z_bounds_factors": "",
    "z_factors": "",
    "bounds_values": "",
    "generic_level_name": "",
}


time = {
            "standard_name": "time",
            "units": "days since ?",
            "axis": "T",
            "long_name": "time",
            "climatology": "",
            "formula": "",
            "must_have_bounds": "yes",
            "out_name": "time",
            "positive": "",
            "requested": "",
            "requested_bounds": "",
            "stored_direction": "increasing",
            "tolerance": "",
            "type": "double",
            "valid_max": "",
            "valid_min": "",
            "value": "",
            "z_bounds_factors": "",
            "z_factors": "",
            "bounds_values": "",
            "generic_level_name": ""
}

time1 = {
            "standard_name": "time",
            "units": "days since ?",
            "axis": "T",
            "long_name": "time",
            "climatology": "",
            "formula": "",
            "must_have_bounds": "no",
            "out_name": "time",
            "positive": "",
            "requested": "",
            "requested_bounds": "",
            "stored_direction": "increasing",
            "tolerance": "",
            "type": "double",
            "valid_max": "",
            "valid_min": "",
            "value": "",
            "z_bounds_factors": "",
            "z_factors": "",
            "bounds_values": "",
            "generic_level_name": ""
}



dim_table = {
    "longitude": longitude,
    "latitude": latitude,
    "heightm": height,
    "p": pressure,
    "time": time,
    "time1": time1
}


def create_dimension_entry(dim):
    dim_type = re.sub(r'[0-9]', '', dim) # remove digits
    if dim_type in ["heightm", "p"]:
        value = get_value_from_str(dim)
        return create_coord(dim_type, value)
    return dim_table[dim].copy()


def create_coord(dim_type, value):
    coord_entry = dim_table[dim_type].copy()
    coord_entry["value"] = str(100 * int(value)) if dim_type == "p" else value
    return coord_entry


def get_value_from_str(out_name):
    try:
        return re.search(r"\d+", out_name).group()
    except Exception:
        return None


def get_coordinates(df):
    coords = []
    for t in ["heightm", "p"]:
        vdims = get_vertical_dimension(df, t)
        for dim in vdims:
            value = get_value_from_str(dim)
            coords.append(create_coord(t, value))
    return coords


def dims_from_table(table):
    with open(table) as f:
        d = json.load(f)["variable_entry"]
    dims = []
    for v in d.values():
        if "dimensions" in v:
            dims.append(v["dimensions"])
    return dims


def unique_dims(dims):
    res = []
    for dim in dims:
        coords = dim.split(" ")
        for c in coords:
            if c not in res:
                res.append(c)
    return res


def unique_dims_from_tables(tables):
    dims = []
    for t in tables:
        print(t)
        dims.extend(dims_from_table(t))
    return unique_dims(dims)


def table_to_json(table, dir=None):
    if dir is None:
        dir = "./"
    filename = op.join(dir, f"CORDEX_coordinate.json")
    print(f"writing: {filename}")
    with open(filename, "w") as fp:
        json.dump(table, fp, indent=4)

def run():
    dims = unique_dims_from_tables(files)
    print(f"found: {dims}")
    return {"axis_entry": {d: create_dimension_entry(d) for d in dims}}


if __name__ == "__main__":
    dims = run()
    table_to_json(dims)
