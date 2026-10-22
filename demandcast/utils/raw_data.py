"""
License: AGPL-3.0.

Description:

    This module keeps the raw electricity demand data: the responses of
    the websites of the data sources as they are downloaded. The data
    can then be processed again without the network, and the data that
    a data source changes or removes is not lost.

    While a request of a data source is downloaded, the responses to
    the requests that its code sends with requests or urllib are
    recorded, and so are the files downloaded manually that it reads
    (see utils.fetcher.find_manual_files), as responses to a request
    with the method FILE and the name of the file. The content of each
    response is saved once, under its checksum, in
    raw/<data source>/files/. The manifest of the data source,
    raw/<data source>/manifest.json, lists the requests of each code
    and, for each of them, the versions of its responses: a version is a
    set of responses, with the dates of the first and the last
    retrievals that downloaded it, and the error that the data source
    raised if its data could not be extracted from them, such as after
    a change of their format.

    The API keys and passwords in the URLs and the bodies of the
    requests are hidden in the manifest. The responses to the requests
    that send one in their body, such as the tickets of EPIAS, are not
    saved: when the data is processed again, they get an empty response.

    To process a version again, its responses are replayed to the code
    of the data source instead of downloads, and its files downloaded
    manually instead of those in their folder: a request without a
    saved response raises an error, so nothing is downloaded.
"""

from __future__ import annotations

import contextlib
import datetime
import email.message
import hashlib
import io
import json
import os
import shutil
import tempfile
import urllib.request
from collections.abc import Iterator
from typing import Any

import pandas as pd
import requests

import utils.config
import utils.fetcher

# The method of the requests of the files downloaded manually.
MANUAL_FILE = "FILE"


class RawDataNotFoundError(LookupError):
    """A request without a saved response, while replaying."""


def _folder(data_source: str) -> str:
    """
    Get the folder of the raw data of a data source.

    Parameters
    ----------
    data_source : str
        The data source.

    Returns
    -------
    str
        The folder.
    """
    return os.path.join(
        utils.config.read_folders_structure()["raw_electricity_demand_folder"],
        data_source,
    )


def encode_request(request: Any) -> Any:
    """
    Encode a request of a data source as JSON.

    Parameters
    ----------
    request : Any
        The request: None, a number, a string, a date, a timestamp, or a
        tuple or list of them.

    Returns
    -------
    Any
        The request with the timestamps, dates and tuples tagged.

    Raises
    ------
    TypeError
        If the request has another type.
    """
    if request is None or isinstance(request, bool | int | float | str):
        return request
    if isinstance(request, pd.Timestamp):
        return {"timestamp": request.isoformat()}
    if isinstance(request, datetime.date):
        return {"date": request.isoformat()}
    if isinstance(request, tuple):
        return {"tuple": [encode_request(item) for item in request]}
    if isinstance(request, list):
        return [encode_request(item) for item in request]
    raise TypeError(f"Cannot save a request of type {type(request)}.")


def decode_request(encoded: Any) -> Any:
    """
    Decode a request of a data source from JSON.

    Parameters
    ----------
    encoded : Any
        The request, as encode_request gives it.

    Returns
    -------
    Any
        The request.
    """
    if isinstance(encoded, list):
        return [decode_request(item) for item in encoded]
    if isinstance(encoded, dict):
        if "timestamp" in encoded:
            return pd.Timestamp(encoded["timestamp"])
        if "date" in encoded:
            return datetime.date.fromisoformat(encoded["date"])
        return tuple(decode_request(item) for item in encoded["tuple"])
    return encoded


def _body_text(body: Any) -> str | None:
    """
    Get the body of a request as text.

    Parameters
    ----------
    body : Any
        The body, as bytes, text or None.

    Returns
    -------
    str | None
        The body as text, or None if there is no body.
    """
    if body is None:
        return None
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _key(method: str, url: str, body: Any) -> tuple[str, str, str | None]:
    """
    Get the key of a request, without its API keys and passwords.

    Parameters
    ----------
    method : str
        The HTTP method.
    url : str
        The URL.
    body : Any
        The body.

    Returns
    -------
    tuple[str, str, str | None]
        The method, the URL and the checksum of the body.
    """
    text = _body_text(body)
    return (
        method.upper(),
        utils.fetcher.redact(url),
        None
        if text is None
        else hashlib.sha256(
            utils.fetcher.redact(text).encode("utf-8")
        ).hexdigest(),
    )


