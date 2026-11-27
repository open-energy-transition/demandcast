# Publish a release on Zenodo

`publish.py` uploads a release of DemandCast to [Zenodo](https://zenodo.org/), an open repository for research data: the trained model, its forecasts, the inputs of the forecasts, and the results of its validation. You need it only if you maintain a Zenodo record of DemandCast results.

The script never publishes anything by itself. It creates a **draft** on Zenodo, which you check and publish on the Zenodo website.

## What a release is

A Zenodo **record** is a dataset page with a DOI, a permanent identifier for citing it. A record can have several **versions**. All versions share one "concept" DOI that always points to the latest version, and each version also has its own DOI. The released DemandCast forecasts are at [10.5281/zenodo.18374351](https://doi.org/10.5281/zenodo.18374351).

A release usually contains:

| File | What it holds |
|---|---|
| `xgboost_model_<time>.json` | The trained model that made the forecasts |
| `forecasts_on_historical_period.parquet` | The hourly forecasts, made from your forecasts file at the upload (see [The forecasts file](#the-forecasts-file)) |
| `assembled_data_for_forecasting_<time>.parquet` | The inputs of the forecasts at each hour |
| `validation.zip` | The model trained without the most recent year of each country and subdivision, and its errors on that year |
| `cross_validation.zip` | The errors of each country or subdivision left out of the training in turn, and the model of each fold |
| `<name>.manifest.json` | The [manifest](../concepts/glossary.md#manifest) of each file, added automatically |
| `README.md` | The files, how to reproduce them, and the sources, licences and attributions of the inputs, added automatically |

### What a release can never contain

A release cannot contain the historical electricity demand: the licences of many data sources forbid redistributing it. The script stops before uploading anything if a file:

- is inside the `electricity_demand/` folder of the data folder;
- has a name starting with `assembled_data_for_training_` (the training data, and its `_coverage.csv` and `_provenance.csv` files);
- has a name starting with `predictions_` (the hourly predictions of a validation or cross-validation, which hold the actual demand of each hour).

The assembled data for forecasting is fine: it has the inputs of the model, without the demand.

## Before you start

1. **Create a Zenodo token.** On Zenodo, open your account settings, then *Applications* → *Personal access tokens*, and create a token with the scopes `deposit:write` and `deposit:actions`.
2. **Add it to `.env`** in the `demandcast/` folder (see [Install](../getting-started/install.md#3-add-your-api-keys)):

    ```bash
    ZENODO_API_KEY=<your_token>
    ```

3. **Prepare the files.** Train the model, forecast, validate and cross-validate, so that each file has its manifest. See [Train and validate](train-validate.md), [Cross-validate](cross-validate.md) and [Forecast](forecast.md).
4. **Update the release metadata** in `demandcast/publishing/release/metadata.yaml` (see [Metadata](#metadata)).

The token is sent only to Zenodo's address, in the `Authorization` header of each request. When a request cannot be sent, the error gives only the type of the failure, so the token does not end up in a log or a traceback.

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

    The folder names `with_...` and `using_...` contain the names of the model and of the assembled data, so a folder such as `using_assembled_data_for_training_...` is fine: only the names of the files are checked for the training data.

2. From the `demandcast/` folder, run:

    ```bash
    uv run publish.py
    ```

    or, with your own settings file:

    ```bash
    uv run publish.py --config config/my_release.yaml
    ```

3. Open the log, `data/logs/publication_YYYYMMDD_HHMMSS.log`. It gives the address of the draft. The script prints nothing in the terminal unless it fails.
4. Check the draft on Zenodo, and publish it there (see [Check the draft](#check-the-draft-before-you-publish)).

## Options

The options are in `config/publish_config.yaml`.

| Option | Required? | Default | What it does |
|---|---|---|---|
| `zenodo_record` | Yes | — | The number of **one version** of your record, as in `https://zenodo.org/records/<number>`. The release becomes a new version of that record. Write `new` to create a new record instead. |
| `version` | Yes | — | The version of the release, such as `"2.1.0"`. Quote it: YAML reads `2.1` as a number, which the script rejects. The release metadata must name this version (see [Metadata](#metadata)). |
| `files` | Yes | `[]` (must not be empty) | The files uploaded as they are: usually the trained model, its forecasts and the assembled data for forecasting. Paths are relative to the data folder, unless absolute. |
| `folders` | No | `{}` | Groups of files, each uploaded as one ZIP archive named after its group, such as `validation` → `validation.zip`. Names may contain only letters, digits, `_` and `-`, and each group needs at least one file. Paths are relative to the data folder, unless absolute. |
| `metadata_file` | No | `oet_zenodo_metadata.yaml` | The file in `config/` with the creators and contributors of a **new** record. Ignored for a new version, which keeps those of the record. |
| `sandbox` | No | `false` | `true` uses the [Zenodo Sandbox](https://sandbox.zenodo.org/), a test copy of Zenodo, with the token in `SANDBOX_ZENODO_API_KEY`. |

!!! warning "Use the number of a version, not the concept DOI"
    `zenodo_record` is the number in the address of one version, such as `18374352`. The number in the concept DOI (`10.5281/zenodo.18374351`) is not a version. Write the number without quotes: a quoted number, such as `"18374352"`, is rejected.

## Files and folders

### Manifests are added for you

For each file, the script checks it against its manifest and uploads the manifest next to it:

- A file whose content differs from the checksum in its manifest stops the release.
- A file without a manifest is uploaded anyway, with a warning in the log. The summaries (`summary_<time>.csv`) and the archive of the cross-validation models (`models_<time>.zip`) have no manifest of their own: the manifest of the results (`all_<time>`) records their checksums. These warnings are expected.
- The CSV and Parquet files of the same results share one manifest, which is uploaded once.
- If the list includes a model, every result in the same list (the files of `files`, or the files of one folder) must come from that model, according to its manifest. Otherwise the release stops. This is why the validation model goes in the `validation` folder, with its results, and not in `files`.

### The forecasts file

The forecasts that `forecast.py` writes have the inputs of the model at each hour. The script replaces them with a compact file, `forecasts_on_historical_period.parquet`, with three columns:

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` | The end of the hour, in UTC | — |
| `Entity code` | The code of the country or subdivision, such as `FRA` or `USA_CAL` | — |
| `Forecast load (MW)` | The forecast demand of the hour | MW |

This name and these columns are those of the first DemandCast release, which other tools, such as PyPSA-Earth, download. The inputs of each hour are in the assembled data for forecasting, which you can add to `files`.

The compact file gets its own manifest. It names the model, the assembled data and the units of the forecasts, and the name, checksum and code version of the forecasts file it comes from.

The script recognises the forecasts as the Parquet file in `files` whose manifest says it holds forecasts. Rules:

- The forecasts must have their manifest. Forecasts without one, in `results/forecasts/`, stop the release: they cannot be checked or made compact. Forecast again with `forecast.py`, which writes it.
- `files` can contain only one forecasts file.
- Only `files` is converted. Forecasts listed in `folders` are archived as they are.

### Folders become ZIP archives

Zenodo has no folders. Each entry of `folders` becomes one ZIP archive, named after the entry, with the files and their manifests inside a folder of the same name: `validation.zip` holds `validation/all_<time>.parquet`, and so on. Zenodo shows the files of an archive in its preview.

Two files with the same name cannot go in the same archive, and two files of the release cannot have the same name.

### The README

Every release also gets `demandcast/publishing/release/README.md`. It describes the files, how to reproduce the forecasts and the errors, and the sources, licences and attributions of the inputs. Update it when the content of a release changes, for example when a new input is added.

## Metadata

The title, description, keywords and related links of the release are in `demandcast/publishing/release/metadata.yaml`. Edit this file by hand for each release: the description names the files and gives the errors of the model. It must have exactly the keys `title`, `description`, `keywords` and `related_identifiers`.

Before anything is uploaded, the script checks the metadata against the release, and stops with the list of what does not match:

| Check | What passes | What fails |
|---|---|---|
| The version is named | `version` appears in a link to its tag (`releases/tag/v2.1.0`) or after "DemandCast" (`DemandCast 2.1.0`) | Neither form names the version |
| No other version is named | Only `version` appears in these two forms. Other mentions, such as "Changes from version 1.0.0", are not checked. | Another version in one of these forms, such as a link to an older tag |
| Every file named exists | Every file name ending in `.parquet`, `.json`, `.zip`, `.md` or `.csv`, such as `xgboost_model_20261103_143736.json` or `validation.zip`, is the name of an uploaded file | A name with an old timestamp, or a file you did not upload |

Names inside links, and `.manifest.json` on its own, are not checked. When you train or forecast again, update the timestamps in the file names of the description.

### New version or new record

| | New version (`zenodo_record: <number>`) | New record (`zenodo_record: new`) |
|---|---|---|
| DOI | Zenodo assigns a new DOI to the version when you publish it. The concept DOI stays the same. | Zenodo assigns a new DOI and a new concept DOI. |
| Title, description, keywords, related links | From `metadata.yaml` | From `metadata.yaml` |
| Creators, contributors, communities | Kept from the record | Creators and contributors from `metadata_file` |
| Other metadata | Kept from the record. Dates without a start or end are dropped, because Zenodo rejects them in a draft. | Upload type `dataset`, open access, licence CC BY 4.0, language English |
| `version` | From the settings | From the settings |
| Publication date | Today, by your computer's clock | Not set by the script |
| Files | None from the previous version. Zenodo copies them into the draft; the script removes them. The previous version keeps its files. | Only the uploaded ones |

The default `metadata_file`, `config/oet_zenodo_metadata.yaml`, lists the creators (name, affiliation, ORCID) and contributors (name and role, such as `HostingInstitution` or `Sponsor`) of Open Energy Transition's records. For your own record, copy it, change the people, and set `metadata_file` to the copy's name.

## Test on the Zenodo Sandbox

The [Zenodo Sandbox](https://sandbox.zenodo.org/) is a separate copy of Zenodo for tests. Its records are not real, and it has its own accounts and tokens.

1. Create an account and a token on the sandbox.
2. Add the token to `.env`:

    ```bash
    SANDBOX_ZENODO_API_KEY=<your_sandbox_token>
    ```

3. Create a record there, or use `zenodo_record: new`.
4. Set `sandbox: true`, and run `uv run publish.py`.

## Check the draft before you publish

Open the address of the draft from the log, and check:

- **Files**: every expected file is there, with a plausible size, including `README.md` and the manifests. No file of the previous version is left.
- **ZIP archives**: the preview of `validation.zip` and `cross_validation.zip` lists the expected files.
- **Metadata**: the title, the version, the description (file names, errors, coverage) and the related links.
- **Creators and licence**, for a new record.

Then click *Publish*.

!!! warning
    On Zenodo, a published version's files cannot be changed or removed. Check them carefully first. You can still edit the metadata afterwards.

## What happens, step by step

The script stops at the first problem. Everything up to step 6 happens on your computer, before anything is sent to Zenodo.

1. It checks the settings.
2. It checks that no file holds the electricity demand.
3. It makes the compact forecasts file, and checks each file against its manifest.
4. It writes the ZIP archive of each folder, in a temporary folder.
5. It checks that every file exists, that no two files share a name, and that the metadata matches the release.
6. It reads the token.
7. It creates the draft, and writes its address in the log.
8. It uploads the files one by one. It waits up to an hour for Zenodo to confirm each upload, and up to a minute for other requests.
9. It writes the address of the draft in the log again.

If an upload fails, the draft stays on Zenodo with the files already uploaded. Open its address from the log, delete the draft, and run the script again.

## The project's release process

Maintainers release a version of the code on GitHub, which also publishes the [Docker image](docker.md), and then publish the forecasts and models on Zenodo with `publish.py`. The steps are in [CONTRIBUTING.md](https://github.com/open-energy-transition/demandcast/blob/main/CONTRIBUTING.md#releasing).

## Troubleshooting

| Error | Cause and fix |
|---|---|
| `The zenodo_record must be the number of a version of your record` | `zenodo_record` is empty, a quoted number, or a word other than `new`. |
| `Input should be a valid string` for `version` | YAML read the version as a number. Quote it: `version: "2.1"`. |
| `The files of the release must be given` | `files` is empty. |
| `The file ... has the electricity demand` | Remove the file from the release (see [What a release can never contain](#what-a-release-can-never-contain)). |
| `The file ... differs from the one that its manifest records` | The file was changed or replaced after its manifest was written. Use the original file, or make it again. |
| `The results ... are not those of the model of the release` | A result in the list comes from another model. Put it in a folder with its own model. |
| `The forecasts ... have no manifest` | Forecast again with `forecast.py`. |
| `The release has several files of forecasts` | Keep one forecasts file in `files`. |
| `The metadata of the release does not match it` | Update `publishing/release/metadata.yaml`: the message lists the missing version, other versions, or file names. |
| `The Zenodo API key is not set` | Add `ZENODO_API_KEY` (or `SANDBOX_ZENODO_API_KEY` with `sandbox: true`) to `.env`. |
| `Zenodo ... failed (403)` or `(401)` | The token is wrong, expired, lacks the scopes, or belongs to the other site (Zenodo vs. Sandbox). |
| `Zenodo new version creation failed` | The record number is wrong or not yours, or it is a concept number rather than a version. |
