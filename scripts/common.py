import json
from os import path as op

import requests

data_request = "https://raw.githubusercontent.com/WCRP-CORDEX/cordex-cmip6-data-request/main/tables/cordex-cmip6-data-request-extended.csv"

CMIP6_CV_URL = "https://raw.githubusercontent.com/PCMDI/cmip6-cmor-tables/master/Tables/CMIP6_CV.json"

domain_table_url = "https://raw.githubusercontent.com/WCRP-CORDEX/domain-tables/main/rotated-latitude-longitude.csv"


table_dir = op.join(op.dirname(op.dirname(__file__)), "Tables")

table_prefix = "CORDEX-CMIP6"


def read_json_url(url):
    with requests.get(url) as r:
        return r.json()


def read_json(filename):
    with open(filename) as f:
        return json.loads(f.read())
    return filename


def write_json(content, filename):
    with open(filename, "w") as f:
        json.dump(content, f, indent=4)
    return filename
