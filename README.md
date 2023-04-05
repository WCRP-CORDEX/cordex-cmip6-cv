# CORDEX-CV

**Controlled Vocabulary (CV) for use in CORDEX.**

This repository contains tables of controlled vocabulary for the *cmorization* of CORDEX datasets in the CMIP6 era. The actual [`CORDEX_CV.json`](https://github.com/WCRP-CORDEX/cordex-cmip6-cmor-tables/blob/main/Tables/CORDEX_CV.json) in the [cordex cmor table repository](https://github.com/WCRP-CORDEX/cordex-cmip6-cmor-tables) is created from a combination of all tables in this repository. There are two events that would trigger an update of the `CORDEX_CV.json` cmor table:

* a manual trigger of the [update-cv github action](https://github.com/WCRP-CORDEX/cordex-cv/actions/workflows/update-cv.yaml)
* a push event in this repo that updates one of the CV tables

The aim is to have the `CORDEX_CV.json` table updated when, e.g., a new RCM model is registered in the `source_id.json` table or a new `institution_id` is required.
