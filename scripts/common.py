
from os import path as op

data_request = "https://raw.githubusercontent.com/WCRP-CORDEX/cordex-cmip6-data-request/main/tables/cordex-cmip6-data-request-extended.csv"

table_dir = op.join(op.dirname(op.dirname(__file__)), "Tables")

table_prefix = "CORDEX"
