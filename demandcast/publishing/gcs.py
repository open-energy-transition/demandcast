"""
License: AGPL-3.0.

Description:

    This module copies the files of the data folder to a bucket of
    Google Cloud Storage, or the files of the bucket to the data folder,
    with the same paths. A copy only adds the files that are missing at
    the destination: it never overwrites or deletes a file there.

    A file at the same path at both ends is compared by its size and its
    CRC32C checksum, which Cloud Storage keeps for each object. An
    identical file is skipped, and a different one is reported in the
    log, and left as it is at both ends, for its user to decide.

    An upload asks Cloud Storage to write an object only if it does not
    exist (if_generation_match=0), so a file that another copy has just
    written is not overwritten either, and a download creates its file
    only if it does not exist.

    The bucket is private: Cloud Storage reads the credentials of the
    user, from "gcloud auth application-default login".
"""

import base64
import dataclasses
import logging
import os
import re
import uuid
from collections.abc import Iterable
from typing import Any, Literal

import google_crc32c
from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

# The size of the blocks of a file whose checksum is computed.
_BLOCK_SIZE = 1024 * 1024


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
        The folders of the data folder that are not copied, such as
        "logs".

    Returns
    -------
    dict[str, str]
        The path of each file on disk, by its path relative to the data
        folder, with forward slashes, which is its name in the bucket.
    """
    excluded = set(excluded_folders)
    files = {}
    for folder, subfolders, file_names in os.walk(data_folder):
        relative_folder = os.path.relpath(folder, data_folder)
        if relative_folder == ".":
            subfolders[:] = [
                name for name in subfolders if name not in excluded
            ]
        for file_name in file_names:
            relative_path = os.path.normpath(
                os.path.join(relative_folder, file_name)
            )
            files[relative_path.replace(os.sep, "/")] = os.path.join(
                folder, file_name
            )
    return files


def _is_excluded(name: str, excluded_folders: Iterable[str]) -> bool:
    """
    Tell whether an object of the bucket is outside the copied files.

    Parameters
    ----------
    name : str
        The name of the object.
    excluded_folders : Iterable[str]
        The folders of the data folder that are not copied.

    Returns
    -------
    bool
        True for a folder placeholder, whose name ends with "/", and for
        the objects of the excluded folders.
    """
    return name.endswith("/") or name.split("/", maxsplit=1)[0] in set(
        excluded_folders
    )


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
    root = os.path.realpath(data_folder)
    if os.path.commonpath([os.path.realpath(file_path), root]) != root:
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
        in the meantime.
    """
    if os.path.exists(file_path):
        return False
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temporary_path = f"{file_path}.{uuid.uuid4().hex}.part"
    try:
        with open(temporary_path, "xb") as file:
            blob.download_to_file(file)
        # The link fails if the file was written in the meantime.
        os.link(temporary_path, file_path)
    except FileExistsError:
        return False
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
    return True


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
        Whether to only list the files to copy, without copying them.
    client : google.cloud.storage.Client, optional
        The client of Cloud Storage, by default one with the credentials
        of the user.

    Returns
    -------
    SyncReport
        The files copied, identical and different.
    """
    excluded_folders = tuple(excluded_folders)
    bucket = (client or storage.Client()).bucket(bucket_name)
    local_files = list_local_files(data_folder, excluded_folders)
    blobs = {
        blob.name: blob
        for blob in bucket.list_blobs()
        if not _is_excluded(blob.name, excluded_folders)
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

    logging.info(
        f"{'Would copy' if dry_run else 'Copied'} {len(report.copied)} "
        f"files {'to' if direction == 'upload' else 'from'} "
        f"gs://{bucket_name}, and skipped {len(report.identical)} "
        "identical files."
    )
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
    return report
