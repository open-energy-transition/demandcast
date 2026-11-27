# Weather and socio-economic inputs

This page explains every input that DemandCast retrieves besides the electricity demand: where it comes from, how it is computed and which files hold it. Read it to understand the features and scaling variables of the models, or to check a value in the data folder.

You retrieve each input with `retrieve.py` and its `variable` option. The [retrieve guide](../guides/retrieve.md) lists all the options; this page names them where they change an input.

## Summary

| Input | `variable` | Past source | Future source | Folder (under the data folder) |
|---|---|---|---|---|
| Hourly electricity demand | `electricity_demand` | Public sources listed in the [Awesome Electricity Demand repository](https://github.com/open-energy-transition/Awesome-Electricity-Demand) (see [Electricity demand](electricity-demand.md)) | – | `electricity_demand/` |
| National annual electricity demand per capita | `annual_electricity_demand_per_capita` | [Ember](https://ember-energy.org/data/yearly-electricity-data/), completed by the [World Bank](https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC) scaled to Ember | Growth rates of the [IIASA SSP Database](https://tntcat.iiasa.ac.at/SspDb) | `annual_electricity_demand_per_capita/` |
| National population | `population` | [World Bank](https://data.worldbank.org/indicator/SP.POP.TOTL) | [IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp) | `population/` |
| National GDP PPP per capita | `gdp_ppp_per_capita` | Mean of the [World Bank](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD) and the [IMF](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)&INDICATOR=NGDPRPPPPC) | [IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp) | `gdp_ppp_per_capita/` |
| Gridded population | `gridded_population` | [SEDAC GPW v4](https://doi.org/10.7927/H49C6VHW) | [Wang X. et al. (2022)](https://doi.org/10.6084/m9.figshare.19608594) | `gridded_population/` |
| Gridded GDP PPP | `gridded_gdp_ppp` | [Wang T. et al. (2022)](https://zenodo.org/records/7898409) | [Wang T. et al. (2022)](https://zenodo.org/records/7898409) | `gridded_gdp_ppp/` |
| Gridded weather | `gridded_weather` | [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) | [CMIP6](https://cds.climate.copernicus.eu/datasets/projections-cmip6) | `gridded_weather/` |
| Temperature | `temperature` | [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) | [CMIP6](https://cds.climate.copernicus.eu/datasets/projections-cmip6) | `temperature/` |

The models use these inputs in two ways (see [Models](models.md)):

- **Features**: the temperature and its statistics, the local hour, weekday and month, the GDP PPP per capita and the annual electricity demand per capita.
- **Scaling**: a forecast turns the predicted shape of the demand into MW with the annual electricity demand per capita times the population.

The cleaning of the electricity demand also uses the annual electricity demand per capita and the population to flag years whose total looks wrong (see [Electricity demand](electricity-demand.md)).

The retrieved data is not redistributed, since the licences of many sources do not allow it. You retrieve it yourself, or share a data folder through a private bucket (see [Sync](../guides/sync.md)).

### Keys you need

| Input | Key in `demandcast/.env` |
|---|---|
| Annual electricity demand per capita | `EMBER_API_KEY`, a free key from Ember |
| Gridded weather, with `reanalysis_source: cds` (also what `points` means for `gridded_weather`) | `CDS_API_KEY`, a free account on the [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/how-to-api) |
| Temperature, with `reanalysis_source: points` (the default) or `cds` | `CDS_API_KEY` |
| Any future weather (climate models) | `CDS_API_KEY` |
| Population, GDP PPP per capita, gridded population, gridded GDP PPP | None |

With `reanalysis_source: arco`, the past weather needs no key. See [API keys and accounts](../guides/retrieve.md#api-keys-and-accounts) for how to set them.

## Scenarios, climate models and years

The future inputs follow scenarios. A **Shared Socioeconomic Pathway (SSP)** is a storyline of how the world develops: `SSP1` (sustainability) to `SSP5` (fossil-fuelled growth). The catalogue of DemandCast, `demandcast/utils/catalogue.py`, lists three kinds of scenarios:

| Kind | Examples | Used by | What the name means |
|---|---|---|---|
| SSP | `SSP1` … `SSP5` | Population, GDP PPP per capita, gridded population, gridded GDP PPP | The pathway alone. |
| IAMC | `SSP2-Baseline`, `SSP2-45` | Annual electricity demand per capita | A pathway with a climate target, given as the radiative forcing in 2100 in W/m² times 10 (`45` is 4.5 W/m²), or its `Baseline` without a target. |
| CMIP6 | `SSP2-4.5` | Gridded weather, temperature | A pathway with its radiative forcing in W/m². |

The 26 IAMC scenarios are `SSP1-Baseline`, `SSP1-19`, `SSP1-26`, `SSP1-34`, `SSP1-45`, `SSP2-Baseline`, `SSP2-19`, `SSP2-26`, `SSP2-34`, `SSP2-45`, `SSP2-60`, `SSP3-Baseline`, `SSP3-34`, `SSP3-45`, `SSP3-60`, `SSP4-Baseline`, `SSP4-26`, `SSP4-34`, `SSP4-45`, `SSP4-60`, `SSP5-Baseline`, `SSP5-19`, `SSP5-26`, `SSP5-34`, `SSP5-45` and `SSP5-60`.

A **climate model** simulates the future weather of a CMIP6 scenario. Each model runs only some scenarios:

| `climate_model` | Institute in | Scenarios |
|---|---|---|
| `CAMS-CSM1-0` | China | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `CESM2` | United States | `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `CNRM-ESM2-1` | France | `SSP1-1.9`, `SSP1-2.6`, `SSP4-3.4`, `SSP2-4.5`, `SSP4-6.0`, `SSP3-7.0`, `SSP5-8.5` |
| `EC-Earth3-Veg-LR` | Europe | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `HadGEM3-GC31-LL` | United Kingdom | `SSP1-2.6`, `SSP2-4.5`, `SSP5-8.5` |
| `MIROC-ES2L` | Japan | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `MPI-ESM1-2-LR` | Germany | `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |

The `scenario` and `climate_model` options accept any case: `ssp2-4.5` works. A wrong name stops the script with the list of valid ones. The years and scenarios you can ask for with `year`, `start_year`, `end_year` and `scenario` are in the table of each input below and in [Years, scenarios and climate models](../guides/retrieve.md#years-scenarios-and-climate-models).

The projections end in 2100. Past and future meet at different years for each input:

- The weather: the past is ERA5 from 1990 to last year; the future is the climate models from the current year. The current year is never taken from ERA5, so the statistics of a year, such as its mean temperature, always cover a whole year.
- Population and GDP PPP per capita: the future starts in the current year.
- Annual electricity demand per capita: the future starts the year after the last year with data of the country.

## Indicators: from yearly values to hourly files

Population, GDP PPP per capita and annual electricity demand per capita are **indicators**: one value per year. The retrieval stores them as hourly series, so that `assemble.py` can merge them with the hourly demand and temperature.

1. The script takes the codes of interest (see [Choose countries and subdivisions](../guides/retrieve.md#choose-countries-and-subdivisions)).
2. For each code, it finds the past years, the future years and the scenarios to save.
3. It gives every hour of a **local year** the value of that year. A local year runs from midnight on 1 January to the next midnight in the time zone of the code.
4. It stores each hour at its end, in UTC, like the electricity demand.
5. It writes one file for the past years and one per scenario.

| File | What it holds |
|---|---|
| `<code>.parquet` | The past years. |
| `<code>_<SCENARIO>.parquet` | The future years of one scenario, in upper case with underscores for hyphens: `FRA_SSP2.parquet`, `FRA_SSP2_BASELINE.parquet`, `FRA_SSP2_45.parquet`. |

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` (index) | End of the hour, in UTC without time zone. | – |
| `Annual electricity demand per capita (kWh)`, `Population` or `GDP PPP per capita (2021 international $)` | The value of the local year of the hour. | kWh per person, people, or 2021 international dollars per person |

A retrieval replaces only the years it computes, and keeps the other years already saved in the file. Hours with a missing or zero value are left out.

Some rules shape the years:

- **Gaps**: a year without data between two years with data takes the value of the year before it. The log warns about it.
- **Recent years**: population and GDP PPP per capita carry their last value forward up to last year, since the World Bank and the IMF publish with a delay. The annual electricity demand per capita does not: its past file ends at the last year with data, and its projections start the year after.
- **No projections**: some codes, such as Kosovo (`XKX`), have past data but no IIASA projections. They get only their past years: they are used for training, but not forecast for future scenarios.

## Annual electricity demand per capita

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| Ember (API, `EMBER_API_KEY`), then the World Bank scaled to Ember | First to last year with data of the country | – | `annual_electricity_demand_per_capita/<code>.parquet` |
| IIASA SSP Database v2.0: growth rates of the IAMC scenarios | Year after the last year with data, to 2100 | 26 IAMC | `annual_electricity_demand_per_capita/<code>_<SCENARIO>.parquet` |

The two past sources count different things:

- **Ember**: the electricity generated and imported, minus the exports. This is the electricity supplied, including the network losses and the generation off the networks of the system operators, such as rooftop solar and the plants of industries for their own use.
- **World Bank** (indicator EG.USE.ELEC.KH.PC, from the IEA): the production of the power plants minus the network losses and the own use of the plants. This is what the consumers use.

Ember is 12% higher in the median country: 1% to 5% where losses are small, such as Korea or Chile, and 15% to 21% where they are large, such as South Africa, Pakistan or Algeria. The hourly demand of the system operators includes their network losses, but not the generation off their networks. In the median national series, its yearly total is 0.94 times Ember and 1.05 times the World Bank. It gets closer to Ember as DemandCast adds the embedded generation to reach the gross demand (see [Electricity demand](electricity-demand.md)).

How the past values are computed:

1. Download Ember's yearly demand per capita of each country, without the regions that group countries.
2. Download the World Bank's electric power consumption per capita.
3. For each country, compute the ratio Ember / World Bank in every year that both have. The country's ratio is the median of these ratios if there are at least 3 such years; otherwise it is the median ratio of all the countries.
4. Take Ember's value where it exists. Elsewhere, take the World Bank's value times the ratio. This fills the years before 2000 and about 46 countries that Ember does not cover.
5. A subdivision gets the value of its country.

The two sources are not averaged, because an average of two definitions would jump wherever one of them is missing.

How the future values are computed:

1. Read the growth rates of the final energy of electricity per capita (`Final Energy|Electricity per capita`, in % per year). They come from the file `IAM_regional_annual_electricity_demand_per_capita_growth.xlsx`, downloaded by hand from the SSP Database into `demandcast/retrievals/socio_economic_data_sources/manual_downloads/`.
2. Each scenario has a rate for each of five world regions (`R5.2ASIA`, `R5.2LAM`, `R5.2MAF`, `R5.2OECD`, `R5.2REF`), for 2005, 2010, then every 10 years to 2090. `iam_regions_mapping.yaml`, next to the module, gives the region of each country. All the countries of a region share its rates.
3. Start from the last past value. For each following year, multiply the previous value by (1 + rate / 100). The rate of a year is that of the last year of the file before it.

The growth rates leave out the losses, as the World Bank does. Applying them to Ember's value assumes that the share of the losses stays the same.

## Population

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| World Bank (SP.POP.TOTL) | From the first year of the country (1960 for most) to last year | – | `population/<code>.parquet` |
| IIASA SSP Database (IIASA-WiC POP 2023) | Current year to 2100 | `SSP1` … `SSP5` | `population/<code>_<SSP>.parquet` |

How the population of a country is computed:

1. Download the World Bank population of each country. The aggregates, such as the world, are left out.
2. Read the IIASA projections from `IAM_national_population.csv` in `manual_downloads/`. They are in millions every five years from 2020; they are converted to people.
3. Interpolate the projections linearly between their years.

A **subdivision** gets a share of its country's population, so that the subdivisions of a country add up to its national population:

1. Sum the [gridded population](#gridded-population) inside the shape of the subdivision, and inside the shape of the whole country. The sum uses the global grid at 30 arc seconds (about 1 km), and counts only the cells whose centres are inside the shape. The people of a cell cut by a coast or a border are then counted where they live.
2. Divide the two sums: this is the share of the subdivision.
3. Interpolate the share linearly between the years of the grids.
4. Multiply the share by the national population of each year.

For past years, the shares come from GPW: every five years from 2000 to 2020, with the share of 2000 before 2000 and that of 2020 after 2020. For future years, they come from the gridded population of the same SSP. The share of a subdivision can therefore change between the last past year and the first future year.

The totals of the grids are not used directly, because they do not follow the national population. The grids of Australia are flat from 2000 to 2020, while its population grew by a third. The grids of the subdivisions of Mexico grew by 43%, while Mexico grew by 29%. With the shares, the demand of Ontario since 1994 and of the regions of the Australian market since 1998 can be used for training.

A country without World Bank or IIASA data, and each of its subdivisions, gets the sum of its own gridded population, interpolated between the years of the grids.

The sums of each code are saved in `gridded_population/totals/<code>.json`, with the **fingerprint** of its shape: a checksum of the shape. When the shape changes, the sums are computed again.

## GDP PPP per capita

GDP PPP is the gross domestic product at **purchasing power parity**: in international dollars, which buy the same goods in every country.

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| Mean of the World Bank (NY.GDP.PCAP.PP.KD) and the IMF World Economic Outlook (NGDPRPPPPC) | From the first year with data (1980 for most) to last year | – | `gdp_ppp_per_capita/<code>.parquet` |
| IIASA SSP Database (IIASA GDP 2023 divided by IIASA-WiC POP 2023) | Current year to 2100 | `SSP1` … `SSP5` | `gdp_ppp_per_capita/<code>_<SSP>.parquet` |

All values are in constant 2021 international dollars per person.

How the past values are computed:

1. Download the World Bank and IMF series. From the IMF, keep the three-letter country codes, and rename its codes of Kosovo (`KOS`) and Palestine (`WBG`) to `XKX` and `PSE`.
2. Where both have a value, take their mean. Where only one has it, take that one.
3. Drop the current year and later: the IMF also publishes forecasts.
4. A subdivision gets the value of its country.

How the future values are computed:

1. Divide the IIASA GDP PPP (billion USD of 2017) by the IIASA population (million) of each country, scenario and year from 2025, times 1000.
2. Convert from 2017 to 2021 dollars with the US consumer price index.
3. Interpolate linearly between the five-year steps.

The result is stored in the repository as `manual_downloads/IAM_national_gdp_ppp_per_capita.csv`. If you remove it, the script computes it again from `IAM_national_gdp_ppp.csv` and `IAM_national_population.csv`, downloads the price indices, and saves it in `gdp_ppp_per_capita/IAM_national_gdp_ppp_per_capita.csv` in the data folder.

A country without these data, and each of its subdivisions, gets its own [gridded GDP PPP](#gridded-gdp-ppp) divided by its own gridded population. Both are summed in its shape on the 0.25° grids, each cell weighted by the fraction of its area inside the shape, and interpolated between the years 2000, 2005, …, 2020 (and the SSP years after). The gridded GDP is converted from 2005 to 2021 dollars with the US consumer price index.

!!! note
    A code without national population and GDP PPP per capita is among the codes of interest only if it has an annual electricity demand per capita and its area is over 500 km² (see [Choose countries and subdivisions](../guides/retrieve.md#choose-countries-and-subdivisions)).

## Gridded population

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| SEDAC Gridded Population of the World v4.11 (population density, 30 arc seconds) | 2000, 2005, 2010, 2015, 2020 | – | `gridded_population/processed/<code>_0.25_deg_<year>.nc` |
| Wang X. et al. (2022) on Figshare (population count, 30 arc seconds) | 2025 to 2100, every 5 years | `SSP1` … `SSP5` | `gridded_population/processed/<code>_0.25_deg_<year>_<SSP>.nc` |

How it is computed:

1. Download the global grid of the year, if it is not in `gridded_population/raw/` yet. The past grids are files `<year>.tif`. Each SSP is an archive of about 2.5 GB, extracted into `raw/<SSP>/`.
2. For a past year, convert the density (people per km²) into a count: density times the area of the cell, which shrinks towards the poles.
3. Cut the grid to the bounds of the shape of each code (see [Shapes](#countries-subdivisions-and-shapes)).
4. Sum the cells into cells of 0.25°, the grid of ERA5. The centres of these cells are on the points of ERA5.
5. Save the grid of each code as NetCDF, with the bounds it was cut with.

The 0.25° grids are used to pick the most populous cells for the [temperature](#temperature), and to estimate the GDP PPP per capita of codes without national data. The population shares of subdivisions use the 30 arc-second global grids directly. The related-entities check also uses the gridded population (see [Models](models.md)).

## Gridded GDP PPP

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| Wang T. et al. (2022) on Zenodo (GDP PPP, 0.25°) | 2000 to 2020, every year | – | `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>.nc` |
| Same | 2025 to 2100, every 5 years | `SSP1` … `SSP5` | `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>_<SSP>.nc` |

How it is computed:

1. Download the archive `GDP_025d (2000-2100).7z` once and extract it into `gridded_gdp_ppp/raw/`. If this folder exists, nothing is downloaded.
2. Cut the global grid of each year and scenario to the bounds of the shape of each code, and save it as NetCDF.

The grid is already at 0.25°, so it is not resampled. Its unit is constant 2005 international dollars. It is used only for the GDP PPP per capita of codes without national data.

## Gridded weather

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| ERA5 reanalysis, 2 m temperature, hourly, 0.25° | 1990 to last year | – | `gridded_weather/processed/<code>_temperature_<year>.nc` |
| CMIP6 climate models, near-surface air temperature, daily | Current year to 2100 | Each model's CMIP6 scenarios | `gridded_weather/processed/<code>_temperature_<year>_<MODEL>_<SCENARIO>.nc` |

A **reanalysis** is a reconstruction of the past weather from observations and a weather model. ERA5 is the reanalysis of the European Centre for Medium-Range Weather Forecasts. Set `weather_variable: temperature`: it is required, and the only weather variable.

The file names have the model in upper case and the scenario with underscores, such as `FRA_temperature_2030_HADGEM3-GC31-LL_SSP2_4_5.nc`. The temperature is in kelvin, in the variable `t2m` for ERA5 and `tas` for CMIP6.

### Where the past weather comes from

`reanalysis_source` picks the source of ERA5. Both give the same values.

| `reanalysis_source` | Source | How it works |
|---|---|---|
| `cds` (also what `points` means here) | Copernicus Climate Data Store (CDS) | Each request waits in a queue, from minutes to hours. For more than five codes, the script downloads a year of the whole globe into `gridded_weather/raw/temperature_<year>.nc` and cuts each code from it. For five or fewer, it downloads a year of each code within its bounds. Data until about a week ago. |
| `arco` | [ARCO-ERA5](https://github.com/google-research/arco-era5), the analysis-ready ERA5 of Google Research on Google Cloud Storage | No account and no queue. It reads one global map per hour, a week at a time, for all codes at once (about 40 minutes a year for all codes). Same values as the CDS, rounded to 0.001 K. Data until about a week ago. Google gives no commitment to keep it up to date. |

The climate models always come from the CDS, with the same rule of more than five codes for a global download.

The files are large: on the order of 100 MB per country per year, about 5 GB a year for all the countries and subdivisions. Check your disk space first.

### When files are downloaded again

ERA5 is published about five days after real time, and updated every day until then. So a file of a year is downloaded again, at most once a day, when:

- it was written before 7 days after the end of its year, so its last days may still change or be missing; or
- it is a past year and its last hour is before 23:00 on 31 December, such as a broken or incomplete file.

The current year is read only by the temperature, west of UTC: its first hours end the last local year of these time zones.

A file of a code is also downloaded or extracted again when the bounds of its shape change. A grid cut from a global file is extracted again when the global file is newer.

## Temperature

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| ERA5 at the most populous cells (`reanalysis_source`: `points`, `cds` or `arco`) | 1990 to last year | – | `temperature/<code>_<year>.parquet` |
| CMIP6 climate models, from the gridded weather of the CDS | Current year to 2100 | Each model's CMIP6 scenarios | `temperature/<code>_<year>_<MODEL>_<SCENARIO>.parquet`, such as `FRA_2030_CESM2_SSP2_4_5.parquet` |

The temperature of a country or subdivision is the temperature where most of its people live. DemandCast keeps two series: that of the most populous cell (**Top 1**) and the mean of the three most populous cells (**Top 3**).

### Most populous cells

1. Load the 0.25° [gridded population](#gridded-population) of the code for the closest grid year. A past year uses 2000 to 2020; a future year uses 2025 to 2100 of the SSP of its CMIP6 scenario, such as `SSP2` for `SSP2-4.5`. The grid is retrieved first if it is missing.
2. Weight each cell by the fraction of its area inside the shape of the code. A populous cell mostly across the border, such as a city of a neighbouring country, then does not represent a small or narrow subdivision.
3. Rank the cells by this weighted population, and keep the top 1 and the top 3.
4. Take the temperature of the weather point closest to each cell. For a climate model, several cells can share the same model cell; it then counts once per cell.

### Where the past temperature comes from

| `reanalysis_source` | Source |
|---|---|
| `points` (default) | The [ERA5 time series](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries) of the CDS at the ERA5 points of the most populous cells. A few MB for all the years. |
| `cds` or `arco` | The [gridded weather](#gridded-weather) of the code, downloaded if needed. |

All three give the same values, because the population cells are on the ERA5 points.

With `points`, the whole series of a point, from 1990 to about a week ago, takes about 35 seconds and 4 MB. It is saved in `gridded_weather/raw/points/temperature_<latitude>_<longitude>.parquet`, such as `temperature_+48.75_+2.25.parquet`.

- **Updates**: a saved series is downloaded again from 120 days before its last hour, at most once a day. This happens only when the CDS may have later hours and the hours needed reach these 120 days. ERA5 first publishes preliminary data, replaced by final data two to three months later, so the last months may change. Earlier years are extracted again from the saved series without a download.
- **Queue**: the points are downloaded one at a time, since the CDS rejects more queued requests for this dataset. A rejected request is sent again every minute, for up to an hour.
- **Status**: the CDS describes this dataset as experimental. The grids remain available through `cds` and `arco`.

### Hourly values and local time

Each row is one hour, stored at its end in UTC, like the electricity demand. The electricity demand of an hour is its mean, so the temperature is the mean too:

- **ERA5**: the mean of the temperatures at the start and the end of the hour, which are instantaneous values.
- **Climate models**: they give daily means. Each day is placed at noon UTC, the hours between are interpolated linearly, and then averaged in the same way. The future hourly temperature therefore has no daily cycle. Models with calendars of 365 or 360 days are converted to the standard calendar; the missing days are interpolated.

A file holds the hours that start in its local year. The local hour, weekday, month and year of an hour are those of its start: the hour from 23:00 to midnight on a Friday is on a Friday. To cover a whole local year, the script also reads the years before and after it, when they exist.

### Columns

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` (index) | End of the hour, in UTC without time zone. | – |
| `Local hour of the day` | Local hour of the start of the hour, 0 to 23. | – |
| `Local weekend indicator` | 1 if the hour starts on a Saturday or Sunday in local time, else 0. | – |
| `Local month of the year` | Local month, 1 to 12. | – |
| `Local year` | Local year. | – |
| `Temperature - Top 1 (K)` | Temperature of the most populous cell. | K |
| `Temperature - Top 3 (K)` | Mean temperature of the three most populous cells. | K |
| `Monthly average temperature - Top 1 (K)` | Mean of Top 1 over the local month in this year. | K |
| `Monthly average temperature rank - Top 1` | Rank of this month by its mean, 1 for the warmest. Ties share an average rank. | – |
| `Annual average temperature - Top 1 (K)` | Mean of Top 1 over the local year. | K |
| `5 percentile temperature - Top 1 (K)` | 5th percentile of Top 1 over the local year. | K |
| `95 percentile temperature - Top 1 (K)` | 95th percentile of Top 1 over the local year. | K |

Only the hours that both Top 1 and Top 3 have are kept.

### When files are extracted again

A temperature file is extracted again when:

- it does not exist;
- it records another version of the processing, or none. The version changes when the extraction gives other values for the same weather, such as a new choice of cells;
- it records the fingerprint of another shape of its code, or none, since the shape decides the cells and their weights;
- it is ERA5, written more than a day ago, and before 7 days after the end of its year.

An extraction again uses the weather already downloaded. Only the weather of new cells is downloaded. The file records the version, the `reanalysis_source` and the shape fingerprint in its Parquet metadata.

## Countries, subdivisions and shapes

Each **entity**, a country or subdivision, has a shape (see the [glossary](glossary.md#entity)). `utils/shapes.py` gives the shape of any code:

- **Countries**: [Natural Earth](https://www.naturalearthdata.com/) at 1:50m, found by ISO alpha-3 code, or by name.
- **Standard subdivisions**, such as `USA_CAL`: the ISO 3166-2 subdivisions of Natural Earth at 1:50m.
- **Non-standard subdivisions, defined by the standard subdivisions that make them up**: built from Natural Earth at 1:10m and the definitions in `demandcast/shapes/subdivisions/` (see [Non-standard subdivisions](../guides/retrieve.md#non-standard-subdivisions)).

Small remote islands are cut away from Chile, Spain, Fiji, France, the Netherlands, Norway, New Zealand, Portugal, Russia, Chukotka (`RUS_CHU`) and the United States, together with the parts beyond 180° of longitude. They would add large weather downloads for little demand.

The grids of a code cover the **bounds** of its shape: its box, widened by 1° on each side, kept within -180° and 180°, and rounded to 0.25°. The NetCDF file of each grid records these bounds. When a shape moves its bounds, such as after a new run of `shapes/eia.py` or a new version of Natural Earth, the next retrieval cuts the population, GDP and weather grids of the code again from the global grids. A weather grid downloaded for that code alone is downloaded again. A grid without recorded bounds is cut again from the global grid, but a weather grid downloaded alone is kept.

What depends on the whole shape, not only on its bounds, records the shape's fingerprint instead: the population sums and the temperature. The fingerprint is a SHA-256 checksum of the shape, with its coordinates rounded to 10⁻⁶ degrees, so that another version of the geometry library gives the same checksum.

Each code also has a time zone, which sets its local years: the only time zone of a country, or that of its capital, and for a subdivision the time zone of its data sources, or that of the centre of its shape.

## Order of the retrievals

The retrievals fetch most of what they need themselves:

- `temperature` retrieves the gridded population and the gridded weather it needs, if they are missing or out of date. You do not need to run `gridded_population` or `gridded_weather` first.
- `population` reads the global population grids for the shares of subdivisions, and downloads them if needed.
- `gdp_ppp_per_capita` retrieves the gridded GDP PPP and population of the codes without national data, if needed.

One order matters: retrieve `population` and `annual_electricity_demand_per_capita` before `electricity_demand`. The cleaning compares each year of demand with the annual demand per capita times the population; without these files, it logs a warning and skips these annual flags (see [Electricity demand](electricity-demand.md)). All retrievals other than `electricity_demand` also need `checks/data_availability_summary.csv`, which comes with the code and which `check.py` writes again.

## Files of the inputs

| Folder | Files | What they hold |
|---|---|---|
| `annual_electricity_demand_per_capita/` | `<code>.parquet`, `<code>_<IAMC>.parquet` | Hourly series of the yearly values. |
| `population/` | `<code>.parquet`, `<code>_<SSP>.parquet` | Same. |
| `gdp_ppp_per_capita/` | `<code>.parquet`, `<code>_<SSP>.parquet`; `IAM_national_gdp_ppp_per_capita.csv` only if computed | Same. |
| `gridded_population/raw/` | `<year>.tif`, `<SSP>/<SSP>_<year>.tif` | Global grids, as downloaded. |
| `gridded_population/processed/` | `<code>_0.25_deg_<year>[_<SSP>].nc` | Population count of each code at 0.25°. |
| `gridded_population/totals/` | `<code>.json` | Population sums in the shape, with its fingerprint. |
| `gridded_gdp_ppp/raw/` | `GDP<year>.tif`, `GDP<year>_ssp<n>.tif` | Global grids, as extracted from the archive. |
| `gridded_gdp_ppp/processed/` | `<code>_0.25_deg_<year>[_<SSP>].nc` | GDP PPP of each code. |
| `gridded_weather/raw/` | `temperature_<year>[_<MODEL>_<SCENARIO>].nc`, `points/` | Global weather from the CDS, and the series of ERA5 points. |
| `gridded_weather/processed/` | `<code>_temperature_<year>[_<MODEL>_<SCENARIO>].nc` | Weather of each code. |
| `temperature/` | `<code>_<year>[_<MODEL>_<SCENARIO>].parquet` | Hourly temperature and its statistics. |

See [The data folder](../reference/data-folder.md) for the whole folder.
