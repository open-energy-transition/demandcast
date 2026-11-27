# Publish a release on Zenodo

`publish.py` uploads a release of DemandCast to [Zenodo](https://zenodo.org/), an open repository for research data: the trained model, its forecasts, their inputs, and the results of its validation. You need it only if you maintain a Zenodo record of DemandCast results.

The script never publishes anything. It creates a **draft**, which you check and publish on the Zenodo website.

## What a release is

A Zenodo **record** is a dataset page with a DOI, a permanent identifier for citing it. A record can have several **versions**. Each version has its own DOI, and all share one "concept" DOI that points to the latest version. The released DemandCast forecasts are at [10.5281/zenodo.18374351](https://doi.org/10.5281/zenodo.18374351).

A release usually contains:

| File | What it holds |
|---|---|
| `xgboost_model_<time>.json` | The trained model that made the forecasts |
| `forecasts_on_historical_period.parquet` | The hourly forecasts, made from your forecasts file at the upload (see [The forecasts file](#the-forecasts-file)) |
| `assembled_data_for_forecasting_<time>.parquet` | The inputs of the forecasts at each hour |
| `validation.zip` | The model trained without the most recent year of each country and subdivision, and its errors on that year |
| `cross_validation.zip` | The errors of each entity left out of the training in turn, and the model of each fold |
| `<name>.manifest.json` | The [manifest](../reference/data-folder.md#manifests) of each file, added automatically |
| `README.md` | The files, how to reproduce them, and the sources, licences and attributions of the inputs, added automatically |

### What a release can never contain

The licences of many data sources forbid redistributing the historical electricity demand. So the script stops, before uploading anything, if a file:

- is inside the `electricity_demand/` folder of the data folder (after following symbolic links);
- has a name starting with `assembled_data_for_training_` (the training data, and its `_coverage.csv` and `_provenance.csv` files);
- has a name starting with `predictions_` (the predictions of a validation or cross-validation, which hold the actual demand of each hour).

Only file names are checked, so folders such as `using_assembled_data_for_training_...` are fine. The assembled data for forecasting is fine too: it has the inputs of the model, without the demand.

## Before you start

1. **Create a Zenodo token**: in your Zenodo account settings, *Applications* → *Personal access tokens*, with the scopes `deposit:write` and `deposit:actions`.
2. **Add it to `.env`** as `ZENODO_API_KEY` (see [Install](../getting-started/install.md#3-add-your-api-keys)).
3. **Prepare the files**: train, forecast, validate and cross-validate, so that each file has its manifest (see [Train and validate](train-validate.md), [Cross-validate](cross-validate.md), [Forecast](forecast.md)).
4. **Update the release metadata** in `demandcast/publishing/release/metadata.yaml` (see [Metadata](#metadata)).

The token is sent only to Zenodo, in the `Authorization` header. A failed request reports only the type of the failure, so the token never reaches a log or a traceback.

## Run a release

1. Set the release in `config/publish_config.yaml`, or in a copy of it:

    ```yaml
    zenodo_record: 18374352   # a version of your record, or "new"
    version: "2.1.0"
    files:                    # relative to the data folder, unless absolute
      - models/xgboost/xgboost_model_20261101_120000.json
      - results/forecasts/with_xgboost_model_20261101_120000/using_assembled_data_for_forecasting_20261101_100000/all_20261101_130000.parquet
      - assembled/assembled_data_for_forecasting_20261101_100000.parquet
    folders:                  # each uploaded as <folder>.zip
      validation:
        - models/xgboost/xgboost_model_20261101_110000.json
        - results/validation/with_xgboost_model_20261101_110000/using_assembled_data_for_training_20261101_090000/all_20261101_113000.parquet
        - results/validation/with_xgboost_model_20261101_110000/using_assembled_data_for_training_20261101_090000/all_20261101_113000.csv
        - results/validation/with_xgboost_model_20261101_110000/using_assembled_data_for_training_20261101_090000/summary_20261101_113000.csv
      cross_validation:
        - results/cross_validation/with_xgboost/using_assembled_data_for_training_20261101_090000/all_20261101_140000.parquet
        - results/cross_validation/with_xgboost/using_assembled_data_for_training_20261101_090000/all_20261101_140000.csv
        - results/cross_validation/with_xgboost/using_assembled_data_for_training_20261101_090000/summary_20261101_140000.csv
        - results/cross_validation/with_xgboost/using_assembled_data_for_training_20261101_090000/models_20261101_140000.zip
    metadata_file: oet_zenodo_metadata.yaml
    sandbox: false
    ```

2. From the `demandcast/` folder, run `uv run publish.py`, or `uv run publish.py --config config/my_release.yaml` for your own file.
3. Open the log, `data/logs/publication_<time>.log`, for the address of the draft. The terminal shows nothing unless the script fails.
4. [Check the draft](#check-the-draft-before-you-publish) and publish it on Zenodo.

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `zenodo_record` | Yes | — | The number of **one version** of your record, as in `https://zenodo.org/records/<number>`, unquoted. The release becomes a new version of that record. `new` creates a new record. |
| `version` | Yes | — | The version of the release, quoted, such as `"2.1.0"` (YAML reads `2.1` as a number, which is rejected). The [metadata](#metadata) must name it. |
| `files` | Yes | `[]` (must not be empty) | The files uploaded as they are: usually the model, its forecasts and the assembled data for forecasting |
| `folders` | No | `{}` | Groups of files, each uploaded as one ZIP archive named after the group (`validation` → `validation.zip`). Names may contain only letters, digits, `_` and `-`; each group needs at least one file. |
| `metadata_file` | No | `oet_zenodo_metadata.yaml` | The file in `config/` with the creators and contributors of a **new** record. Ignored for a new version. |
| `sandbox` | No | `false` | `true` uses the [Zenodo Sandbox](#test-on-the-zenodo-sandbox), with the token in `SANDBOX_ZENODO_API_KEY` |

Paths in `files` and `folders` are relative to the data folder, unless absolute.

!!! warning "Use the number of a version, not the concept DOI"
    `zenodo_record` is the number in the address of one version, such as `18374352`. The number of the concept DOI (`10.5281/zenodo.18374351`) is not a version. A quoted number, such as `"18374352"`, is rejected.

## Files and folders

### Manifests are added for you

The script checks each file against its manifest and uploads the manifest next to it:

- A file whose content differs from the checksum in its manifest stops the release.
- A file without a manifest is uploaded with a warning in the log. The summaries (`summary_<time>.csv`) and the archive of the fold models (`models_<time>.zip`) have no manifest of their own, since the manifest of the results (`all_<time>`) records their checksums, so these warnings are expected.
- The CSV and Parquet files of the same results share one manifest, uploaded once.
- If a list contains a model, every result in the same list (`files`, or one folder) must come from that model, according to its manifest. This is why the validation model goes in the `validation` folder with its results, not in `files`.

### The forecasts file

The forecasts that `forecast.py` writes have all the inputs of the model at each hour. The script uploads instead a compact file, `forecasts_on_historical_period.parquet`, with three columns:

| Column | Meaning |
|---|---|
| `Time (UTC)` | The end of the hour, in UTC |
| `Entity code` | The code of the country or subdivision, such as `FRA` or `USA_CAL` |
| `Forecast load (MW)` | The forecast demand of the hour, in MW |

This name and these columns are those of the first DemandCast release, which other tools, such as PyPSA-Earth, download. Add the assembled data for forecasting to `files` to publish the inputs of each hour.

The compact file gets its own manifest, with the model, the assembled data, the units and the `annual_totals` of the forecasts, and the name, checksum and code version of the forecasts file it comes from.

The forecasts file is the Parquet file in `files` whose manifest says it holds forecasts:

- Forecasts without a manifest, in `results/forecasts/`, stop the release: they cannot be checked or made compact. Forecast again with `forecast.py`.
- `files` can contain only one forecasts file.
- Forecasts listed in `folders` are archived as they are.

### Folders become ZIP archives

Zenodo has no folders. Each entry of `folders` becomes one ZIP archive with the files and their manifests inside a folder of the same name: `validation.zip` holds `validation/all_<time>.parquet`, and so on. Zenodo previews the files of an archive.

Two files of one archive, or two files of the release, cannot have the same name.

### The README

Every release also gets `demandcast/publishing/release/README.md` (see [What a release is](#what-a-release-is)). Update it when the content of a release changes, such as a new input.

## Metadata

`demandcast/publishing/release/metadata.yaml` holds the title, description, keywords and related links of the release. It must have exactly the keys `title`, `description`, `keywords` and `related_identifiers`. Edit it for each release: the description names the files and gives the errors of the model.

Before anything is uploaded, the script checks it against the release, and stops with the list of what does not match:

| Check | Passes when | Fails when |
|---|---|---|
| The version is named | `version` appears in a link to its tag (`releases/tag/v2.1.0`) or after "DemandCast" (`DemandCast 2.1.0`) | Neither form names it |
| No other version is named | Only `version` appears in these two forms. Other mentions, such as "Changes from version 1.0.0", are not checked. | Another version appears in one of these forms, such as a link to an older tag |
| Every file named exists | Every name ending in `.parquet`, `.json`, `.zip`, `.md` or `.csv`, such as `validation.zip`, is an uploaded file | A name with an old timestamp, or a file you did not upload |

Names inside links, and `.manifest.json` alone, are not checked. When you train or forecast again, update the timestamps in the description.

### New version or new record

Both take the title, description, keywords and related links from `metadata.yaml`, and the version from `version`.

| | New version (`zenodo_record: <number>`) | New record (`zenodo_record: new`) |
|---|---|---|
| DOI | A new DOI for the version when you publish it; the concept DOI stays | A new DOI and a new concept DOI |
| Creators, contributors, communities | Kept from the record | Creators and contributors from `metadata_file` |
| Other metadata | Kept from the record, except dates without a start or end, which Zenodo rejects in a draft | Upload type `dataset`, open access, licence CC BY 4.0, language English |
| Publication date | Today, by your computer's clock | Not set by the script |
| Files | Only the uploaded ones: the script removes the files that Zenodo copies from the previous version, which keeps them | Only the uploaded ones |

The default `metadata_file`, `config/oet_zenodo_metadata.yaml`, lists the creators (name, affiliation, ORCID) and contributors (name and role, such as `HostingInstitution` or `Sponsor`) of Open Energy Transition's records. For your own record, copy it, change the people, and set `metadata_file` to the copy's name.

## Test on the Zenodo Sandbox

The [Zenodo Sandbox](https://sandbox.zenodo.org/) is a separate copy of Zenodo for tests, with its own accounts and tokens. Create a token there, add it to `.env` as `SANDBOX_ZENODO_API_KEY`, set `sandbox: true`, and give a sandbox record or `zenodo_record: new`.

## Check the draft before you publish

Open the address of the draft from the log, and check the files (each expected file with a plausible size, `README.md` and the manifests, none of the previous version), the previews of the ZIP archives, the metadata (title, version, description, related links) and, for a new record, the creators and licence. Then click *Publish*.

!!! warning
    The files of a published version cannot be changed or removed. You can still edit its metadata.

## What happens, step by step

The script stops at the first problem. Before it sends anything, it checks the settings and the [forbidden files](#what-a-release-can-never-contain), makes the compact forecasts file, checks each file against its manifest, writes the ZIP archives in a temporary folder, checks that every file exists with a unique name and that the [metadata](#metadata) matches, and reads the token.

Then it creates the draft, logs its address, and uploads the files one by one. It waits up to an hour for Zenodo to confirm each upload, and up to a minute for other requests. At the end it logs the address of the draft again. If an upload fails, the draft stays on Zenodo with the files already uploaded: delete it from its address in the log, and run the script again.

## The project's release process

Maintainers release a version of the code on GitHub, which also publishes the [Docker image](docker.md), and then publish the forecasts and models on Zenodo with `publish.py`. The steps are in [CONTRIBUTING.md](https://github.com/open-energy-transition/demandcast/blob/main/CONTRIBUTING.md#releasing).

## Troubleshooting

The other errors name their fix, such as `The forecasts ... have no manifest`.

| Error | Cause and fix |
|---|---|
| `The zenodo_record must be the number of a version of your record` | `zenodo_record` is empty, a quoted number, or a word other than `new`. |
| `Input should be a valid string` for `version` | Quote the version: `version: "2.1"`. |
| `The file ... has the electricity demand` | Remove the file ([why](#what-a-release-can-never-contain)). |
| `The file ... differs from the one that its manifest records` | Use the original file, or make it again. |
| `The results ... are not those of the model of the release` | Put the result in a folder with its own model. |
| `The metadata of the release does not match it` | Update `metadata.yaml` as the message says ([checks](#metadata)). |
| `The ... API key is not set` | Add `ZENODO_API_KEY`, or `SANDBOX_ZENODO_API_KEY` with `sandbox: true`, to `.env`. |
| `Zenodo ... failed (403)` or `(401)` | The token is wrong, expired, lacks the scopes, or belongs to the other site (Zenodo or Sandbox). |
| `Zenodo new version creation failed` | The record number is wrong, not yours, or a concept number rather than a version. |
