# Sharing and publishing

DemandCast keeps the retrieved data in a private bucket of Google Cloud Storage, to share it between the people who work on it and their computers, and publishes on Zenodo only its trained models and their forecasts: the licences of many data sources do not allow their data to be redistributed.

## Copying the data folder to and from a bucket

`sync.py` copies the data folder (see [architecture](architecture.md#data-folder)) to a bucket, or the bucket to the data folder, with the same paths. A copy only adds the files that are missing at the destination: it never overwrites or deletes a file there, so the copies of several people and computers complement each other.

A file at the same path at both ends is compared by its size and its CRC32C checksum. An identical file is skipped, and a file that differs, such as a cleaned file computed again with a newer version of the code, is left as it is at both ends and listed in the log, for you to decide which one to keep. The logs are not copied.

A download is written to a temporary file and given its name only once complete, so a copy that stops leaves no partial file. An object of the bucket whose name is not a path inside the data folder, such as one with `..`, is not downloaded and is listed in the log. A weather file of a past year that ends before the year does is retrieved again a day after it was written, even when it was copied from the bucket.

The bucket should be private. Log in once with your Google account, which needs access to the bucket:

```bash
gcloud auth application-default login
```

Set your bucket and the direction in `config/sync_config.yaml`, or in a copy of it passed with `--config`:

```yaml
direction: upload        # or download
bucket: demandcast-data  # the name of your bucket
excluded_folders:
  - logs
dry_run: false           # true lists the files to copy, without copying them
```

Then, in the `demandcast` folder:

```bash
uv run sync.py
```

The bucket is empty in the configuration of the repository, so nothing is copied until you name yours.

## Publishing a release on Zenodo

`publish.py` uploads a release, the trained model, its settings and its forecasts, as a new version of a record on Zenodo, so that the DOI of all its versions stays the same (that of DemandCast is [10.5281/zenodo.18374351](https://doi.org/10.5281/zenodo.18374351)). The new version is a draft, without the files of the previous version, which stay in it: check it on the website of Zenodo, and publish it there.

Set the API key of your Zenodo account in `ZENODO_API_KEY` in the `.env` file, which `publish.py` sends only to Zenodo, in the header of its requests, (see [getting started](getting_started.md#13-configure-environment-variables)), and the release in `config/publish_config.yaml`:

```yaml
zenodo_record: 18374352  # the number of a version of your record, or "new"
version: "1.1.0"
files:                   # relative to the data folder, unless absolute
  - models/xgboost/xgboost_model_20261101_120000.json
  - results/forecasts/with_xgboost_model_20261101_120000/using_assembled_data_for_forecasting_20261101_100000/all_20261101_130000.parquet
metadata_file: oet_zenodo_metadata.yaml  # the creators of a new record
sandbox: false           # true uses sandbox.zenodo.org and SANDBOX_ZENODO_API_KEY
```

The manifest of each file (see [the manifests](ML.md#manifests)), which tells how the model was trained and which model and data gave the forecasts, is uploaded with it, and the log lists the files without one.

Then run:

```bash
uv run publish.py
```

The log gives the address of the draft. To test a release, use the [sandbox of Zenodo](https://sandbox.zenodo.org/) with `sandbox: true`, a record there, and its own key in `SANDBOX_ZENODO_API_KEY`.
