# Data sources

DemandCast retrieves hourly electricity demand from 47 [data sources](../concepts/glossary.md#data-source). This page lists each one and explains the YAML file that describes it.

## Files of a data source

Each source is two files in `demandcast/retrievals/electricity_demand_data_sources/`:

- `<source>.py`: the module that downloads the data and returns the demand in MW. Its docstring gives the format, time zone, quirks and left-out areas of the data.
- `<source>.yaml`: the licence, what the demand counts, and the countries and subdivisions with their dates.

The file name without `.yaml`, such as `entsoe`, is the value of `electricity_data_source` in [`retrieve.py`](../guides/retrieve.md).

## The YAML file

| Field | What it gives |
|---|---|
| `licence` | `redistribute` (whether the terms allow sharing the data), `terms` (a summary) and `url`. DemandCast publishes only its models and forecasts, not the retrieved data. |
| `definition` | What the demand counts, as periods in order of `start_date`. See [The `definition` of a data source](../concepts/electricity-demand.md#the-definition-of-a-data-source). |
| `compiled` | `true` for a [compiled data source](../concepts/glossary.md#compiled-data-source), which republishes the data of system operators, such as the EIA. Default `false`. |
| `republishes` | For a compiled source, the compiled sources it also republishes, such as `entsoe` for the IEA. |
| `entities` | The countries and subdivisions, with the fields below. |

| Entity field | Meaning |
|---|---|
| `country_name`, `country_code` | The country and its ISO 3166 alpha-3 code. |
| `subdivision_name`, `subdivision_code`, `time_zone` | For a subdivision only, all three. Its code is `<country_code>_<subdivision_code>`, such as `USA_CAL`. |
| `start_date`, `end_date` | First and last days of the data. `end_date: today` means five days ago. |
| `same_area` | `false` if the data covers only part of the shape of the code. Default `true`. |

The processed data of an entity keeps only the days between its `start_date` and `end_date`, in local time. So a country can have its own data only until the data of its subdivisions starts, as Argentina does until 2026-02-16.

The file is checked when read. An unknown field, a subdivision without all three of its fields, an unknown time zone, a `start_date` after `end_date`, a code listed twice, periods of `definition` out of order, or `republishes` without `compiled: true` is an error.

The combination ranks the sources of a code with `definition`, `compiled`, `republishes` and `same_area`: see [Combination](../concepts/electricity-demand.md#combination).

## The table

- **Covers**: the codes in the YAML file.
- **Years**: first and last years in the YAML file.
- **Resolution**: the time step, from the module docstring.
- **Embedded generation**: the `embedded_generation` value of each period of `definition` (see [embedded generation](../concepts/glossary.md#embedded-generation)).
- **Needs**: the variables to set in `demandcast/.env` (see [API keys and accounts](../guides/retrieve.md#api-keys-and-accounts)), or the start of the names of the files that you [download by hand](../guides/retrieve.md#files-downloaded-by-hand) into `electricity_demand/raw/manual_downloads/`.

| Source | Provider | Covers | Years | Resolution | Embedded generation | Needs | Notes |
|---|---|---|---|---|---|---|---|
| `adme` | Administrador del Mercado Eléctrico (Uruguay) | `URY` | 2019–today | 1 h | unknown | – | Generation plus imports minus exports. |
| `aemo_nem` | Australian Energy Market Operator, National Electricity Market | 5 subdivisions of `AUS` | 1998–today | 30 min; 5 min from Oct 2021 | excluded; added from 2017-01-01 | – | Adds AEMO's rooftop solar estimate. A month waits for its archive file. |
| `aemo_wem` | Australian Energy Market Operator, Wholesale Electricity Market | `AUS_SWIS` | 2006–today | 30 min; 5 min from Oct 2023 | excluded; added from 2020-11-03 | – | Adds AEMO's distributed solar estimate. |
| `aeso` | Alberta Electric System Operator | `CAN_AB-AIES` | 2001–2025 | 1 h | included | – | Alberta Internal Load; also supplies Fort Nelson, BC. |
| `bchydro` | BC Hydro | `CAN_BC-INTEGRATED` | 2001–today | 1 h | unknown | – | Without Fort Nelson and off-grid areas. |
| `caiso` | California ISO | `USA_CAISO` | 2019–today | 1 h | excluded | – | About 82% of the EIA region `USA_CAL`. |
| `cammesa` | CAMMESA (Argentina) | 22 provinces of `ARG` | 2026–today | 5 min | unknown | – | The API keeps only the last 7 to 8 months; the raw data keeps the rest. |
| `ccei` | Canadian Centre for Energy Information | 8 subdivisions of `CAN` | 2002–today | various | unknown | – | Compiled. Corrects wrong times of some provinces; no BC or Saskatchewan. |
| `cen` | Coordinador Eléctrico Nacional (Chile) | `CHL_SEN` | 2016–2026 | 1 h | unknown | – | No data after 2026-05-13. |
| `cenace` | Centro Nacional de Control de Energía (Mexico) | 9 subdivisions of `MEX` | 2016–today | 1 h | excluded | – | Until 2019, each area gives its generation minus its exports. |
| `cnd` | Centro Nacional de Despacho (Panama), on Mendeley Data | `PAN_SIN` | 2016–2020 | 1 h | unknown | – | One file. |
| `coes` | Comité de Operación Económica (Peru) | `PER_SEIN-2000`, `PER_SEIN` | 2000–today | 30 min | unknown | – | One entity per area of the grid, before and from 2011. |
| `edf_sei` | EDF Systèmes Énergétiques Insulaires (Corsica) | `FRA_20R` | 2019–2024 | 1 h | unknown | – | Generation plus imports; years after 2020 are estimates. |
| `egat` | Electricity Generating Authority of Thailand, on Zenodo | `THA` | 2023–2024 | 1 h | unknown | – | Sum of five regions. |
| `eia` | US Energy Information Administration | 13 regions of `USA` | 2020–today | 1 h | excluded | `EIA_API_KEY` | Compiled. Corrects the one-hour delay of CAISO in `USA_CAL` (2022-06-16 to 2025-12-02). |
| `ema` | Energy Market Authority (Singapore) | `SGP` | 2014–today | 30 min | included | – | Weekly files: several years take up to 10 minutes. |
| `emi` | Electricity Market Information (New Zealand) | `NZL` | 2005–2020 | 30 min | unknown | – | From 2020-12-22 the IEA gives the two islands. |
| `entsoe` | European Network of Transmission System Operators for Electricity | 30 countries and 9 subdivisions (38 countries in all) | 2014–today | 15 min to 1 h | unknown | `ENTSOE_API_KEY` | Compiled. Corrects wrong times of Bulgaria, Northern Ireland and Ukraine. |
| `epias` | EPIAS transparency platform (Turkey) | `TUR` | 2015–today | 1 h | added; included from 2020-12-30 | `EPIAS_USERNAME`, `EPIAS_PASSWORD` | Adds licence-exempt generation until 2020-12-29. |
| `eskom` | Eskom (South Africa) | `ZAF` | 2021–today | 1 h | excluded | Files `ESK*` (CSV) | Ask for the data with the form of the Eskom data portal; a link arrives by email. |
| `grupoice` | Grupo ICE (Costa Rica) | `CRI` | 2012–today | 15 min | unknown | – | |
| `hydroquebec` | Hydro-Québec | `CAN_QC-INTEGRATED` | 2019–2025 | 1 h | unknown | – | Real-time values; a year is added months after it ends. |
| `iea` | International Energy Agency, Real-Time Electricity Tracker | 45 countries and 94 subdivisions (70 countries in all) | 2009–today | 1 h | unknown | – | Compiled; republishes `ccei`, `eia`, `entsoe` and `occto`. Times corrected per country. |
| `ieso` | Independent Electricity System Operator (Ontario) | `CAN_ON` | 1994–today | 1 h | excluded | – | Times in Eastern Standard Time all year. |
| `ismo` | Independent System and Market Operator (Pakistan) | `PAK_NTDC` | 2024–2025 | 1 h | excluded | – | One fiscal year, July 2024 to June 2025; without K-Electric. |
| `isone` | ISO New England | `USA_NE` | 2019–today | 1 h | added | `ISONE_USERNAME`, `ISONE_PASSWORD` | Native load plus ISO-NE's estimate of the solar behind the meters. |
| `kansaitd` | Kansai Transmission and Distribution (Japan) | `JPN_Kansai` | 2016–today | 1 h; 30 min from Mar 2024 | partial | – | OCCTO republishes the same demand. |
| `korem` | Kazakhstan Operator of Electricity and Capacity Market | `KAZ_NORTH-SOUTH`, `KAZ_WEST` | 2023–today | 1 h | unknown | – | Monthly files listed by hand in the module: add each new one there. |
| `krogd` | Korean Open Government Data portal (data of KPX) | `KOR` | 2013–2025 | 1 h | excluded | – | Stops with an error when the portal asks for a CAPTCHA. |
| `nbpower` | NB Power (New Brunswick) | `CAN_NB` | 2019–today | 1 h | unknown | – | The current month is not in the archive yet. |
| `nea` | Nepal Electricity Authority, on Open Data Nepal | `NPL_INPS` | 2017–2018 | 1 h, some 30 min | unknown | – | One year of the Bikram Sambat calendar. |
| `neso` | National Energy System Operator (Great Britain) | `GBR_GB` | 2001–today | 30 min | excluded; added from 2007-10-28 | – | Adds NESO's embedded wind and solar estimate. |
| `ngcp` | National Grid Corporation of the Philippines | 7 grids of `PHL` | 2013–2025 | 1 h | unknown | – | One Excel file, one sheet per grid. |
| `niti` | NITI Aayog, India Climate and Energy Dashboard | 32 subdivisions of `IND` | 2017–2026 | 1 h | excluded | Files `NIT*` (Excel) | Download a year and two states at a time, behind a reCAPTCHA. |
| `ntdc` | National Transmission & Despatch Company (Pakistan), Zenodo copy | `PAK_NTDC` | 2015–2020 | 1 h | excluded | – | Corrects the dates around midnight and the hours that slip in 2019. |
| `occto` | Organization for Cross-regional Coordination of Transmission Operators (Japan) | 10 areas of `JPN` | 2016–today | 1 h | partial | – | Compiled. |
| `oluwole_et_al` | Oluwole et al., on Mendeley Data (Nigeria) | `NGA` | 2016 | 1 h | unknown | – | Modelled demand without load shedding, not measured. |
| `ons` | Operador Nacional do Sistema Elétrico (Brazil) | 9 subdivisions of `BRA` | 2000–today | 1 h | excluded; included from 2023-04-29 | – | One entity per area of the North and South-East subsystems. |
| `pgcb` | Power Grid Bangladesh | `BGD` | 2014–today | 1 h | excluded | – | One report a day: all the data takes a few hours. |
| `pucsl` | Public Utilities Commission of Sri Lanka | `LKA` | 2023–today | 15 min | excluded; included from 2025-07-11 | – | Sum of the dispatch of the plants; up to an hour for all data. |
| `so_ups` | System Operator of the Unified Energy System of Russia | 7 subdivisions of `RUS` | 2001–today | 1 h | unknown | – | One request a day, at least 3 seconds apart: slow. |
| `sonelgaz` | Sonelgaz (Algeria), on Mendeley Data | `DZA_RIN` | 2008–2020 | 1 h | unknown | – | Values divided by 125/148 to get MW. |
| `taipower` | Taipower (Taiwan), on Zenodo | `TWN` | 2017–2022 | 10 min | unknown | – | Sum of four areas. |
| `tepco` | Tokyo Electric Power Company | `JPN_Kantō` | 2016–2026 | 1 h | partial | – | The website refuses its monthly files (from 2025) outside Japan since 2026-10-22; OCCTO gives the same demand. |
| `tsoc` | Transmission System Operator of Cyprus | `CYP` | 2018–today | 15 min | included | – | Only years that have ended; corrects shifted times. |
| `wu_et_al` | Wu and Kan, on Zenodo (China) | 31 provinces of `CHN` | 2018 | 1 h | unknown | – | Modelled load: each day has the shape of a typical day. |
| `xm` | XM (Colombia) | `COL_SIN` | 2000–today | 1 h | unknown | – | Through a proxy, about 25 seconds a month. |

The [status page](../status.md) gives the numbers of countries, subdivisions and years of all the sources.

## Add a data source

1. Add the source to the [Awesome Electricity Demand](https://github.com/open-energy-transition/Awesome-Electricity-Demand) list first.
2. Write `<source>.py`, with `get_available_requests(code, start_date, end_date)` and `download_and_extract_data_for_request(request, code)`, and `<source>.yaml` without comments. `ons.py` and `hydroquebec.py` are good templates.
3. Add a test with a small synthetic fixture of the source's files.
4. Check it over the network with the [live check](../guides/check.md#live-check-of-the-data-sources), and run the [related entities](../guides/check.md#related-entities) check for its codes.

The [contributing guide](https://github.com/open-energy-transition/demandcast/blob/main/CONTRIBUTING.md#adding-an-electricity-demand-data-source) is the reference for the module interface and the YAML fields.
