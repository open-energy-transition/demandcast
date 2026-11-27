"""
License: AGPL-3.0.

Description:

    This module copies the files of the data folder to a bucket of
    Google Cloud Storage, or the files of the bucket to the data folder,
    with the same paths. A copy only adds the files that are missing at
    the destination: it never overwrites or deletes a file there. It can
    be limited to some folders, such as "assembled" to download only
    the assembled data.

    A file at the same path at both ends is compared by its size and its
    CRC32C checksum, which Cloud Storage keeps for each object. An
    identical file is skipped, and a different one is reported in the
    log, and left as it is at both ends, for its user to decide.

    The bucket is private: Cloud Storage reads the credentials of the
    user, from "gcloud auth application-default login".
"""

import base64
import dataclasses
import logging
import os
import pathlib
import re
import uuid
from collections.abc import Iterable
from typing import Any, Literal

import google_crc32c
from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

# The size of the blocks of a file whose checksum is computed.
_BLOCK_SIZE = 1024 * 1024

# The temporary file of a download, which an interrupted download leaves
# next to the file.
_TEMPORARY_FILE = re.compile(r"\.[0-9a-f]{32}\.part$")


@dataclasses.dataclass
class SyncReport:
    """
    The files of a copy.

    Attributes
    ----------
    copied : list[str]
        The paths of the files copied, or to copy in a dry run.
    identical : list[str]
        The paths of the files that are identical at both ends.
    different : list[str]
        The paths of the files that differ, left as they are.
    unsafe : list[str]
        The names of the objects that are not paths inside the data
        folder, which are not downloaded.
    """

    copied: list[str] = dataclasses.field(default_factory=list)
    identical: list[str] = dataclasses.field(default_factory=list)
    different: list[str] = dataclasses.field(default_factory=list)
    unsafe: list[str] = dataclasses.field(default_factory=list)


def get_checksum(file_path: str) -> str:
    """
    Get the CRC32C checksum of a file, as Cloud Storage gives it.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    str
        The checksum, in base 64.
    """
    checksum = google_crc32c.Checksum()
    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(_BLOCK_SIZE), b""):
            checksum.update(block)
    return base64.b64encode(checksum.digest()).decode()


def list_local_files(
    data_folder: str, excluded_folders: Iterable[str]
) -> dict[str, str]:
    """
    List the files of the data folder by their path in the bucket.

    Parameters
    ----------
    data_folder : str
        The data folder.
    excluded_folders : Iterable[str]
        The folders of the data folder that are not copied, relative to
        it, such as "logs" or "results/figures".

    Returns
    -------
    dict[str, str]
        The path of each file on disk, by its path relative to the data
        folder, with forward slashes, which is its name in the bucket,
        without the temporary files of the downloads.

    Notes
    -----
    The folders that are symbolic links are not followed, since they
    can lead outside the data folder, or back into it, and the log
    warns of those that are not excluded.
    """
    excluded_folders = tuple(excluded_folders)
    files = {}
    linked_folders = []
    for folder, folder_names, file_names in os.walk(data_folder):
        relative_folder = os.path.relpath(folder, data_folder)
        for folder_name in folder_names:
            name = _get_name(relative_folder, folder_name)
            if os.path.islink(
                os.path.join(folder, folder_name)
            ) and not _is_in_folders(name + "/", excluded_folders):
                linked_folders.append(name)
        for file_name in file_names:
            name = _get_name(relative_folder, file_name)
            if not (
                _is_excluded(name, excluded_folders)
                or _TEMPORARY_FILE.search(file_name)
            ):
                files[name] = os.path.join(folder, file_name)
    if linked_folders:
        logging.warning(
            f"{len(linked_folders)} folders of the data folder are symbolic "
            "links, which are not followed, so their files are not "
            f"uploaded: {', '.join(sorted(linked_folders))}"
        )
    return files


def _get_name(relative_folder: str, file_name: str) -> str:
    """
    Get the name in the bucket of a file or folder of the data folder.

    Parameters
    ----------
    relative_folder : str
        The folder of the file, relative to the data folder.
    file_name : str
        The name of the file or folder.

    Returns
    -------
    str
        The path of the file relative to the data folder, with forward
        slashes.
    """
    return os.path.normpath(os.path.join(relative_folder, file_name)).replace(
        os.sep, "/"
    )


def _is_in_folders(name: str, folders: Iterable[str]) -> bool:
    """
    Tell whether a file is in one of some folders.

    Parameters
    ----------
    name : str
        The path of the file relative to the data folder, with forward
        slashes, which is its name in the bucket.
    folders : Iterable[str]
        The folders, relative to the data folder, such as "assembled" or
        "results/forecasts".

    Returns
    -------
    bool
        Whether the file is in one of the folders, or in their
        subfolders.
    """
    return any(name.startswith(folder.strip("/") + "/") for folder in folders)


