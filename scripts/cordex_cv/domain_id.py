import pandas as pd
from .common import domain_table_url, table_prefix, write_json


def create_domain_id():
    """Create domain_id CV from cordex domain table

    Creates CV from domains in table:
    "https://raw.githubusercontent.com/WCRP-CORDEX/domain-tables/
    main/rotated-latitude-longitude.csv"

    """
    df = pd.concat(
        [pd.read_csv(url, index_col="domain_id") for url in domain_table_url]
    )
    print(df)
    df["domain_id"] = df.index
    text = {"domain_id": df[["domain", "domain_id"]].to_dict(orient="index")}
    write_json(f"{table_prefix}_domain_id.json", text)
