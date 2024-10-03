import json
from pathlib import Path

"""
# Export the CVs to JSON-schema.

The function `make_global_attrs_schema` reads the CVs in the root directory and return a JSON schema. This schema can 
then be used to validate global attributes from CORDEX simulations.

For example

```
import jsonschema
import xarray as xr
ds = xr.open_dataset("<path to netCDF file>")
schema = make_global_attrs_schema()
jsonschema.validate(ds.attrs, schema)
```

Any missing or incorrect global attribute will raise a `ValidationError`. 
"""

DIR = Path(".")


def read_cv(key: str) -> dict:
    """Read a CV file and return it as a dictionary."""
    path = DIR / f"CORDEX-CMIP6_{key}.json"
    with open(path) as f:
        return json.load(f)


def cv_to_property(cv: dict) -> dict:
    """Convert a CV to a JSON schema property."""
    if len(cv) > 1:
        raise ValueError("CV has more than one key.")

    field = {"source_id": "label",
             "experiment_id": "description",
             "domain_id": "domain",
             "driving_source_id": "driving_source"
             }

    out = {}
    for fid, keys in cv.items():
        items = []
        if isinstance(keys, dict):
            for key, value in keys.items():
                if isinstance(value, str):
                    items.append({"const": key, "title": value})
                elif isinstance(value, dict):
                    items.append(
                        {
                            "const": key,
                            "title": value.get(field[fid], "")
                        }
                    )
            out[fid] = {"oneOf": items}
        elif isinstance(keys, list):
            out[fid] = {"enum": keys}
    return out


def make_global_attrs_schema() -> dict:
    """Create a JSON schema for netCDF global attributes from the JSON CVs.
    """

    # Read required global attributes
    reqs = read_cv("required_global_attributes")["required_global_attributes"]

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "CORDEX-CMIP6 metadata schema for global attributes",
        "description": "JSON schema for global attributes of CORDEX-CMIP6 datasets. This schema is automatically "
                       "generated from the CVs. Manual edits will be overwritten.",
        "type": "object",
        "properties": {},
        "required": reqs
    }

    integer_fields = []

    formats = {"creation_date": "date-time"}

    props = {}
    for fid in reqs:
        if fid in integer_fields:
            # Could be replaced by patternProperties, but at the expense of readability
            props[fid] = {"type": "integer"}
        else:
            try:
                cv = read_cv(fid)
                props.update(cv_to_property(cv))
            except FileNotFoundError:
                props[fid] = {"type": "string"}

        if fid in formats:
            props[fid]["format"] = formats[fid]

    schema["properties"].update(props)

    return schema


if __name__ == "__main__":
    schema = make_global_attrs_schema()
    with open("cmip6-cordex-global-attrs-schema.json", "w") as f:
        json.dump(schema, f, indent=2)
