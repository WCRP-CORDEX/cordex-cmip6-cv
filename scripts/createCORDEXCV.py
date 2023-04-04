# -*- coding: utf-8 -*-
import json
import urllib.request
from collections import OrderedDict

# List of files needed from github for CORDEX CV
# ---------------------------------------------
filelist = [
    "CORDEX_required_global_attributes.json",
    "CORDEX_activity_id.json",
    "CORDEX_domain_id.json",
    "CORDEX_domain.json",
    "CORDEX_institution_id.json",
    "CORDEX_driving_source_id.json",
    "CORDEX_source_id.json",
    "CORDEX_source_type.json",
    "CORDEX_frequency.json",
    "CORDEX_grid_label.json",
    "CORDEX_nominal_resolution.json",
    "CORDEX_realm.json",
    "CORDEX_table_id.json",
    #    "CORDEX_license.json",
    "CORDEX_DRS.json",
    "mip_era.json",
    #"CORDEX_driving_experiment_id.json",
    "CORDEX_experiment_id.json",
]
# Github repository with CORDEX related Control Vocabulary files
# -------------------------------------------------------------
githubRepo = "https://raw.githubusercontent.com/WCRP-CORDEX/cordex-cv/main/"


class readWCRP:
    def __init__(self):
        pass

    def createSource(self, myjson):
        root = myjson["source_id"]
        for key in root.keys():
            root[key]["source"] = (
                root[key]["label"] + " (" + root[key]["release_year"] + "): " + chr(10)
            )
            for realm in root[key]["model_component"].keys():
                if (
                    root[key]["model_component"][realm]["description"].find("None")
                    == -1
                ):
                    root[key]["source"] += realm + ": "
                    root[key]["source"] += root[key]["model_component"][realm][
                        "description"
                    ] + chr(10)
            root[key]["source"] = root[key]["source"].rstrip()
            del root[key]["label"]
            del root[key]["release_year"]
            # del root[key]["label_extended"]
            del root[key]["model_component"]

    def createExperimentID(self, myjson):
        #
        # Delete undesirable attribute for experiement_id
        #
        root = myjson["experiment_id"]
        for key in root.keys():
            print(key)
            # del root[key]["tier"]
            # del root[key]["start_year"]
            # del root[key]["end_year"]
            # del root[key]["description"]
            # del root[key]["min_number_yrs_per_sim"]

    def createLicense(self, myjson):
        #
        # Create regex templates for validating license values in CMOR
        #
        root = myjson["license"]
        base_template = root["license"]
        # license_templates = []
        # for key, value in root["license_options"].items():
        #    tmp = base_template.replace(". ", ". *")
        #    tmp = tmp.replace(
        #        "<Creative Commons; select and insert a license_id; see below>",
        #        value["license_id"],
        #    )
        #    tmp = tmp.replace(
        #        "<insert the matching license_url; see below>", value["license_url"]
        #    )
        #    tmp = tmp.replace(".", "\\.")
        #    tmp = tmp.replace(
        #        "<Your Institution; see CORDEX_institution_id\\.json>", ".*"
        #    )
        #    tmp = tmp.replace("[ and at <some URL maintained by modeling group>]", ".*")
        #    license_template = "^{}$".format(tmp)
        #    license_templates.append(license_template)
        myjson["license"] = base_template  # license_templates

    def readGit(self):
        Dico = OrderedDict()
        for file in filelist:
            url = githubRepo + file
            print(url)
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                urlJson = response.read().decode()
            myjson = json.loads(urlJson, object_pairs_hook=OrderedDict)
            if file == "CORDEX_source_id.json":
                self.createSource(myjson)
            if file == "CORDEX_experiment_id.json":
                self.createExperimentID(myjson)
            if file == "CORDEX_license.json":
                self.createLicense(myjson)
            Dico.update(myjson)

        finalDico = OrderedDict()
        finalDico["CV"] = Dico
        return finalDico


def run():
    f = open("CORDEX_CV.json", "w")
    gather = readWCRP()
    CV = gather.readGit()
    regexp = OrderedDict()
    regexp["mip_era"] = ["CMIP6"]
    regexp["product"] = ["model-output"]
    regexp["tracking_id"] = ["hdl:21.14100/.*"]
    regexp["further_info_url"] = ["https://furtherinfo.es-doc.org/.*"]
    regexp["realization_index"] = ["^\\[\\{0,\\}[[:digit:]]\\{1,\\}\\]\\{0,\\}$"]
    regexp["variant_label"] = [
        "r[[:digit:]]\\{1,\\}i[[:digit:]]\\{1,\\}p[[:digit:]]\\{1,\\}f[[:digit:]]\\{1,\\}$"
    ]
    regexp["data_specs_version"] = [
        "^[[:digit:]]\\{2,2\\}\\.[[:digit:]]\\{2,2\\}\\.[[:digit:]]\\{2,2\\}$"
    ]
    regexp["Conventions"] = ["^CF-1.7 CMIP-6.[0-2]\\( UGRID-1.0\\)\\{0,\\}$"]
    regexp["forcing_index"] = ["^\\[\\{0,\\}[[:digit:]]\\{1,\\}\\]\\{0,\\}$"]
    regexp["initialization_index"] = ["^\\[\\{0,\\}[[:digit:]]\\{1,\\}\\]\\{0,\\}$"]
    regexp["physics_index"] = ["^\\[\\{0,\\}[[:digit:]]\\{1,\\}\\]\\{0,\\}$"]

    CV["CV"].update(regexp)
    for exp in CV["CV"]["experiment_id"]:
        CV["CV"]["experiment_id"][exp]["activity_id"] = [
            " ".join(CV["CV"]["experiment_id"][exp]["activity_id"])
        ]
        print("AC ID:", CV["CV"]["experiment_id"][exp]["activity_id"])
    f.write(json.dumps(CV, indent=4, separators=(",", ":"), sort_keys=False))

    f.close()


if __name__ == "__main__":
    run()
