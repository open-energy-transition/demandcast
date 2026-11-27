# Share the data folder

`sync.py` copies your [data folder](../concepts/glossary.md#data-folder) to a private [bucket](../concepts/glossary.md#bucket) of Google Cloud Storage, or the bucket to your data folder. Use it to share retrieved data, models and results between people and computers without retrieving everything again.

Each file in a bucket is an **object**, named by its path. `sync.py` keeps the same paths at both ends: `data/assembled/x.parquet` becomes the object `assembled/x.parquet`, and the other way round.

## What a copy does

A copy **only adds files that are missing at the destination**. It never overwrites or deletes anything, so copies from several people complement each other and no one can erase someone else's work.

The source is the data folder for an `upload`, and the bucket for a `download`. For each file:

| Situation | What happens | Reported as |
|---|---|---|
| Only at the source | Copied to the destination | Copied |
| At both ends, same content | Nothing | Identical |
| At both ends, different content | Nothing: both versions stay | Different (a conflict) |
| Written at the destination while the copy runs | Not overwritten | Different |
| A bucket object that is not a safe path inside the data folder (see [Safe downloads](#safe-downloads)) | Not downloaded | Unsafe |

!!! note
    A copy runs in one direction. To have the same files at both ends, run an `upload` and then a `download`.

### How files are compared

A file at the same path at both ends is identical only if its **size** and its **CRC32C checksum** (a short code computed from the content) match. Cloud Storage stores the checksum of every object, so nothing is downloaded to compare. Modification times are not compared.

The script reads each local file that has the same size as its object, to compute its checksum. On a large data folder, a run takes a while even when nothing is copied.

### Files that are never copied

- The folders in `excluded_folders`, by default `logs`.
- The temporary files of an unfinished write (a dot, 32 hexadecimal characters and `.part` at the end of the name). DemandCast writes every file under such a name first ([why](../reference/data-folder.md#how-files-are-written)), so a file left by a crashed run is never uploaded.
- The empty "folder" objects that the Cloud Storage console creates, whose names end with `/`.

### Safe downloads

A download is written to a temporary `.part` file and then hard-linked to its final name. The link fails if a file appeared at that path in the meantime, so that file is not overwritten. A download that stops halfway leaves no partial file under the final name.

An upload asks Cloud Storage to write the object only if it does not exist yet, so an object that someone else uploads at the same moment is not overwritten either.

A bucket object is **unsafe**, and not downloaded, if its name is not a plain relative path inside the data folder: names with `..`, `.`, empty parts (`a//b`, a leading `/`), backslashes, a drive letter such as `C:`, or a path that leads outside the data folder through a symbolic link.

An object is also not downloaded, and is reported as different, if the data folder has a file where the object needs a folder: the object `a/b` cannot be downloaded next to a file named `a`.

## Before you start

1. Ask the owner of the bucket for access with your Google account. Keep the bucket private: the licences of many data sources forbid redistribution.
2. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
3. Log in once. This saves your credentials on your computer, where the Google Cloud client library finds them; no key goes in `.env`.

    ```bash
    gcloud auth application-default login
    ```

To run `sync.py` in Docker, see [Docker](docker.md#copy-the-data-folder-to-or-from-a-bucket).

## Run a copy

1. Set the direction and your bucket in `config/sync_config.yaml`, or in a copy of it:

    ```yaml
    direction: download
    bucket: demandcast-data
    ```

2. From the `demandcast/` folder, run `uv run sync.py`, or `uv run sync.py --config config/my_sync_config.yaml` for your own file.
3. Read the log (see [Read the result](#read-the-result)). The terminal shows nothing unless the script fails.

!!! tip
    Start with `dry_run: true` to count the files that the copy would add, without copying anything.

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `direction` | Yes | — | `upload` copies the data folder to the bucket; `download` copies the bucket to the data folder. Lowercase only. |
| `bucket` | Yes | empty | The name of your bucket, such as `demandcast-data`, without `gs://`. The script stops while it is empty. |
| `excluded_folders` | No | `[logs]` | Folders of the data folder that are never copied, such as `logs` or `results/figures`, with their subfolders |
| `included_folders` | No | empty (all folders) | The only folders to copy, such as `assembled` or `results/forecasts`, with their subfolders |
| `dry_run` | No | `false` | `true` counts the files that a copy would add, without copying them. Differences and unsafe objects are still listed by name. |

### Choose the folders to copy

A file is copied only if it is in one of the `included_folders` (when you give some) **and** in none of the `excluded_folders`: an exclusion always wins. For example, to download only the assembled data and the forecasts:

```yaml
direction: download
bucket: demandcast-data
included_folders:
  - assembled
  - results/forecasts
```

Folder names are relative to the data folder and match whole folders: `assembled` matches `assembled/x.parquet`, not `assembled_old/x.parquet`. Use forward slashes, also on Windows; a leading or trailing `/` is ignored. The [data folder reference](../reference/data-folder.md#the-tree) lists the folders.

!!! warning "Empty lists"
    - `included_folders: []` copies **nothing**. Leave the option empty (`included_folders:`) to copy every folder.
    - `excluded_folders:` left empty stops the script with a validation error. Write `excluded_folders: []` to exclude nothing.

## Read the result

Each run writes `logs/sync_upload_<time>.log` or `logs/sync_download_<time>.log` in the data folder. It gives:

- the settings;
- the number of files copied (or that would be copied, in a dry run) and of identical files skipped;
- a warning with the paths of the files that differ, if any;
- a warning with the names of the unsafe objects, if any.

The script exits with status **1** if any file differs or any object is unsafe, also in a dry run, and **0** otherwise. A scheduled copy, such as a cron job, can use this status to alert you.

## Resolve a conflict

A conflict is a file that differs between the two ends, such as a cleaned file computed again with newer code. `sync.py` keeps both, so you choose:

1. Find the paths in the warning of the log.
2. Compare the two versions. For an assembled dataset, a model or a result, its [manifest](../reference/data-folder.md#manifests) tells which code and inputs made it.
3. Remove the version you do not want:
    - to keep the bucket's version, move or delete your local file, then run a `download`;
    - to keep yours, delete the object, for example with `gcloud storage rm gs://<bucket>/<path>`, then run an `upload`.

!!! warning "Resolve a file together with its manifest"
    A file and its manifest must come from the same run, or the scripts stop when they check the file. Remove both, then copy both.

Each data source has one index of its raw data, `electricity_demand/raw/<source>/manifest.json`. If two computers retrieve the same source, this file differs at the two ends. Choose one computer's raw data as the reference for each source.

## After a download

The scripts check downloaded files by their content, so no extra step is needed:

- Manifest paths are relative to the data folder, and the scripts check each file against the checksum in its manifest, which a faithful copy keeps.
- The combined electricity demand records a [fingerprint](../concepts/glossary.md#fingerprint) of the code, reviews and source files that made it. If yours differ, or the combined file is older than the cleaned data of its sources, `assemble.py` combines it again (see [Electricity demand](../concepts/electricity-demand.md#when-the-combination-runs-again)).
- Temperature files record the fingerprint of their shape, and grids the bounds of their shape. A file made with another shape is computed again.

Some checks use the time a file was written, which for a downloaded file is the time of the download:

- A reanalysis weather file of a past year whose data ends before 31 December is retrieved again, but not until a day after the download.
- The grids of each code are extracted again from a global weather grid that is newer. A download writes `gridded_weather/processed/` before `gridded_weather/raw/` (alphabetical order), so the first retrieval after a full download extracts them again. This takes time but downloads nothing.
- A temperature file of a year counts as complete if it was written more than seven days after that year ended. So a temperature file made elsewhere while its year was in progress looks complete after a download. Delete it to compute it again.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `The bucket must be given` | Set `bucket` to the name of your bucket. |
| `Input should be 'upload' or 'download'` | `direction` has another value, or capital letters. |
| An error about credentials or the default project | Run `gcloud auth application-default login`. |
| `403` or `Forbidden` | Your Google account has no access to the bucket. Ask its owner. |
| `Copied 0 files` | Everything is already there, `included_folders` is an empty list, or the folder names do not match (spelling, forward slashes). |
| Exit status 1 | Some files differ or some objects are unsafe. Read the warnings in the log. |
| A folder of the data folder is never uploaded | It is a symbolic link to a folder. The script does not follow linked folders, and does not download into them. Point `DEMANDCAST_DATA_FOLDER` to the real folder. |
| A download fails with an `OSError` about links | The file system has no hard links (such as FAT32 or exFAT). Use another disk for the data folder. |
