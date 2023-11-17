import json

import pandas as pd
from common import table_prefix


def addtag(word, field):
    rval = word
    if (field == "comments") and word.startswith("#"):
        rval = f'<span class="tag">{word[1:]}</span>'
    elif (field == "comments") and word.startswith("http"):
        rval = f'<a href="{word}">{word}</a>'
    elif (field == "status") and word in [
        "selected",
        "planned",
        "running",
        "completed",
        "published",
    ]:
        rval = f'<span class="{word}">{word}</span>'
    return rval


def taggify(text, field):
    rval = text
    if field in ["status", "comments"]:
        rval = " ".join([addtag(x, field) for x in text.split(" ")])
    return rval


def delistify(text):
    rval = text
    # if type(text) == list:
    if isinstance(text, list):
        rval = ", ".join(text)
    return rval


def listify(dic):
    return {k: [v] for k, v in dic}


def json2datatable(
    jsonfile,
    htmlout,
    top_level,
    title="",
    intro="",
    columns=[],
    linearize_columns=[],
    rename_fields={},
    is_1d=False,
):
    with open(jsonfile) as f:
        data = json.load(f)
    if top_level:
        data = data[top_level]
    if linearize_columns:
        for col in linearize_columns:
            for item in data:
                data[item].update(
                    {k: v["description"] for k, v in data[item][col].items()}
                )
    if is_1d:
        df = pd.DataFrame(data.values(), index=data.keys()).reset_index()
        df.columns = [top_level, top_level.replace("_id", "")]
    else:
        df = pd.DataFrame(data).transpose()
    if columns:
        df = df[columns]
    field_names = dict(zip(df.columns, df.columns))
    field_names.update(rename_fields)
    fp = open(htmlout, "w")
    fp.write(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta name="author" content="J. Fernandez" />
<meta name="keywords" content="HTML, CSS, JavaScript" />
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.css">
<script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.5.1.js"></script>
<script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.js"></script>
<script type="text/javascript">
$(document).ready( function () {
    $('#table_id').DataTable({
    });
} );
</script>
"""
    )
    if title:
        fp.write(f"<title>{title}</title>")
    fp.write(
        """
<style>
span.tag {
  background-color: #c5def5;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 500;
  line-height: 22px !important;
  border: 1px solid transparent;
  border-radius: 2em;
}
span.selected {color: #3399FF}
span.planned {color: #FF9999}
span.running {color: #009900}
span.completed {color: black; font-weight: bold}
span.published {color: #3399FF; font-weight: bold}
span.warning {color: #FF0000; font-weight: bold}
a:link { text-decoration: none; }
a:visited { text-decoration: none; }
a:hover { text-decoration: underline; }
a:active { text-decoration: underline; }
</style>
</head>
<body>
"""
    )
    if title:
        fp.write(f"<h1>{title}</h1>")
    if intro:
        fp.write(f"{intro}<p>")
    fp.write(
        """
<table id="table_id" class="display">
    <thead>
        <tr>
"""
    )
    [fp.write(f"              <th>{field_names[x]}</th>\n") for x in df]
    fp.write(
        """
        </tr>
    </thead>
    <tbody>
"""
    )
    for idx, row in df.iterrows():
        fp.write("        <tr>\n")
        for field, item in zip(df.columns, row):
            fp.write(f"            <td>{delistify(item)}</td>\n")
        fp.write("        </tr>\n")
    fp.write(
        """
    </tbody>
</table>
</body>
</html>"""
    )
    fp.close()


datatable_columns = {
    "source_id": [
        "source_id",
        "label",
        "release_year",
        "institution_id",
        "activity_participation",
        "license",
    ],
    "institution_id": [
        "institution_id",
        "institution"
    ],
}

is_1d = {"source_id": False, "institution_id": True}

link_header = '> ' + ' · '.join([f'<a href="{table_prefix}_{x}.html">{x} table</a>' for x in datatable_columns.keys()]) + '<p>'
cordex_cv_repo = '<a href="https://github.com/WCRP-CORDEX/cordex-cmip6-cv">CORDEX-CMIP6 CV repository</a>'

text = {
    "source_id": f'{link_header}Registered models. Visit the {cordex_cv_repo} to register or update your model. <span class="warning">This is a test page.</span>',
    "institution_id": f'{link_header}Registered institutions. Visit the {cordex_cv_repo} to register or update your institution details. <span class="warning">This is a test page.</span>',
    "source_id_components": f'{link_header}Registered models with components. <span class="warning">This is a test page.</span>',
}


if __name__ == "__main__":
    for cv in ["source_id", "institution_id"]:
        json2datatable(
            f"../{table_prefix}_{cv}.json",
            f"../docs/{table_prefix}_{cv}.html",
            cv,
            columns=datatable_columns[cv],
            is_1d=is_1d[cv],
            title=f"WCRP-CORDEX CORDEX-CMIP6 CV {cv}",
            intro=text[cv],
        )
