"""
License: AGPL-3.0.

Description:

    This module writes and reads the manifests of the files that the
    scripts produce: the assembled datasets, the trained models and
    their results. A manifest is a JSON file next to its file, with the
    same name and the extension ".manifest.json", which tells what the
    file is and how it was made: its kind, the version of the code and
    of its locked dependencies, the checksum of the file and of its
    inputs, and the settings of the script, so that a model, its data
    and its results can be checked to belong together.

    The manifests have a version (MANIFEST_VERSION), which grows when
    their content changes in a way that older code cannot read.
"""

import datetime
import hashlib
import json
import os
import subprocess
from typing import Any

import utils.paths

# The version of the content of the manifests.
MANIFEST_VERSION = 1

# The extension of the manifests, after the name of their file without
# its extension.
MANIFEST_EXTENSION = ".manifest.json"

# The size of the blocks of a file whose checksum is computed.
_BLOCK_SIZE = 1024 * 1024


def get_manifest_path(file_path: str) -> str:
    """
    Get the path of the manifest of a file.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    str
        The path of its manifest, with the name of the file without its
        extension.
    """
    return os.path.splitext(file_path)[0] + MANIFEST_EXTENSION


def get_checksum(file_path: str) -> str:
    """
    Get the SHA-256 checksum of a file.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    str
        The checksum, in hexadecimal.
    """
    checksum = hashlib.sha256()
    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(_BLOCK_SIZE), b""):
            checksum.update(block)
    return checksum.hexdigest()


def get_code_version() -> dict[str, str | None]:
    """
    Get the version of the code and of its locked dependencies.

    Returns
    -------
    dict[str, str | None]
        The commit of the repository ("commit"), with "+changes" if it
        has changes that are not committed, and the checksum of the
        lock file of the dependencies ("lockfile"), None if unknown.
    """
    commit = None
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=utils.paths.CODE_FOLDER,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],  # noqa: S607
            cwd=utils.paths.CODE_FOLDER,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if changes:
            commit += "+changes"
    except (OSError, subprocess.CalledProcessError):
        # Without git, or outside a repository, such as in a copy of the
        # code, the commit is unknown, even if only its changes are.
        commit = None
    lockfile_path = os.path.join(utils.paths.CODE_FOLDER, "uv.lock")
    return {
        "commit": commit,
        "lockfile": get_checksum(lockfile_path)
        if os.path.exists(lockfile_path)
        else None,
    }


def write_manifest(file_path: str, kind: str, content: dict[str, Any]) -> str:
    """
    Write the manifest of a file.

    Parameters
    ----------
    file_path : str
        The path of the file, which must exist.
    kind : str
        The kind of the file, such as "dataset", "model" or "results".
    content : dict[str, Any]
        What the manifest tells about the file, which can be written as
        JSON, such as its settings and inputs.

    Returns
    -------
    str
        The path of the manifest.
    """
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "kind": kind,
        "file": os.path.basename(file_path),
        "sha256": get_checksum(file_path),
        "created": datetime.datetime.now(datetime.UTC).isoformat(
            timespec="seconds"
        ),
        "code": get_code_version(),
        **content,
    }
    manifest_path = get_manifest_path(file_path)
    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, default=str)
        file.write("\n")
    return manifest_path


def read_manifest(file_path: str) -> dict[str, Any] | None:
    """
    Read the manifest of a file.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    dict[str, Any] | None
        The manifest, or None if the file has none, such as a file made
        before the manifests.

    Raises
    ------
    ValueError
        If the manifest has a newer version than this code reads.
    """
    manifest_path = get_manifest_path(file_path)
    if not os.path.exists(manifest_path):
        return None
    with open(manifest_path, encoding="utf-8") as file:
        manifest = json.load(file)
    if manifest.get("manifest_version", 0) > MANIFEST_VERSION:
        raise ValueError(
            f"The manifest {manifest_path} has the version "
            f"{manifest['manifest_version']}, newer than the version "
            f"{MANIFEST_VERSION} that this code reads."
        )
    return manifest