def _sends_secret(body: Any) -> bool:
    """
    Check whether the body of a request has an API key or a password.

    Parameters
    ----------
    body : Any
        The body.

    Returns
    -------
    bool
        True if the body has an API key or a password.
    """
    text = _body_text(body)
    return text is not None and utils.fetcher.redact(text) != text


def _save_file(data_source: str, content: bytes) -> str:
    """
    Save the content of a response once, under its checksum.

    Parameters
    ----------
    data_source : str
        The data source.
    content : bytes
        The content.

    Returns
    -------
    str
        The checksum of the content.
    """
    checksum = hashlib.sha256(content).hexdigest()
    file_path = os.path.join(_folder(data_source), "files", checksum)
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path + ".tmp", "wb") as file:
            file.write(content)
        os.replace(file_path + ".tmp", file_path)
    return checksum


class _UrlResponse(io.BytesIO):
    """A response of urllib, with its content read."""

    def __init__(
        self, content: bytes, headers: dict[str, str], status: int, url: str
    ) -> None:
        super().__init__(content)
        self.headers = email.message.Message()
        for name, value in headers.items():
            self.headers[name] = value
        self.status = status
        self.url = url

    def getcode(self) -> int:
        """
        Get the status of the response, as urllib does.

        Returns
        -------
        int
            The status.
        """
        return self.status

    def geturl(self) -> str:
        """
        Get the URL of the response, as urllib does.

        Returns
        -------
        str
            The URL.
        """
        return self.url


def _url_and_body(url: Any) -> tuple[str, Any]:
    """
    Get the URL and the body of a request of urllib.

    Parameters
    ----------
    url : Any
        The URL or the request object passed to urlopen.

    Returns
    -------
    tuple[str, Any]
        The URL and the body.
    """
    if isinstance(url, urllib.request.Request):  # noqa: S310
        return url.full_url, url.data
    return str(url), None


@contextlib.contextmanager
def recording(data_source: str) -> Iterator[list[dict[str, Any]]]:
    """
    Record the responses of the requests sent with requests or urllib.

    The files downloaded manually that the data source finds are
    recorded too.

    Parameters
    ----------
    data_source : str
        The data source, whose folder keeps the responses.

    Yields
    ------
    list[dict[str, Any]]
        The responses, in the order of their requests, with their key,
        status, headers and the checksum of their content, or no
        checksum if the request sends a secret in its body.
    """
    responses: list[dict[str, Any]] = []
    send = requests.Session.send
    urlopen = urllib.request.urlopen  # noqa: S310
    find_manual_files = utils.fetcher.find_manual_files

    def record(
        method: str,
        url: str,
        body: Any,
        content: bytes,
        status: int,
        headers: dict[str, str],
    ) -> None:
        responses.append(
            {
                "key": list(_key(method, url, body)),
                "status": status,
                "headers": headers,
                "file": None
                if _sends_secret(body)
                else _save_file(data_source, content),
            }
        )

    def recording_send(
        session: requests.Session,
        request: requests.PreparedRequest,
        **kwargs: Any,
    ) -> requests.Response:
        response = send(session, request, **kwargs)
        headers = {
            name: response.headers[name]
            for name in ("Content-Type",)
            if name in response.headers
        }
        if response.encoding:
            headers["Encoding"] = response.encoding
        record(
            str(request.method),
            str(request.url),
            request.body,
            response.content,
            response.status_code,
            headers,
        )
        return response

    def recording_urlopen(url: Any, *args: Any, **kwargs: Any) -> _UrlResponse:
        full_url, body = _url_and_body(url)
        method = "POST" if body is not None else "GET"
        with urlopen(url, *args, **kwargs) as response:
            content = response.read()
            headers = {
                name: response.headers[name]
                for name in ("Content-Type", "Content-Encoding")
                if response.headers.get(name)
            }
            status = response.status
        record(method, full_url, body, content, status, headers)
        return _UrlResponse(content, headers, status, full_url)

    def recording_find_manual_files(prefix: str) -> list[str]:
        file_paths = find_manual_files(prefix)
        for file_path in file_paths:
            name = os.path.basename(file_path)
            # A file found twice, such as to check whether it changed
            # before reading it, is recorded once.
            if any(
                response["key"] == list(_key(MANUAL_FILE, name, None))
                for response in responses
            ):
                continue
            with open(file_path, "rb") as file:
                record(MANUAL_FILE, name, None, file.read(), 200, {})
        return file_paths

    setattr(requests.Session, "send", recording_send)  # noqa: B010
    setattr(urllib.request, "urlopen", recording_urlopen)  # noqa: B010
    setattr(  # noqa: B010
        utils.fetcher, "find_manual_files", recording_find_manual_files
    )
    try:
        yield responses
    finally:
        setattr(requests.Session, "send", send)  # noqa: B010
        setattr(urllib.request, "urlopen", urlopen)  # noqa: B010
        setattr(  # noqa: B010
            utils.fetcher, "find_manual_files", find_manual_files
        )


