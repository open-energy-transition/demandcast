# Share the data folder

`sync.py` copies your [data folder](../concepts/glossary.md#data-folder) to a private bucket of Google Cloud Storage, or copies the bucket to your data folder. Use it to share retrieved data, models and results between people and computers without retrieving everything again.

A **bucket** is a storage container in Google Cloud Storage. Each file in it is an **object**, named by its path, such as `assembled/assembled_data_for_forecasting_20261102_201544.parquet`.

## What a copy does

`sync.py` keeps the same paths at both ends: the file `data/assembled/x.parquet` becomes the object `assembled/x.parquet`, and the other way round.

A copy **only adds files that are missing at the destination**. It never overwrites or deletes anything. This way, the copies of several people and computers complement each other, and no one can erase someone else's work by mistake.

For each file, the script does one of four things:

| Situation | What happens | Reported as |
|---|---|---|
| The file exists only at the source | It is copied to the destination | Copied |
| The file exists at both ends, with the same content | Nothing | Identical |
| The file exists at both ends, with different content | Nothing: both versions stay as they are | Different (a conflict) |
| A bucket object cannot be written safely inside the data folder | It is not downloaded | Unsafe |

The source is the data folder for an upload, and the bucket for a download.

!!! note
    The copy runs in one direction only. To end up with the same files at both ends, run an upload and then a download.

### How it decides that a file is the same

A file at the same path at both ends is compared by:

1. its **size** in bytes, and
2. its **CRC32C checksum**, a short code computed from the file's content. Cloud Storage stores this checksum for every object, so the script does not need to download the object to compare it.

The file is identical only if both match. Modification times are not compared.

The script reads every local file that also exists in the bucket to compute its checksum. On a large data folder, a run takes a while even when nothing is copied.

### Files that are never copied

- The folders in `excluded_folders`, by default `logs`.
- The temporary files of an unfinished write, whose names end with a dot, 32 hexadecimal characters and `.part`. DemandCast writes every file under such a name first and renames it once complete, so a file that a crashed run left behind is never uploaded.
- The empty "folder" objects that the Cloud Storage console creates, whose names end with `/`.

### Safe downloads

A download is written to a temporary `.part` file next to its target, and then linked to its final name. The link fails if a file appeared at that path in the meantime, so even a file written while the copy runs is not overwritten. A copy that stops halfway leaves no partial file under the final name.

An upload asks Cloud Storage to write the object only if it does not exist yet. An object that someone else uploads at the same moment is therefore not overwritten either.

A bucket object is **unsafe**, and is not downloaded, if its name is not a plain relative path inside the data folder. This covers names with `..`, `.`, empty parts (such as `a//b` or a leading `/`), backslashes, a drive letter such as `C:`, or a path that leads outside the data folder through a symbolic link.

An object is also not downloaded, and is reported as **different**, if the data folder has a file where the object needs a folder. For example, the object `a/b` cannot be downloaded next to a file named `a`.

## Before you start

1. Ask the owner of the bucket for access with your Google account. The bucket should be private, because the retrieved data comes from sources whose licences often forbid redistribution.
2. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
3. Log in once:

    ```bash
    gcloud auth application-default login
    ```

    This saves your credentials on your computer. `sync.py` reads them through the Google Cloud client library; you do not put any key in `.env`.

To run `sync.py` in Docker, see [Docker](docker.md#copy-the-data-folder-to-or-from-a-bucket).

## Run a copy

1. Set the direction and your bucket in `config/sync_config.yaml`, or in a copy of it:

    ```yaml
    direction: download
    bucket: demandcast-data
    ```

2. From the `demandcast/` folder, run:

    ```bash
    uv run sync.py
    ```

    or, with your own settings file:

    ```bash
    uv run sync.py --config config/my_sync_config.yaml
    ```

3. Read the log in `data/logs/` (see [Read the result](#read-the-result)). The script prints nothing in the terminal unless it fails.

!!! tip
    Start with `dry_run: true` to see how many files the copy would add, without copying anything.

## Options

The options are in `config/sync_config.yaml`.

| Option | Required? | Default | What it does |
|---|---|---|---|
| `direction` | Yes | — | `upload` copies the data folder to the bucket. `download` copies the bucket to the data folder. Lowercase only. |
| `bucket` | Yes | — (empty in the repository's file) | The name of your bucket, such as `demandcast-data`, without `gs://`. The script stops if it is empty, so nothing is copied until you name yours. |
| `excluded_folders` | No | `[logs]` | Folders of the data folder that are never copied, relative to it, such as `logs` or `results/figures`. Subfolders are excluded too. |
| `included_folders` | No | empty (all folders) | The only folders to copy, relative to the data folder, such as `assembled` or `results/forecasts`. Subfolders are included too. Empty copies every folder that is not excluded. |
| `dry_run` | No | `false` | `true` counts the files that a copy would add, without copying them. Conflicts and unsafe objects are still listed by name. |

### Choose the folders to copy

A file is copied only if it is inside one of the `included_folders` (when you give some) **and** not inside one of the `excluded_folders`. An exclusion always wins.

For example, to download only the assembled data and the forecasts:

```yaml
direction: download
bucket: demandcast-data
included_folders:
  - assembled
  - results/forecasts
```

To upload everything except the logs and the figures:

```yaml
direction: upload
bucket: demandcast-data
excluded_folders:
  - logs
  - results/figures
```

Folder names are prefixes of whole folders: `assembled` matches `assembled/x.parquet`, but not `assembled_old/x.parquet`. Write them with forward slashes, also on Windows. A leading or trailing `/` is ignored.

The [data folder reference](../reference/data-folder.md) lists every folder you can name.

!!! warning "Empty lists"
    - `included_folders: []` (an empty list) copies **nothing**. Leave the option empty (`included_folders:`) to copy every folder.
    - `excluded_folders:` left empty stops the script with a validation error. Write `excluded_folders: []` to exclude nothing.

## Read the result

Each run writes a log file in the data folder, `logs/sync_upload_YYYYMMDD_HHMMSS.log` or `logs/sync_download_YYYYMMDD_HHMMSS.log`, named after the direction and the local time. It has:

- the settings of the run;
- the number of files copied (or that would be copied, in a dry run) and of identical files skipped;
- a warning with the paths of the files that differ, if any;
- a warning with the names of the unsafe objects, if any.

The script exits with status **1** if any file differs or any object is unsafe, and **0** otherwise. A scheduled copy, such as a cron job, can use this status to alert you.

## Resolve a conflict

A conflict is a file that differs between the two ends, such as a cleaned file computed again with a newer version of the code. `sync.py` leaves both versions in place, so you decide which one to keep:

1. Find the paths in the warning of the log.
2. Compare the two versions. For an assembled dataset, a model or a result, its [manifest](../concepts/glossary.md#manifest) (`<name>.manifest.json`, next to the file) tells which code and inputs made it.
3. Remove the version you do not want:
    - to keep the bucket's version, move or delete your local file, then run a `download`;
    - to keep your version, delete the object in the bucket, for example with `gcloud storage rm gs://<bucket>/<path>`, then run an `upload`.

!!! warning "Resolve a file together with its manifest"
    A file and its manifest must come from the same run. If you replace only one of them, the scripts stop when they check the file against its manifest. Remove both, then copy both.

The raw electricity demand of each data source has one index file, `electricity_demand/raw/<source>/manifest.json`, that lists all its downloaded versions. If two computers retrieve the same data source, this file differs at the two ends, and `sync.py` keeps both. Choose one computer's raw data as the reference for each data source.

## After a download

The scripts check most downloaded files by their content, so a download needs no extra step:

- The paths in the [manifests](../concepts/glossary.md#manifest) are relative to the data folder, so they stay valid in a copy of it. The scripts check each assembled dataset, model and result against the checksum in its manifest, which a faithful copy keeps.
- The combined electricity demand of each country or subdivision records a fingerprint: a checksum of the cleaning code, the flag reviews, and the files and flags of its data sources. If your copy of these differs from the one that made it, or if it is older than the cleaned data of its sources, `assemble.py` combines it again from the cleaned data. See [Electricity demand](../concepts/electricity-demand.md).
- The temperature files record the fingerprint of the shape of their country or subdivision, and the grids record the bounds of that shape. A file made with another shape is computed again.

Some checks use the time a file was written, and a downloaded file has the time of the download:

- A reanalysis weather file of a past year that ends before the year does is retrieved again a day after it was written, even when it was copied from the bucket. The end of its data is read from the file.
- The grids of the countries and subdivisions are extracted again from the global weather grid when they are older than it. A download writes `gridded_weather/processed/` before `gridded_weather/raw/` (in alphabetical order), so the first retrieval after a full download extracts them again. This takes time but downloads nothing.
- A temperature file of a year is treated as complete if it was written more than seven days after that year ended. A copy gets the time of the download, so a temperature file made elsewhere while its year was still in progress looks complete. Delete it to compute it again.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `The bucket must be given` | `bucket` is empty. Set the name of your bucket. |
| `Input should be 'upload' or 'download'` | `direction` has another value, or capital letters. |
| An error about credentials or the default project | You have not logged in. Run `gcloud auth application-default login`. |
| `403` or `Forbidden` | Your Google account has no access to the bucket. Ask its owner. |
| `Copied 0 files` | Everything is already there, or `included_folders` is an empty list, or your folder names do not match (check the spelling and use forward slashes). |
| Exit status 1 | Some files differ, or some objects are unsafe. Read the warnings in the log. |
| A folder of the data folder is never uploaded | It is a symbolic link to another folder. The script does not follow linked folders when it lists the local files, and does not download into them. Point `DEMANDCAST_DATA_FOLDER` to the real folder instead. |
| A download fails with an `OSError` about links | The download links its temporary file to the final name, which needs a file system with hard links. Some file systems, such as FAT32 and exFAT, have none. Use another disk for the data folder. |
