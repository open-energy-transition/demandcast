"""
License: AGPL-3.0.

Description:

    Tests of the script of the regions of EIA-930, with synthetic files
    instead of its downloads: five square counties of New Mexico and
    Texas, the reference tables of EIA-930, the service territories and
    retail sales of EIA-861, the zones of Electricity Maps and the
    states of Natural Earth. They check the assignment of the counties
    to the regions, the cuts of the states, and the rewriting of
    subdivisions/USA.yaml.
"""

import io
import os
import pathlib
import re
import shutil
import zipfile
from typing import Any

import geopandas
import pandas as pd
import pytest
import requests
import shapely
import yaml

from shapes import eia

# The state, key, western longitude and population of each county, a
# square of one degree from latitude 35 to 36.
COUNTIES = [
    ("NM", "NM|ALPHA", -106, 300),
    ("NM", "NM|BETA", -105, 100),
    ("TX", "TX|GAMMA", -104, 100),
    ("NM", "NM|DELTA", -107, 100),
    ("NM", "NM|EPSILON", -102, 100),
]


def _counties() -> geopandas.GeoDataFrame:
    """
    Make the counties, as `read_counties` gives them.

    Returns
    -------
    geopandas.GeoDataFrame
        The counties of COUNTIES.
    """
    return geopandas.GeoDataFrame(
        {
            "state": [state for state, *_ in COUNTIES],
            "key": [key for _, key, *_ in COUNTIES],
            "population": [population for *_, population in COUNTIES],
        },
        geometry=[
            shapely.box(west, 35, west + 1, 36) for *_, west, _ in COUNTIES
        ],
        crs="EPSG:4326",
    )