def _copy_manual_files(
    data_source: str,
    saved: dict[tuple[str, str, str | None], dict[str, Any]],
    prefix: str,
    folder: str,
) -> list[str]:
    """
    Copy the saved files downloaded manually that start with a prefix.

    Parameters
    ----------
    data_source : str
        The data source, whose folder keeps the files.
    saved : dict[tuple[str, str, str | None], dict[str, Any]]
        The saved responses, by their key.
    prefix : str
        The start of the names of the files.
    folder : str
        The folder to copy the files into, with their names.

    Returns
    -------
    list[str]
        The paths of the copies, in the order of their names.

    Raises
    ------
    RawDataNotFoundError
        If no saved file starts with the prefix.
    """
    names = sorted(
        name
        for method, name, _ in saved
        if method == MANUAL_FILE and name.startswith(prefix)
    )
    if not names:
        raise RawDataNotFoundError(
            f"No saved file of {data_source} downloaded manually whose "
            f"name starts with {prefix}. Retrieve the data again to save "
            "the files."
        )
    file_paths = []
    for name in names:
        file_path = os.path.join(folder, name)
        if not os.path.exists(file_path):
            shutil.copyfile(
                os.path.join(
                    _folder(data_source),
                    "files",
                    saved[(MANUAL_FILE, name, None)]["file"],
                ),
                file_path,
            )
        file_paths.append(file_path)
    return file_paths


@contextlib.contextmanager
def replaying(
    data_source: str, responses: list[dict[str, Any]]
) -> Iterator[None]:
    """
    Replay saved responses instead of downloads.

    Parameters
    ----------
    data_source : str
        The data source, whose folder keeps the responses.
    responses : list[dict[str, Any]]
        The responses, as recording gives them. The last response of a
        request is replayed.

    Yields
    ------
    None
        Nothing: the requests sent with requests or urllib get the saved
        responses meanwhile, and the data source finds the saved files
        downloaded manually.
    """
    saved = {tuple(response["key"]): response for response in responses}
    send = requests.Session.send
    urlopen = urllib.request.urlopen  # noqa: S310
    find_manual_files = utils.fetcher.find_manual_files
    # The saved files downloaded manually are copied with their names,
    # which can tell how to read them.
    manual_folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def replay(
        method: str, url: str, body: Any
    ) -> tuple[bytes, dict[str, Any]]:
        response = saved.get(_key(method, url, body))
        if response is None:
            if _sends_secret(body):
                return b"", {"status": 200, "headers": {}}
            raise RawDataNotFoundError(
                f"No saved response of {data_source} for {method} "
                f"{utils.fetcher.redact(url)}."
            )
        if response["file"] is None:
            return b"", response
        with open(
            os.path.join(_folder(data_source), "files", response["file"]), "rb"
        ) as file:
            return file.read(), response

    def replaying_send(
        _session: requests.Session,
        request: requests.PreparedRequest,
        **_kwargs: Any,
    ) -> requests.Response:
        content, saved_response = replay(
            str(request.method), str(request.url), request.body
        )
        response = requests.Response()
        response.status_code = saved_response["status"]
        response._content = content
        response.url = str(request.url)
        response.request = request
        headers = dict(saved_response["headers"])
        response.encoding = headers.pop("Encoding", None)
        response.headers.update(headers)
        return response

    def replaying_urlopen(
        url: Any, *_args: Any, **_kwargs: Any
    ) -> _UrlResponse:
        full_url, body = _url_and_body(url)
        method = "POST" if body is not None else "GET"
        content, saved_response = replay(method, full_url, body)
        return _UrlResponse(
            content,
            saved_response["headers"],
            saved_response["status"],
            full_url,
        )

    def replaying_find_manual_files(prefix: str) -> list[str]:
        return _copy_manual_files(
            data_source, saved, prefix, manual_folder.name
        )

    setattr(requests.Session, "send", replaying_send)  # noqa: B010
    setattr(urllib.request, "urlopen", replaying_urlopen)  # noqa: B010
    setattr(  # noqa: B010
        utils.fetcher, "find_manual_files", replaying_find_manual_files
    )
    try:
        yield
    finally:
        setattr(requests.Session, "send", send)  # noqa: B010
        setattr(urllib.request, "urlopen", urlopen)  # noqa: B010
        setattr(  # noqa: B010
            utils.fetcher, "find_manual_files", find_manual_files
        )
        manual_folder.cleanup()


