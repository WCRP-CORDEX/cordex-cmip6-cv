import pandas as pd
from common import domain_table_url, table_prefix, write_json


def create_domain_id_table():
    """Create domain_id CV from cordex domain table

    Creates CV from domains in table:
    "https://raw.githubusercontent.com/WCRP-CORDEX/domain-tables/
    main/rotated-latitude-longitude.csv"

    """
    df = pd.read_csv(domain_table_url, index_col="domain_id")
    df["domain_id"] = df.index
    text = {"domain_id": df[["domain", "domain_id"]].to_dict(orient="index")}
    write_json(text, f"{table_prefix}_domain_id.json")


if __name__ == "__main__":
    create_domain_id_table()