def _excel(sheets: dict[str, pd.DataFrame], start_row: int = 0) -> bytes:
    """
    Write sheets into an Excel file.

    Parameters
    ----------
    sheets : dict[str, pandas.DataFrame]
        The table of each sheet, by its name.
    start_row : int, optional
        The row of the header of the tables.

    Returns
    -------
    bytes
        The content of the file.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, table in sheets.items():
            table.to_excel(
                writer, sheet_name=name, index=False, startrow=start_row
            )
    return buffer.getvalue()


def _reference() -> bytes:
    """
    Make the reference tables of EIA-930.

    Returns
    -------
    bytes
        The Excel file, with the region of each balancing authority and
        the name of each region.
    """
    return _excel(
        {
            "BAs": pd.DataFrame(
                {
                    "BA Code": ["PNM", "CISO", "ERCO"],
                    "Region/Country Code": ["SW", "CAL", "TEX"],
                }
            ),
            "Regions": pd.DataFrame(
                {
                    "Region/Country Code": ["SW", "CAL", "TEX"],
                    "Region/Country Name": [
                        "Southwest",
                        "California",
                        "Texas",
                    ],
                }
            ),
        }
    )


def _eia861() -> bytes:
    """
    Make the archive of EIA-861.

    Returns
    -------
    bytes
        The ZIP file, with the counties that each utility serves in
        each state and its retail sales by balancing authority.

    Notes
    -----
    The energy only sales (part B), the sales of an unknown balancing
    authority and those of a utility that serves no known county must
    be left out. The total sales are in the fifth column named
    "Megawatthours", which pandas names "Megawatthours.4".
    """
    territories = pd.DataFrame(
        [
            (1, "NM", "Alpha County"),
            (1, "NM", "Beta"),
            (2, "NM", "Beta"),
            (3, "TX", "Gamma"),
            (4, "NM", "Epsilon"),
            (5, "NM", "Nowhere"),
        ],
        columns=["Utility Number", "State", "County"],
    )
    sales = pd.DataFrame(
        [
            (1, "NM", "A", "PNM", 1000),
            (1, "NM", "B", "CISO", 10000),
            (2, "NM", "C", "CISO", 230),
            (2, "NM", "A", "XXXX", 5000),
            (3, "TX", "A", "ERCO", 1000),
            (4, "NM", "D", "CISO", 520),
            (4, "NM", "D", "PNM", 480),
            (5, "NM", "A", "PNM", 999),
        ],
        columns=["Utility Number", "State", "Part", "BA Code", "Total"],
    )
    for column in range(4):
        sales.insert(4, f"Other {column}", 0)
    sales.columns = [*sales.columns[:4], *["Megawatthours"] * 5]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            f"Service_Territory_{eia.EIA861_YEAR}.xlsx",
            _excel({"Counties_States": territories}),
        )
        archive.writestr(
            f"Sales_Ult_Cust_{eia.EIA861_YEAR}.xlsx",
            _excel({"States": sales}, start_row=2),
        )
    return buffer.getvalue()


def _zones() -> bytes:
    """
    Make the zones of Electricity Maps.

    Returns
    -------
    bytes
        The GeoJSON file, with a zone of California over most of Beta
        and half of Alpha, one of the Southwest over Gamma and a tenth
        of Beta, and a zone outside the United States over Delta.
    """
    return (
        geopandas.GeoDataFrame(
            {"zoneName": ["US-CAL-CISO", "US-SW-PNM", "FR"]},
            geometry=[
                shapely.box(-105.5, 34.5, -104.1, 36.5),
                shapely.box(-104.1, 34.5, -102.5, 36.5),
                shapely.box(-107.5, 34.5, -106.1, 36.5),
            ],
            crs="EPSG:4326",
        )
        .to_json()
        .encode()
    )


@pytest.fixture
def downloads(monkeypatch):
    """
    Serve the synthetic files instead of the downloads.

    Returns
    -------
    dict[str, bytes]
        The content of each file by its URL, to which a test can add.
    """
    files = {
        eia.EIA930_URL: _reference(),
        eia.EIA861_URL: _eia861(),
        eia.ZONES_URL: _zones(),
    }
    monkeypatch.setattr(eia, "_download", files.__getitem__)
    return files


@pytest.fixture
def natural_earth(tmp_path, monkeypatch):
    """Serve a shapefile of the states of Natural Earth."""
    folder = tmp_path / "natural_earth"
    folder.mkdir()
    path = folder / "states.shp"
    geopandas.GeoDataFrame(
        {
            "iso_a2": ["US", "US", "FR"],
            "iso_3166_2": ["US-NM", "US-TX", "FR-IDF"],
            "name": ["New Mexico", "Texas", "Île-de-France"],
        },
        geometry=[shapely.box(-109, 31, -103, 37)] * 3,
        crs="EPSG:4326",
    ).to_file(path)
    monkeypatch.setattr(
        eia.cartopy.io.shapereader, "natural_earth", lambda **_: str(path)
    )


@pytest.fixture
def subdivisions_file(tmp_path, monkeypatch):
    """
    Point the script at a file of the subdivisions in tmp_path.

    Returns
    -------
    pathlib.Path
        The path of the file, which the test writes.
    """
    path = tmp_path / "USA.yaml"
    monkeypatch.setattr(eia, "SUBDIVISIONS_FILE", str(path))
    return path


def test_download(monkeypatch):
    """Test that a download gives the content of the response."""
    calls = []

    def get(url: str, **kwargs: Any) -> requests.Response:
        """
        Record a download and answer with a fixed content.

        Returns
        -------
        requests.Response
            The response.
        """
        calls.append((url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(b"content")
        return response

    monkeypatch.setattr(eia.requests, "get", get)

    assert eia._download("https://example.org/file") == b"content"
    assert calls == [("https://example.org/file", {"timeout": 300})]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Doña Ana County", "DONAANA"),
        ("St. Mary's Parish", "STMARYS"),
        ("Saint Louis", "STLOUIS"),
        ("Matanuska-Susitna Borough", "MATANUSKASUSITNA"),
        ("Valdez-Cordova Census Area", "VALDEZCORDOVA"),
    ],
)
def test_normalize(name, expected):
    """Test that names of counties are normalized to match EIA-861."""
    assert eia._normalize(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("New Mexico", "new_mexico"),
        ("Mid-Atlantic", "mid_atlantic"),
        ("Île-de-France", "ile_de_france"),
    ],
)
def test_slug(name, expected):
    """Test that names give the names of the cuts."""
    assert eia._slug(name) == expected


def test_read_counties(tmp_path, downloads):
    """Test the counties of the lower 48 states and their population."""
    folder = tmp_path / "counties"
    folder.mkdir()
    geopandas.GeoDataFrame(
        {
            "STUSPS": ["NM", "VA", "AK", "TX"],
            "GEOID": ["35001", "51760", "02020", "48001"],
            "NAME": ["Doña Ana", "Richmond", "Anchorage", "Anderson"],
            "LSAD": ["06", "25", "12", "06"],
        },
        geometry=[shapely.box(x, 35, x + 1, 36) for x in range(4)],
        crs="EPSG:4269",
    ).to_file(folder / "counties.shp")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        for path in folder.iterdir():
            zip_file.write(path, path.name)
    downloads[eia.COUNTIES_URL] = archive.getvalue()
    downloads[eia.POPULATION_URL] = (
        "SUMLEV,STATE,COUNTY,POPESTIMATE2024\n"
        "040,35,000,2100000\n"
        "050,35,001,220000\n"
        "050,51,760,230000\n"
        "050,02,020,290000\n"
    ).encode("latin-1")

    counties = eia.read_counties()

    # Alaska is left out, Richmond is an independent city, and Anderson
    # has no population in the file.
    assert counties["key"].tolist() == [
        "NM|DONAANA",
        "VA|RICHMONDCITY",
        "TX|ANDERSON",
    ]
    assert counties["state"].tolist() == ["NM", "VA", "TX"]
    assert counties["population"].tolist() == [220000, 230000, 1]
    assert counties.index.tolist() == [0, 1, 2]


@pytest.mark.usefixtures("downloads")
def test_sales_by_region():
    """Test that the sales of a utility are spread over its counties."""
    sales = eia.sales_by_region(_counties())

    # Alpha has three quarters of the people that utility 1 serves, and
    # Delta is served by no utility.
    assert [dict(by_region) for by_region in sales] == [
        {"SW": 750.0},
        {"SW": 250.0, "CAL": 230.0},
        {"TEX": 1000.0},
        {},
        {"CAL": 520.0, "SW": 480.0},
    ]


@pytest.mark.usefixtures("downloads")
def test_zone_regions():
    """Test that each county takes the zone of most of its area."""
    zones = eia.zone_regions(_counties())

    assert zones.index.tolist() == [0, 1, 2, 3, 4]
    assert zones.iloc[:3].tolist() == ["CAL", "CAL", "SW"]
    assert zones.iloc[3:].isna().all()


@pytest.mark.usefixtures("downloads")
def test_assign_regions():
    """Test the region of each county, by its sales or its zone."""
    regions = eia.assign_regions(_counties())

    # Alpha leads by its sales, Beta leads by less than MARGIN and takes
    # its zone, Gamma is in Texas and takes its zone, Delta has neither
    # and takes the region of Alpha, the nearest county of New Mexico,
    # and Epsilon has no zone and takes its largest sales.
    assert regions.tolist() == ["SW", "CAL", "SW", "SW", "CAL"]


@pytest.mark.usefixtures("downloads", "natural_earth")
def test_build():
    """Test the definitions of the regions and the cuts of states."""
    counties = _counties()
    regions = pd.Series(["SW", "CAL", "SW", "SW", "CAL"])

    built = eia.build(counties, regions)

    assert built["subdivisions"] == {
        "USA_CAL": {
            "name": "California",
            "standard_subdivisions": ["US-NM"],
            "cuts": {"US-NM": "new_mexico_outside_california"},
        },
        "USA_SW": {
            "name": "Southwest",
            "standard_subdivisions": ["US-NM", "US-TX"],
            "cuts": {"US-NM": "new_mexico_outside_southwest"},
        },
    }
    assert set(built["cuts"]) == {
        "new_mexico_outside_california",
        "new_mexico_outside_southwest",
    }
    assert built["cuts"]["new_mexico_outside_california"]["description"] == (
        "The counties of New Mexico, United States, outside the California "
        "region of EIA-930."
    )
    for key, outside, inside in [
        ("new_mexico_outside_california", [0, 3], [1, 4]),
        ("new_mexico_outside_southwest", [1, 4], [0, 3]),
    ]:
        polygon = built["cuts"][key]["polygon"]
        assert all(
            len(decimals) <= 1 for decimals in re.findall(r"\.(\d+)", polygon)
        )
        cut = shapely.from_wkt(polygon)
        for county in outside:
            assert cut.contains(counties.geometry[county].centroid)
        for county in inside:
            assert cut.intersection(counties.geometry[county]).area < 0.01
    # The counties outside the Southwest are apart, so their cut has two
    # parts.
    assert (
        shapely.from_wkt(
            built["cuts"]["new_mexico_outside_southwest"]["polygon"]
        ).geom_type
        == "MultiPolygon"
    )


def test_wrap():
    """Test that a text is wrapped at its spaces into short lines."""
    text = " ".join(["word"] * 40)

    lines = eia._wrap(text, "      ", "    ")

    assert lines[0].startswith("    word")
    assert all(line.startswith("      word") for line in lines[1:])
    assert all(len(line) <= 79 for line in lines)
    assert len(lines[0]) > 74
    assert " ".join(line.strip() for line in lines) == text
    # A word longer than a line stays whole, on a line of its own.
    long_word = "x" * 90
    assert eia._wrap(f"a {long_word} b", "  ") == [
        "  a",
        f"  {long_word}",
        "  b",
    ]
    assert eia._wrap("short", "  ") == ["  short"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Southwest", "Southwest"),
        ("Region: west", '"Region: west"'),
        ('A "quoted" name', '"A \\"quoted\\" name"'),
        ("St. Mary's", '"St. Mary\'s"'),
        ("No. #1", '"No. #1"'),
    ],
)
def test_quote(text, expected):
    """Test that texts are quoted for YAML only when they need it."""
    assert eia._quote(text) == expected
    assert yaml.safe_load(f"key: {eia._quote(text)}")["key"] == text


def _write_file(path: pathlib.Path, data: dict[str, Any]) -> None:
    """
    Write a file of subdivisions with a header of comments.

    Parameters
    ----------
    path : pathlib.Path
        The path of the file.
    data : dict[str, Any]
        The cuts and the subdivisions.
    """
    path.write_text(
        "# The subdivisions.\n# Second line.\n\n" + yaml.safe_dump(data),
        encoding="utf-8",
    )


def test_write_replaces_regions_and_keeps_other_subdivisions(
    subdivisions_file,
):
    """Test that the regions are replaced and the others are kept."""
    _write_file(
        subdivisions_file,
        {
            "cuts": {
                "old_cut": {"description": "Old.", "polygon": "POINT (0 0)"},
                "kept_cut": {
                    "description": "Kept: a colon.",
                    "polygon": "POLYGON ((0 0, 1 0, 1 1, 0 0))",
                },
            },
            "subdivisions": {
                "USA_CAISO": {
                    "name": "CAISO balancing area",
                    "standard_subdivisions": "US-CA",
                    "cuts": {"US-CA": "kept_cut"},
                },
                "USA_SW": {
                    "name": "Old Southwest",
                    "standard_subdivisions": "US-AZ",
                    "cuts": {"US-AZ": "old_cut"},
                },
            },
        },
    )
    states = [f"US-S{index:02d}" for index in range(20)]
    long_polygon = "POLYGON ((" + ", ".join(["-100.1 35.2"] * 20) + "))"

    eia.write(
        {
            "cuts": {
                "new_cut": {
                    "description": "The counties outside the Southwest.",
                    "polygon": long_polygon,
                }
            },
            "subdivisions": {
                "USA_SW": {
                    "name": "Southwest",
                    "standard_subdivisions": states,
                    "cuts": {"US-S00": "new_cut"},
                },
                "USA_TEX": {
                    "name": "Texas",
                    "standard_subdivisions": ["US-TX"],
                },
            },
        }
    )

    text = subdivisions_file.read_text(encoding="utf-8")
    assert text.startswith("# The subdivisions.\n# Second line.\n\ncuts:\n")
    assert all(len(line) <= 79 for line in text.splitlines())
    assert "    standard_subdivisions: >-\n" in text
    assert "    standard_subdivisions: US-TX\n" in text
    data = yaml.safe_load(text)
    # The cut that no subdivision uses any more is dropped.
    assert data["cuts"] == {
        "kept_cut": {
            "description": "Kept: a colon.",
            "polygon": "POLYGON ((0 0, 1 0, 1 1, 0 0))",
        },
        "new_cut": {
            "description": "The counties outside the Southwest.",
            "polygon": long_polygon,
        },
    }
    assert data["subdivisions"] == {
        "USA_CAISO": {
            "name": "CAISO balancing area",
            "standard_subdivisions": "US-CA",
            "cuts": {"US-CA": "kept_cut"},
        },
        "USA_SW": {
            "name": "Southwest",
            "standard_subdivisions": " ".join(states),
            "cuts": {"US-S00": "new_cut"},
        },
        "USA_TEX": {"name": "Texas", "standard_subdivisions": "US-TX"},
    }


def test_write_without_changes_keeps_the_file(subdivisions_file):
    """Test that USA.yaml is rewritten byte for byte without changes."""
    original = os.path.join(
        os.path.dirname(eia.__file__), "subdivisions", "USA.yaml"
    )
    shutil.copyfile(original, subdivisions_file)

    eia.write({"cuts": {}, "subdivisions": {}})

    assert (
        subdivisions_file.read_bytes() == pathlib.Path(original).read_bytes()
    )


@pytest.mark.parametrize(
    ("data", "unknown"),
    [
        ({"cuts": {}, "subdivisions": {}, "notes": "x"}, "notes"),
        (
            {
                "cuts": {
                    "cut": {"description": "A.", "polygon": "P", "source": "x"}
                },
                "subdivisions": {},
            },
            "cut: source",
        ),
        (
            {
                "cuts": {},
                "subdivisions": {
                    "USA_X": {
                        "name": "X",
                        "standard_subdivisions": "US-CA",
                        "same_area": False,
                    }
                },
            },
            "USA_X: same_area",
        ),
    ],
)
def test_write_rejects_unknown_keys(subdivisions_file, data, unknown):
    """Test that a file with keys that would be lost is not written."""
    _write_file(subdivisions_file, data)
    before = subdivisions_file.read_bytes()

    with pytest.raises(ValueError, match=f"would be dropped: {unknown}$"):
        eia.write({"cuts": {}, "subdivisions": {}})

    assert subdivisions_file.read_bytes() == before


@pytest.mark.usefixtures("downloads", "natural_earth")
def test_main(subdivisions_file, monkeypatch):
    """Test that the script writes the regions of the counties."""
    _write_file(
        subdivisions_file,
        {
            "cuts": {},
            "subdivisions": {
                "USA_CAISO": {
                    "name": "CAISO balancing area",
                    "standard_subdivisions": "US-CA",
                }
            },
        },
    )
    monkeypatch.setattr(eia, "read_counties", _counties)

    eia.main()

    data = yaml.safe_load(subdivisions_file.read_text(encoding="utf-8"))
    assert sorted(data["subdivisions"]) == ["USA_CAISO", "USA_CAL", "USA_SW"]
    assert data["subdivisions"]["USA_SW"] == {
        "name": "Southwest",
        "standard_subdivisions": "US-NM US-TX",
        "cuts": {"US-NM": "new_mexico_outside_southwest"},
    }
    assert sorted(data["cuts"]) == [
        "new_mexico_outside_california",
        "new_mexico_outside_southwest",
    ]
