from common import CMIP6_CV_URL, read_json_url, table_prefix, write_json


def create_driving_source_attrs(cmip6_source_id):
    keep_rename = {
        "institution_id": "driving_institution_id",
        "source_id": "driving_source_id",
        "source": "driving_source",
    }
    driving_source_id = {}
    for source_id, attrs in cmip6_source_id.items():
        new_attrs = {}
        for attr, v in attrs.items():
            if attr in keep_rename.keys():
                new_attrs[keep_rename[attr]] = v
        driving_source_id[source_id] = new_attrs
    return driving_source_id


def era5_driving_source_id():
    return dict(
        driving_institution_id=["ECMWF"],
        driving_source_id="ECMWF-ERA5",
        driving_experiment_id=["evaluation"],
    )


def create_driving_source_id():
    """Create CORDEX driving source id from CMIP6 source_id

    Takes the original CMIP6 source id, takes and renames
    some attributes for use as driving_source_id in CORDEX.

    """
    cmip6_cv = read_json_url(CMIP6_CV_URL)
    driving_source_id = dict(
        driving_source_id=create_driving_source_attrs(cmip6_cv["CV"]["source_id"])
    )
    driving_source_id["driving_source_id"]["ECMWF-ERA5"] = era5_driving_source_id()
    return write_json(driving_source_id, f"{table_prefix}_driving_source_id.json")


if __name__ == "__main__":
    create_driving_source_id()
