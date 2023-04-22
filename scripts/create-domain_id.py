import pandas as pd
from common import domain_table_url, write_json


def create_domain_id_table():
    df = pd.read_csv(domain_table_url, index_col="domain_id")
    df["domain_id"] = df.index
    text = {"domain_id": df[["domain", "domain_id"]].to_dict(orient="index")}
    write_json(text, "CORDEX_domain_id.json")


if __name__ == "__main__":
    create_domain_id_table()
