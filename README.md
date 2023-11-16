# CORDEX-CMIP6 CV

**Controlled Vocabulary (CV) for use in CORDEX.**

This repository contains tables of controlled vocabulary for the *cmorization* of CORDEX datasets in the CMIP6 era. The actual [`CORDEX_CV.json`](https://github.com/WCRP-CORDEX/cordex-cmip6-cmor-tables/blob/main/Tables/CORDEX_CV.json) in the [cordex cmor table repository](https://github.com/WCRP-CORDEX/cordex-cmip6-cmor-tables) is created from a combination of all tables in this repository. There are two events that would trigger an update of the `CORDEX_CV.json` cmor table:

* a manual trigger of the [update-cv github action](https://github.com/WCRP-CORDEX/cordex-cv/actions/workflows/update-cv.yaml)
* a push event in this repo that updates one of the CV tables

The aim is to have the `CORDEX_CV.json` table updated when, e.g., a new RCM model is registered in the `source_id.json` table or a new `institution_id` is required.

## Registering Institutions, Models, or requesting changes to CVs:

To register your institution or model, please submit an issue using these forms: [New institution_id]() or [New source_id (i.e. model)]().
These forms will automatically create a pull request, where further details can be discussed.
Models must not be distinguished by the `institution_id`.
Do not register a new `source_id` if the same model or method configuration is already registered by other institution.
Just request to add your `institution_id` to the list of the corresponding `source_id`.

To request changes in any other CV use a [blank issue](https://github.com/WCRP-CORDEX/cordex-cmip6-cv/issues/new) with a meaningful title.
E.g. `source_type: add YOURNEWTYPE` or `source_id: update MODEL123A further_info_url`

To view current repository contents in HTML format, point your browser to:

| target | URL |
| :-- | :-- |
| `institution_id` | [CORDEX-CMIP6_institution_id.html](https://wcrp-cordex.github.io/cordex-cmip6-cv/CORDEX-CMIP6_institution_id.html) |
| `source_id` | [CORDEX-CMIP6_source_id.html](https://wcrp-cordex.github.io/cordex-cmip6-cv/CORDEX-CMIP6_source_id.html) |

The CVs build on logic that is described in the [CORDEX-CMIP6 Archiving Specifications for Dynamical Downscaling](http://goo.gl/v1drZl) document.

The controlled vocabularies for CORDEX-CMIP6 will be augmented (e.g., as new `institution_id`s and `source_id`s are registered), but there should be no changes in the existing vocabulary that would impair searches of and access to already published data or that would in any way invalidate published data.