def read_manifest(data_source: str) -> dict[str, Any]:
    """
    Read the manifest of the raw data of a data source.

    Parameters
    ----------
    data_source : str
        The data source.

    Returns
    -------
    dict[str, Any]
        The manifest, with the list of its requests, or an empty list if
        the data source has no raw data yet.
    """
    file_path = os.path.join(_folder(data_source), "manifest.json")
    if not os.path.exists(file_path):
        return {"requests": []}
    with open(file_path, encoding="utf-8") as file:
        return json.load(file)


def _write_manifest(data_source: str, manifest: dict[str, Any]) -> None:
    """
    Write the manifest of the raw data of a data source.

    Parameters
    ----------
    data_source : str
        The data source.
    manifest : dict[str, Any]
        The manifest.
    """
    file_path = os.path.join(_folder(data_source), "manifest.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path + ".tmp", "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=1)
    os.replace(file_path + ".tmp", file_path)


def save_versions(
    data_source: str,
    code: str,
    downloads: list[tuple[Any, list[dict[str, Any]], str | None]],
    retrieved: str,
) -> None:
    """
    Save the responses of the requests of a code as their versions.

    If the responses of a request are those of its latest version, only
    the date of its last retrieval changes, and its error is that of the
    last retrieval. The manifest is written once for all the requests.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    downloads : list[tuple[Any, list[dict[str, Any]], str | None]]
        Each request, with its responses as recording gives them, and
        the error raised while its data was extracted from them, if any.
    retrieved : str
        The date and time of the retrieval, in ISO format.
    """
    manifest = read_manifest(data_source)
    entries = {
        json.dumps(entry["request"], sort_keys=True): entry
        for entry in manifest["requests"]
        if entry["code"] == code
    }
    for request, responses, error in downloads:
        encoded = encode_request(request)
        entry = entries.get(json.dumps(encoded, sort_keys=True))
        if entry is None:
            entry = {"code": code, "request": encoded, "versions": []}
            manifest["requests"].append(entry)
            entries[json.dumps(encoded, sort_keys=True)] = entry

        files = [(response["key"], response["file"]) for response in responses]
        latest = entry["versions"][-1] if entry["versions"] else None
        if (
            latest is not None
            and [
                (response["key"], response["file"])
                for response in latest["responses"]
            ]
            == files
        ):
            latest["last_retrieved"] = retrieved
        else:
            latest = {
                "first_retrieved": retrieved,
                "last_retrieved": retrieved,
                "responses": responses,
            }
            entry["versions"].append(latest)
        if error is None:
            latest.pop("error", None)
        else:
            latest["error"] = error

    _write_manifest(data_source, manifest)