def _is_excluded(name: str, excluded_folders: Iterable[str]) -> bool:
    """
    Tell whether an object of the bucket is outside the copied files.

    Parameters
    ----------
    name : str
        The name of the object.
    excluded_folders : Iterable[str]
        The folders of the data folder that are not copied, relative to
        it.

    Returns
    -------
    bool
        True for a folder placeholder, whose name ends with "/", and for
        the objects of the excluded folders.
    """
    return name.endswith("/") or _is_in_folders(name, excluded_folders)


def _is_included(name: str, included_folders: Iterable[str] | None) -> bool:
    """
    Tell whether a file is in the folders to copy.

    Parameters
    ----------
    name : str
        The path of the file relative to the data folder, with forward
        slashes, which is its name in the bucket.
    included_folders : Iterable[str] | None
        The folders to copy, relative to the data folder, such as
        "assembled" or "results/forecasts", or None for all of them.

    Returns
    -------
    bool
        True if the file is in one of the folders, or if all of them are
        copied.
    """
    if included_folders is None:
        return True
    return _is_in_folders(name, included_folders)


def get_local_path(data_folder: str, name: str) -> str | None:
    """
    Get the path in the data folder of an object of the bucket.

    Parameters
    ----------
    data_folder : str
        The data folder.
    name : str
        The name of the object.

    Returns
    -------
    str | None
        The path of the file, or None if the name is not a relative path
        with forward slashes, or if the path leads outside the data
        folder, such as through a symbolic link.
    """
    parts = name.split("/")
    if (
        "\\" in name
        or re.match(r"^[A-Za-z]:", name)
        or any(part in ("", ".", "..") for part in parts)
    ):
        return None
    file_path = os.path.join(data_folder, *parts)
    if not pathlib.Path(os.path.realpath(file_path)).is_relative_to(
        os.path.realpath(data_folder)
    ):
        return None
    return file_path


def _is_identical(file_path: str, blob: Any) -> bool:
    """
    Tell whether a file and an object of the bucket are identical.

    Parameters
    ----------
    file_path : str
        The path of the file.
    blob : google.cloud.storage.Blob
        The object, with its size and checksum.

    Returns
    -------
    bool
        Whether the size and the checksum are the same.
    """
    return os.path.getsize(file_path) == blob.size and (
        get_checksum(file_path) == blob.crc32c
    )


def _upload(blob: Any, file_path: str) -> bool:
    """
    Upload a file, unless the object exists.

    Parameters
    ----------
    blob : google.cloud.storage.Blob
        The object to write.
    file_path : str
        The path of the file.

    Returns
    -------
    bool
        Whether the file was uploaded, False if the object was written
        in the meantime.

    Notes
    -----
    Cloud Storage writes the object only if it does not exist
    (if_generation_match=0), so an object that another copy has just
    written is not overwritten.
    """
    try:
        blob.upload_from_filename(file_path, if_generation_match=0)
    except PreconditionFailed:
        return False
    return True


def _download(blob: Any, file_path: str) -> bool:
    """
    Download an object, unless the file exists.

    Parameters
    ----------
    blob : google.cloud.storage.Blob
        The object to read.
    file_path : str
        The path of the file.

    Returns
    -------
    bool
        Whether the object was downloaded, False if the file was written
        in the meantime, or if a file has the name of one of its
        folders, such as the file of an object "a" for the object "a/b".

    Notes
    -----
    The object is downloaded to a temporary file, which is then given
    the path without overwriting a file written there in the meantime
    (see _name_without_overwriting).
    """
    if os.path.exists(file_path):
        return False
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        return False
    temporary_path = f"{file_path}.{uuid.uuid4().hex}.part"
    try:
        with open(temporary_path, "xb") as file:
            blob.download_to_file(file)
        _name_without_overwriting(temporary_path, file_path)
    except FileExistsError:
        return False
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
    return True


def _name_without_overwriting(temporary_path: str, file_path: str) -> None:
    """
    Give a complete file its path, unless a file has it.

    Parameters
    ----------
    temporary_path : str
        The path of the complete file.
    file_path : str
        Its final path.

    Raises
    ------
    FileExistsError
        If a file has the path.

    Notes
    -----
    A hard link to the path fails if a file has it, even one written a
    moment before. File systems without hard links, such as exFAT and
    some network shares, refuse the link, so the file is renamed
    instead, if no file has the path: the rename fails on Windows if
    one is written in the meantime, and overwrites it elsewhere.
    """
    try:
        os.link(temporary_path, file_path)
    except FileExistsError:
        raise
    except OSError:
        if os.path.lexists(file_path):
            raise FileExistsError(file_path) from None
        os.rename(temporary_path, file_path)


