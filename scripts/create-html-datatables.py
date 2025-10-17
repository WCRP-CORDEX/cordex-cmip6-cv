import json

import pandas as pd
from cordex_cv.common import table_prefix


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
    column_as_link="",
    column_as_link_source="",
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
    if column_as_link:
        if not column_as_link_source:
            column_as_link_source = column_as_link
        df[column_as_link] = (
            '<a href="' + df[column_as_link_source] + '">' + df[column_as_link] + "</a>"
        )
        if column_as_link != column_as_link_source:
            df.drop(columns=column_as_link_source, inplace=True)
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
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.css">
<script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.5.1.js"></script>
<script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.js"></script>"""
    )
    if title:
        fp.write(f"<title>{title}</title>")
    fp.write(
        """
<style>
body {
  font-family: "Montserrat", sans-serif;
  padding-top: 15px;
  padding-left: 15px;
  padding-right: 15px;
  padding-bottom: 600px;
}
tr:hover {background-color:#f5f5f5;}
th, td {text-align: left; padding: 2px;}
table {border-collapse: collapse;}
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
span.planned {color: #F54d4d; font-weight: bold}
span.running {color: #009900; font-weight: bold}
span.completed {color: #17202a; font-weight: bold}
span.published {color: #3399FF; font-weight: bold}
span.warning {color: #FF0000; font-weight: bold}
a {color: DodgerBlue}
a:link { text-decoration: none; }
a:visited { text-decoration: none; }
a:hover { text-decoration: underline; }
a:active { text-decoration: underline; }
.logo {
  text-align: center;
  margin-bottom: 20px;
}
.nav-button {
  display: inline-block;
  padding: 8px 16px;
  margin: 0 4px;
  background-color: #f8f9fa;
  border: 1px solid #ddd;
  border-radius: 20px;
  color: #0969da;
  text-decoration: none;
  transition: all 0.3s ease;
}
.nav-button:hover {
  background-color: #0969da;
  color: white;
  text-decoration: none;
}
</style>
</head>
<body>
"""
    )
    if title:
        fp.write(
            f"""
<div class="logo">
   <img src="https://cordex.org/wp-content/uploads/2025/02/CORDEX_RGB_logo_baseline_positive-300x133.png"
        alt="CORDEX Logo" >
   <h1>{title}</h1>
</div>
    """
        )
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

<script>
    // URL parameter helpers
    function getParam(name) {
        var urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name) || '';
    }

    function setParam(name, value) {
        var url = new URL(window.location);
        if (value && value !== '') {
            url.searchParams.set(name, value);
        } else {
            url.searchParams.delete(name);
        }
        window.history.replaceState({}, '', url);
    }

    $(document).ready(function() {
        // Get initial values from URL
        var initialSearch = getParam('search');
        var initialLength = parseInt(getParam('length')) || 20;
        var initialOrder = getParam('order');

        var initialOrderArray = [[0, 'asc']]; // default
        if (initialOrder) {
            try {
                initialOrderArray = JSON.parse(initialOrder);
            } catch (e) {
                console.log('Could not parse order parameter');
            }
        }

        // Initialize DataTable with URL parameters
        var table = $('#table_id').DataTable({
            pageLength: initialLength,
            lengthMenu: [20, 50, 100, 200, 500],
            order: initialOrderArray,
            searching: true
        });

        // Set initial search if provided
        if (initialSearch) {
            table.search(initialSearch).draw();
        }

        // Update URL when search changes
        table.on('search.dt', function() {
            var searchValue = table.search();
            setParam('search', searchValue);
        });

        // Update URL when page length changes
        table.on('length.dt', function(e, settings, len) {
            setParam('length', len == 20 ? '' : len);
        });

        // Update URL when column order changes
        table.on('order.dt', function() {
            var currentOrder = table.order();
            setParam('order', JSON.stringify(currentOrder));
        });
    });
</script>
</body>
</html>"""
    )
    fp.close()


cvs = ["source_id", "institution_id"]

link_header = (
    "\n<div style='text-align: center; margin: 1em 0;'>"
    + "".join(
        [f'<a class="nav-button" href="{table_prefix}_{x}.html">{x}</a>' for x in cvs]
    )
    + "</div>\n"
)
cordex_cv_repo = '<a href="https://github.com/WCRP-CORDEX/cordex-cmip6-cv">CORDEX-CMIP6 CV repository</a>'
display_options = {
    "source_id": {
        "columns": [
            "source_id",
            "label",
            "label_extended",
            "release_year",
            "source_type",
            "institution_id",
            "activity_participation",
            "further_info_url",
            "license",
        ],
        "is_1d": False,
        "intro": f"{link_header}List of registered models. Visit the {cordex_cv_repo} to register or update your model.",
        "column_as_link": "source_id",
        "column_as_link_source": "further_info_url",
    },
    "institution_id": {
        "columns": ["institution_id", "institution"],
        "is_1d": True,
        "intro": f"{link_header}List of registered institutions. Visit the {cordex_cv_repo} to register or update your institution details.",
    },
}

if __name__ == "__main__":
    for cv in ["source_id", "institution_id"]:
        opts = display_options[cv]
        json2datatable(
            f"{table_prefix}_{cv}.json",
            f"docs/{table_prefix}_{cv}.html",
            cv,
            title=f"CORDEX-CMIP6 CV · {cv}",
            **opts,
        )
