"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand of the ten areas of
    Japan from the system information service of the Organization for
    Cross-regional Coordination of Transmission Operators (OCCTO).

    The daily actual demand ("需要実績（日別）") gives the
    consumption of each area in each hour, in MWh, which is the mean
    demand of the hour in MW, from 2016-04-01. It is the area demand of
    the general transmission operators, in their national format (see
    the YAML file): the demand of Tokyo is that of TEPCO, which rounds
    it to 10 MW, within 5 MW in all but 5 of the 9,504 hours of 2023 and
    January 2024, and the demand of Kansai that of Kansai TD, the same
    in all but 41 of them, by up to 116 MW. OCCTO republishes the data
    of the operators, so it is compiled in the YAML file: the combined
    demand of Kantō and Kansai takes the data of TEPCO and Kansai TD
    first (see cleaning/combining.py).

    The service is a web application without an account, whose public
    screens are opened by posting a form and whose files are saved by
    the "CSV 保存" button. The information download screen
    ("情報ダウンロード", CF01S010C) is opened with an empty post, then
    its form, with the daily actual demand (data kind 12), the first and
    last days and the area, is checked ("print"), confirmed ("ok"),
    which gives a download key and a new request token, and submitted
    ("download"), which gives the file: the requests that the button
    sends in a browser. A request is a year of an area; a whole year is
    accepted at once.

    The file is a CSV in Shift JIS (code page 932), with the date
    (YYYY/MM/DD), the hour ("hh:mm～hh:mm", its start and end in
    Japanese time, which has no daylight saving time), a column for each
    area and one for their total. After the 24 hours of each day, two
    rows give the daily energy ("日電力量") and the daily maximum
    ("日最大電力"), which are left out.

    The terms of use of the system information service were not found,
    so the data is not redistributed.

    The area demand counts the solar fed into the networks, but not the
    solar that the consumers of the surplus purchase scheme use
    themselves, which lowers the area demand: Kyushu states it for the
    national format ("「エリア需要」および「太陽光」には、
    余剰買取による太陽光発電の自家消費分は含んでいません"), so the
    embedded generation is partial in the YAML file.

    Source: https://occtonet3.occto.or.jp/public/dfw/RP11/OCCTO/SD/LOGIN_login
    Source: https://www.occto.or.jp/assets/occtosystem2/files/250306_keitoujouhou.pdf
    Source: https://www.kyuden.co.jp/td_area_jukyu/jukyu.html
"""

import datetime
import io
from html.parser import HTMLParser

import pandas as pd
import requests

import utils.time_series

# The address of the screens of the public system information service.
ROOT = "https://occtonet3.occto.or.jp/public/dfw/RP11/OCCTO/SD/"

# The information download screen and its data kind of the daily
# actual demand.
SCREEN = "CF01S010C"
DAILY_DEMAND = "12"

# The check box of each area in the download screen, its value, and the
# column of the area in the CSV file.
AREAS = {
    "JPN_Hokkaidō": ("hkd", "01", "北海道"),
    "JPN_Tōhoku": ("thk", "02", "東北"),
    "JPN_Kantō": ("tko", "03", "東京"),
    "JPN_Chūbu": ("chb", "04", "中部"),
    "JPN_Hokuriku": ("hkr", "05", "北陸"),
    "JPN_Kansai": ("kns", "06", "関西"),
    "JPN_Chūgoku": ("cgk", "07", "中国"),
    "JPN_Shikoku": ("skk", "08", "四国"),
    "JPN_Kyūshū": ("kys", "09", "九州"),
    "JPN_Okinawa": ("oki", "10", "沖縄"),
}

# The time out of the requests, in seconds: a year takes a few seconds.
TIMEOUT = 300


class _FormFields(HTMLParser):
    """The fields of a form and the values that a browser sends."""

    def __init__(self) -> None:
        super().__init__()
        self.fields: list[tuple[str, str]] = []
        self._select: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """
        Add the value of a field.

        Parameters
        ----------
        tag : str
            The tag.
        attrs : list[tuple[str, str | None]]
            The attributes of the tag.
        """
        attributes = {key: value or "" for key, value in attrs}
        name = attributes.get("name")
        if tag == "input" and name:
            kind = attributes.get("type", "text").lower()
            if kind in ("checkbox", "radio"):
                if "checked" in attributes:
                    self.fields.append((name, attributes.get("value", "on")))
            elif kind not in ("button", "submit", "image"):
                self.fields.append((name, attributes.get("value", "")))
        elif tag == "select" and name:
            self._select = [name]
        elif tag == "option" and self._select is not None:
            if len(self._select) == 1 or "selected" in attributes:
                self._select[1:] = [attributes.get("value", "")]

    def handle_endtag(self, tag: str) -> None:
        """
        Add the value of a list.

        Parameters
        ----------
        tag : str
            The tag.
        """
        if tag == "select" and self._select is not None:
            name, *value = self._select
            self.fields.append((name, value[0] if value else ""))
            self._select = None


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the area.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The day after the last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The years of the data, from their first day to the first day
        after them.
    """
    return utils.time_series.split_period(start_date, end_date, "YS")


def get_url() -> str:
    """
    Get the URL of the information download screen.

    Returns
    -------
    str
        The URL.
    """
    return ROOT + SCREEN


def _post(
    session: requests.Session,
    fields: list[tuple[str, str]],
    sub_action: str,
) -> requests.Response:
    """
    Send the form of the download screen with an action.

    Parameters
    ----------
    session : requests.Session
        The session of the service.
    fields : list[tuple[str, str]]
        The fields of the form.
    sub_action : str
        The action: "print", "ok" or "download".

    Returns
    -------
    requests.Response
        The response, a JSON message for the checks.

    Raises
    ------
    ValueError
        If the service reports an error.
    """
    response = session.post(
        get_url(),
        data=[
            *fields,
            ("fwExtention.actionType", "reference"),
            ("fwExtention.actionSubType", sub_action),
        ],
        headers={} if sub_action == "download" else {"sdReqType": "AJAX"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    if sub_action != "download":
        message = response.json()["root"]
        if message.get("errMessage"):
            raise ValueError(
                f"OCCTO refused the download: {message['errMessage']}"
            )
    return response


def _download(
    first_day: datetime.date, last_day: datetime.date, code: str
) -> bytes:
    """
    Download the daily actual demand of an area.

    Parameters
    ----------
    first_day : datetime.date
        The first day.
    last_day : datetime.date
        The last day.
    code : str
        The code of the area.

    Returns
    -------
    bytes
        The CSV file.

    Raises
    ------
    ValueError
        If the service gives a page instead of the file.
    """
    check_box, value, _ = AREAS[code]
    with requests.Session() as session:
        session.get(ROOT + "LOGIN_login", timeout=TIMEOUT).raise_for_status()
        screen = session.post(
            f"{get_url()}?fwExtention.pathInfo={SCREEN}&fwExtention.prgbrh=0",
            data={},
            timeout=TIMEOUT,
        )
        screen.raise_for_status()
        form = _FormFields()
        form.feed(screen.text)
        chosen = {
            "areaDataKnd": DAILY_DEMAND,
            "areaNngpFrom": first_day.strftime("%Y/%m/%d"),
            "areaNngpTo": last_day.strftime("%Y/%m/%d"),
            check_box: value,
        }
        fields = [
            (name, field_value)
            for name, field_value in form.fields
            if name not in chosen
            and name
            not in ("fwExtention.actionType", "fwExtention.actionSubType")
        ] + list(chosen.items())

        _post(session, fields, "print")
        # The confirmation gives the key of the file and a new token,
        # which the browser puts in the form.
        header = _post(session, fields, "ok").json()["root"]["bizRoot"][
            "header"
        ]
        given = {
            item["name"]: item.get("value", "")
            for item in header.values()
            if isinstance(item, dict)
            and item.get("name") in ("downloadKey", "requestToken")
        }
        fields = [
            (name, given.pop(name, field_value))
            for name, field_value in fields
        ] + list(given.items())

        response = _post(session, fields, "download")
    if response.headers.get("content-type", "").startswith("text/html"):
        raise ValueError(
            f"OCCTO gave a page instead of the file of {code} from "
            f"{first_day} to {last_day}."
        )
    return response.content


def download_and_extract_data_for_request(
    request: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract the electricity demand of an area in a year.

    Parameters
    ----------
    request : tuple[pandas.Timestamp, pandas.Timestamp]
        The first day of the year of the data, and the first day after
        it.
    code : str
        The code of the area.

    Returns
    -------
    pandas.Series
        The electricity demand in MW, at the ends of the hours in
        Japanese time.
    """
    start, end = request
    content = _download(
        start.date(), (end - pd.Timedelta(days=1)).date(), code
    )
    dataset = pd.read_csv(io.StringIO(content.decode("cp932")), dtype=str)

    # Keep the hours, without the daily energy and maximum.
    hours = dataset[dataset.iloc[:, 1].str.match(r"\d\d:\d\d", na=False)]
    starts = pd.to_datetime(
        hours.iloc[:, 0] + " " + hours.iloc[:, 1].str[:5],
        format="%Y/%m/%d %H:%M",
    )
    electricity_demand_time_series = pd.Series(
        pd.to_numeric(hours[AREAS[code][2]], errors="coerce").to_numpy(
            dtype="float64"
        ),
        index=pd.DatetimeIndex(starts),
    )

    # The times are the starts of the hours. Move them to the ends.
    return utils.time_series.localize_interval_starts(
        electricity_demand_time_series, "Asia/Tokyo", pd.Timedelta(hours=1)
    )