def _copy(
    bucket: Any,
    blobs: dict[str, Any],
    local_files: dict[str, str],
    data_folder: str,
    direction: Literal["upload", "download"],
    name: str,
) -> bool:
    """
    Copy a file that is missing at the destination.

    Parameters
    ----------
    bucket : google.cloud.storage.Bucket
        The bucket.
    blobs : dict[str, google.cloud.storage.Blob]
        The objects of the bucket, by name.
    local_files : dict[str, str]
        The paths of the files of the data folder, by their name in the
        bucket.
    data_folder : str
        The data folder.
    direction : str
        "upload" or "download".
    name : str
        The name of the file in the bucket.

    Returns
    -------
    bool
        Whether the file was copied, False if it was written at the
        destination in the meantime.
    """
    if direction == "upload":
        return _upload(bucket.blob(name), local_files[name])
    return _download(blobs[name], str(get_local_path(data_folder, name)))


def sync(
    bucket_name: str,
    direction: Literal["upload", "download"],
    data_folder: str,
    excluded_folders: Iterable[str] = ("logs",),
    dry_run: bool = False,
    client: Any = None,
    included_folders: Iterable[str] | None = None,
) -> SyncReport:
    """
    Copy the missing files to the bucket or to the data folder.

    Parameters
    ----------
    bucket_name : str
        The name of the bucket.
    direction : str
        "upload" to copy the files of the data folder to the bucket, or
        "download" to copy the files of the bucket to the data folder.
    data_folder : str
        The data folder.
    excluded_folders : Iterable[str], optional
        The folders of the data folder that are not copied.
    dry_run : bool, optional
        Whether to only list the files to copy in the log, one a line,
        without copying them.
    client : google.cloud.storage.Client, optional
        The client of Cloud Storage, by default one with the credentials
        of the user.
    included_folders : Iterable[str] | None, optional
        The only folders to copy, relative to the data folder, such as
        "assembled" or "results/forecasts", or None to copy all the
        folders that are not excluded.

    Returns
    -------
    SyncReport
        The files copied, identical and different.
    """
    excluded_folders = tuple(excluded_folders)
    if included_folders is not None:
        included_folders = tuple(included_folders)
    bucket = (client or storage.Client()).bucket(bucket_name)
    local_files = {
        name: file_path
        for name, file_path in list_local_files(
            data_folder, excluded_folders
        ).items()
        if _is_included(name, included_folders)
    }
    blobs = {
        blob.name: blob
        for blob in bucket.list_blobs()
        if not _is_excluded(blob.name, excluded_folders)
        and _is_included(blob.name, included_folders)
    }
    report = SyncReport()

    if direction == "upload":
        sources, destinations = local_files, blobs
    else:
        sources, destinations = blobs, local_files

    for name in sorted(sources):
        if direction == "download" and (
            get_local_path(data_folder, name) is None
        ):
            report.unsafe.append(name)
            continue
        if name in destinations:
            file_path = local_files[name]
            if _is_identical(file_path, blobs[name]):
                report.identical.append(name)
            else:
                report.different.append(name)
            continue

        if dry_run or _copy(
            bucket, blobs, local_files, data_folder, direction, name
        ):
            report.copied.append(name)
        else:
            report.different.append(name)

    _log_report(report, bucket_name, direction, dry_run)
    return report


def _log_report(
    report: SyncReport,
    bucket_name: str,
    direction: Literal["upload", "download"],
    dry_run: bool,
) -> None:
    """
    Write the files of a copy in the log.

    Parameters
    ----------
    report : SyncReport
        The files of the copy.
    bucket_name : str
        The name of the bucket.
    direction : str
        "upload" or "download".
    dry_run : bool
        Whether the files were only listed, each on its own line.
    """
    logging.info(
        f"{'Would copy' if dry_run else 'Copied'} {len(report.copied)} "
        f"files {'to' if direction == 'upload' else 'from'} "
        f"gs://{bucket_name}, and skipped {len(report.identical)} "
        "identical files."
    )
    if dry_run:
        for name in report.copied:
            logging.info(f"Would copy {name}")
    if report.different:
        logging.warning(
            f"{len(report.different)} files differ between the data folder "
            f"and gs://{bucket_name} and were left as they are at both "
            f"ends: {', '.join(report.different)}"
        )
    if report.unsafe:
        logging.warning(
            f"{len(report.unsafe)} objects of gs://{bucket_name} are not "
            "paths inside the data folder and were not downloaded: "
            f"{', '.join(report.unsafe)}"
        )
