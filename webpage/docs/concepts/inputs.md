# Weather and socio-economic inputs

This page explains every input that DemandCast retrieves besides the electricity demand: its source, how it is computed and what its files hold. You retrieve each with `retrieve.py` and its `variable` option; the [retrieve guide](../guides/retrieve.md) lists the options.

## Summary

| Input | `variable` | Past source | Future source |
|---|---|---|---|
| Hourly electricity demand | `electricity_demand` | Public sources listed in the [Awesome Electricity Demand repository](https://github.com/open-energy-transition/Awesome-Electricity-Demand) (see [Electricity demand](electricity-demand.md)) | – |
| National annual electricity demand per capita | `annual_electricity_demand_per_capita` | [Ember](https://ember-energy.org/data/yearly-electricity-data/), completed by the [World Bank](https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC) scaled to Ember | Growth rates of the [IIASA SSP Database](https://tntcat.iiasa.ac.at/SspDb) |
| National population | `population` | [World Bank](https://data.worldbank.org/indicator/SP.POP.TOTL) | [IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp) |
| National GDP PPP per capita | `gdp_ppp_per_capita` | Mean of the [World Bank](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD) and the [IMF](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)&INDICATOR=NGDPRPPPPC) | [IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp) |
| Gridded population | `gridded_population` | [SEDAC GPW v4](https://doi.org/10.7927/H49C6VHW) | [Wang X. et al. (2022)](https://doi.org/10.6084/m9.figshare.19608594) |
| Gridded GDP PPP | `gridded_gdp_ppp` | [Wang T. et al. (2022)](https://zenodo.org/records/7898409) | Same |
| Gridded weather | `gridded_weather` | [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) | [CMIP6](https://cds.climate.copernicus.eu/datasets/projections-cmip6) |
| Temperature | `temperature` | ERA5 | CMIP6 |

Each input has a folder of the same name in the data folder; [The data folder](../reference/data-folder.md#weather-and-gridded-data) lists every file. The models use the temperature, the GDP PPP per capita and the annual electricity demand per capita as [features](glossary.md#feature), and scale their forecasts with the annual electricity demand per capita times the population (see [Models](models.md)). The cleaning uses the annual electricity demand per capita and the population to flag years whose total demand looks wrong (see [flags](flags.md#annual-total-and-annual-change)).

The retrieved data is not redistributed, since the licences of many sources forbid it. You retrieve it yourself, or share a data folder through a private bucket (see [Sync](../guides/sync.md)).

The annual electricity demand per capita needs `EMBER_API_KEY`. The weather needs `CDS_API_KEY`, except the past weather with `reanalysis_source: arco`. The other inputs need no key. See [API keys and accounts](../guides/retrieve.md#api-keys-and-accounts).

## Scenarios, climate models and years

The future inputs follow scenarios. A **Shared Socioeconomic Pathway ([SSP](glossary.md#ssp))** is a storyline of how the world develops, from `SSP1` (sustainability) to `SSP5` (fossil-fuelled growth). `demandcast/utils/catalogue.py` lists three kinds of scenarios:

| Kind | Examples | Used by | What the name means |
|---|---|---|---|
| SSP | `SSP1` … `SSP5` | Population, GDP PPP per capita, gridded population, gridded GDP PPP | The pathway alone |
| [IAMC](glossary.md#iamc-scenario) | `SSP2-Baseline`, `SSP2-45` | Annual electricity demand per capita | A pathway with a climate target: the radiative forcing in 2100 in W/m² times 10 (`45` is 4.5 W/m²), or `Baseline` without a target |
| [CMIP6](glossary.md#cmip6) | `SSP2-4.5` | Gridded weather, temperature | A pathway with its radiative forcing in W/m² |

The 26 IAMC scenarios are `SSP<n>-Baseline` for each pathway, plus these targets: `19`, `26`, `34`, `45` for SSP1; `19` to `60` for SSP2 and SSP5; `34`, `45`, `60` for SSP3; `26` to `60` for SSP4 (for example `SSP3-60`).

A [climate model](glossary.md#climate-model) simulates the future weather of a CMIP6 scenario. Each model runs only some scenarios:

| `climate_model` | Institute in | Scenarios |
|---|---|---|
| `CAMS-CSM1-0` | China | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `CESM2` | United States | `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `CNRM-ESM2-1` | France | `SSP1-1.9`, `SSP1-2.6`, `SSP4-3.4`, `SSP2-4.5`, `SSP4-6.0`, `SSP3-7.0`, `SSP5-8.5` |
| `EC-Earth3-Veg-LR` | Europe | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `HadGEM3-GC31-LL` | United Kingdom | `SSP1-2.6`, `SSP2-4.5`, `SSP5-8.5` |
| `MIROC-ES2L` | Japan | `SSP1-1.9`, `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |
| `MPI-ESM1-2-LR` | Germany | `SSP1-2.6`, `SSP2-4.5`, `SSP3-7.0`, `SSP5-8.5` |

`scenario` and `climate_model` accept any case (`ssp2-4.5` works). A wrong name stops the script with the list of valid ones. The years you can ask for with `year`, `start_year` and `end_year` are in [Years, scenarios and climate models](../guides/retrieve.md#years-scenarios-and-climate-models).

The projections end in 2100. Past and future meet at a different year for each input:

| Input | Past | Future |
|---|---|---|
| Weather | ERA5, 1990 to last year | Climate models, from the current year. The current year is never taken from ERA5, so the statistics of a year always cover a whole year. |
| Population, GDP PPP per capita | To last year | From the current year |
| Annual electricity demand per capita | To the last year with data of the country | From the year after |

## Indicators: from yearly values to hourly files

Population, GDP PPP per capita and annual electricity demand per capita are **indicators**: one value per year, stored as hourly series so that `assemble.py` can merge them with the hourly demand and temperature.

1. For each code of interest (see [Choose countries and subdivisions](../guides/retrieve.md#choose-countries-and-subdivisions)), find the past years, the future years and the scenarios to save.
2. Give every hour of a [local year](glossary.md#local-day) the value of that year. A local year runs from midnight on 1 January to the next midnight in the time zone of the code.
3. Store each hour at its end, in UTC, like the electricity demand.
4. Write `<code>.parquet` for the past years and `<code>_<SCENARIO>.parquet` per scenario. The scenario is in upper case with underscores for hyphens: `FRA_SSP2.parquet`, `FRA_SSP2_BASELINE.parquet`, `FRA_SSP2_45.parquet`.

| Column | Meaning |
|---|---|
| `Time (UTC)` (index) | End of the hour, UTC without time zone |
| `Annual electricity demand per capita (kWh)`, `Population` or `GDP PPP per capita (2021 international $)` | The value of the local year of the hour (kWh per person, people, or 2021 international dollars per person) |

A retrieval replaces only the years it computes and keeps the others already in the file. Hours with a missing or zero value are left out.

Rules that shape the years:

- **Gaps**: a year without data between two years with data takes the value of the year before. The log warns about it.
- **Recent years**: population and GDP PPP per capita carry their last value forward up to last year, since the World Bank and the IMF publish late. The annual electricity demand per capita does not.
- **No projections**: some codes, such as Kosovo (`XKX`), have past data but no IIASA projections. They get only past years (used for training, never forecast), and the log says their future years are skipped.

## Annual electricity demand per capita

| Source | Years | Scenarios |
|---|---|---|
| Ember (API), then the World Bank scaled to Ember | First to last year with data of the country | – |
| IIASA SSP Database v2.0: growth rates | Year after the last year with data, to 2100 | 26 IAMC |

The two past sources count different things:

- **Ember**: electricity generated and imported, minus exports. This is the electricity supplied, including network losses and generation off the system operators' networks, such as rooftop solar and industrial plants for own use.
- **World Bank** (EG.USE.ELEC.KH.PC, from the IEA): power plant production minus network losses and the plants' own use. This is what the consumers use.

Ember is 12% higher in the median country: 1% to 5% where losses are small (Korea, Chile), 15% to 21% where they are large (South Africa, Pakistan, Algeria). The hourly demand of system operators includes their network losses but not the generation off their networks: in the median national series, its yearly total is 0.94 times Ember and 1.05 times the World Bank. Adding embedded generation for the [gross demand](electricity-demand.md#gross-and-net-demand) brings it closer to Ember.

Past values:

1. Download Ember's yearly demand per capita of each country, without the regions that group countries, and the World Bank's electric power consumption per capita.
2. For each country, compute the ratio Ember / World Bank in every year that both have. The country's ratio is their median if there are at least 3 such years; otherwise it is the median ratio of the countries that have one.
3. Take Ember's value where it exists, and elsewhere the World Bank's value times the ratio. This fills the years before 2000 and about 46 countries that Ember does not cover.
4. A subdivision gets the value of its country.

The two sources are not averaged, because an average of two definitions would jump wherever one is missing.

Future values:

1. Read the growth rates of `Final Energy|Electricity per capita` (% per year) from `IAM_regional_annual_electricity_demand_per_capita_growth.xlsx`, downloaded by hand from the SSP Database into `demandcast/retrievals/socio_economic_data_sources/manual_downloads/`.
2. Each scenario has a rate for each of five world regions (`R5.2ASIA`, `R5.2LAM`, `R5.2MAF`, `R5.2OECD`, `R5.2REF`) for 2005, 2010, then every 10 years to 2090. `iam_regions_mapping.yaml`, next to the module, gives the region of each country; all countries of a region share its rates.
3. Start from the last past value, and multiply each year by (1 + rate / 100). The rate of a year is that of the last year of the file before it (the first rate for years up to the first year of the file).

The growth rates leave out the losses, as the World Bank does. Applying them to Ember's value assumes that the share of the losses stays the same.

## Population

| Source | Years | Scenarios |
|---|---|---|
| World Bank (SP.POP.TOTL) | First year of the country (1960 for most) to last year | – |
| IIASA SSP Database (IIASA-WiC POP 2023) | Current year to 2100 | `SSP1` … `SSP5` |

For a country, the World Bank gives the past (aggregates such as the world are left out). The IIASA projections, in `IAM_national_population.csv` in `manual_downloads/`, are in millions every five years; they are converted to people and interpolated linearly.

A **subdivision** gets a share of its country's population, so the subdivisions of a country add up to its national population:

1. Sum the [gridded population](#gridded-population) inside the shape of the subdivision and inside the shape of the whole country. The sum uses the global 30-arc-second grid (about 1 km) and counts only cells whose centres are inside the shape, so the people of a cell cut by a coast or border are counted where they live.
2. The share is the ratio of the two sums, interpolated linearly between the years of the grids.
3. Multiply the share by the national population of each year.

Past shares come from GPW, every five years from 2000 to 2020 (the 2000 share before 2000, the 2020 share after 2020). Future shares come from the gridded population of the same SSP, so a share can jump between the last past year and the first future year.

Grid totals are not used directly because they do not follow the national population: Australia's grids are flat from 2000 to 2020 while its population grew by a third, and Mexico's subdivisions grew by 43% while Mexico grew by 29%. Shares also give past years before 2000, so the demand of Ontario since 1994 and of the Australian market regions since 1998 can train the models.

A country without World Bank or IIASA data, and each of its subdivisions, gets the sum of its own gridded population, interpolated between the grid years.

The sums are saved in `gridded_population/totals/<code>.json` with the [fingerprint](glossary.md#fingerprint) of the shape, and computed again when the shape changes.

## GDP PPP per capita

GDP PPP is the gross domestic product at [purchasing power parity](glossary.md#gdp-ppp): in international dollars, which buy the same goods in every country. All values are in constant 2021 international dollars per person.

| Source | Years | Scenarios |
|---|---|---|
| Mean of the World Bank (NY.GDP.PCAP.PP.KD) and the IMF World Economic Outlook (NGDPRPPPPC) | First year with data (1980 for most) to last year | – |
| IIASA SSP Database (IIASA GDP 2023 divided by IIASA-WiC POP 2023) | Current year to 2100 | `SSP1` … `SSP5` |

Past values:

1. Download the World Bank and IMF series. From the IMF, keep the three-letter country codes, and rename Kosovo (`KOS`) and Palestine (`WBG`) to `XKX` and `PSE`.
2. Take the mean where both have a value, or the one that has it.
3. Drop the current year and later, since the IMF also publishes forecasts.
4. A subdivision gets the value of its country.

Future values:

1. For each country, scenario and year from 2025, divide the IIASA GDP PPP (billion 2017 USD) by the IIASA population (million), and multiply by 1000 to get dollars per person.
2. Convert from 2017 to 2021 dollars with the US consumer price index.
3. Interpolate linearly between the five-year steps.

The result is in the repository as `manual_downloads/IAM_national_gdp_ppp_per_capita.csv`. Without it, the script computes it from `IAM_national_gdp_ppp.csv` and `IAM_national_population.csv`, downloading the price indices, and saves it as `gdp_ppp_per_capita/IAM_national_gdp_ppp_per_capita.csv` in the data folder.

A country without these data, and each of its subdivisions, gets its own [gridded GDP PPP](#gridded-gdp-ppp) divided by its own gridded population. Both are summed in its shape on the 0.25° grids, each cell weighted by the fraction of its area inside the shape, and interpolated between the grid years. The gridded GDP is converted from 2005 to 2021 dollars with the US consumer price index.

!!! note
    A code without national population and GDP PPP per capita is among the codes of interest only if it has an annual electricity demand per capita and its area is over 500 km² (see [Choose countries and subdivisions](../guides/retrieve.md#choose-countries-and-subdivisions)).

## Gridded population

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| SEDAC Gridded Population of the World v4.11 (density, 30 arc seconds) | 2000 to 2020, every 5 years | – | `gridded_population/processed/<code>_0.25_deg_<year>.nc` |
| Wang X. et al. (2022) on Figshare (count, 30 arc seconds) | 2025 to 2100, every 5 years | `SSP1` … `SSP5` | `gridded_population/processed/<code>_0.25_deg_<year>_<SSP>.nc` |

1. Download the global grid of the year into `gridded_population/raw/` if it is not there yet: `<year>.tif` for the past, or an archive of about 2.5 GB per SSP, extracted into `raw/<SSP>/`.
2. For a past year, convert the density (people per km²) into a count: density times the area of the cell, which shrinks towards the poles.
3. Cut the grid to the [bounds](#countries-subdivisions-and-shapes) of the shape of each code.
4. Sum the cells into 0.25° cells, whose centres are on the points of ERA5.
5. Save the grid of each code as NetCDF, with the bounds it was cut with.

The 0.25° grids pick the most populous cells for the [temperature](#temperature), give the GDP PPP per capita of codes without national data, and feed the related-entities check (see [Models](models.md)). The population shares of subdivisions use the 30-arc-second global grids.

## Gridded GDP PPP

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| Wang T. et al. (2022) on Zenodo (GDP PPP, 0.25°) | 2000 to 2020, every year | – | `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>.nc` |
| Same | 2025 to 2100, every 5 years | `SSP1` … `SSP5` | `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>_<SSP>.nc` |

The archive `GDP_025d (2000-2100).7z` is downloaded once and extracted into `gridded_gdp_ppp/raw/`; if that folder exists, nothing is downloaded. The global grid of each year and scenario is then cut to the bounds of each code's shape and saved as NetCDF, without resampling. Its unit is constant 2005 international dollars. It is used only for the GDP PPP per capita of codes without national data.

## Gridded weather

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| ERA5 [reanalysis](glossary.md#reanalysis), 2 m temperature, hourly, 0.25° | 1990 to last year | – | `gridded_weather/processed/<code>_temperature_<year>.nc` |
| CMIP6 climate models, near-surface air temperature, daily | Current year to 2100 | Each model's scenarios | `gridded_weather/processed/<code>_temperature_<year>_<MODEL>_<SCENARIO>.nc` |

Set `weather_variable: temperature`: it is required, and the only weather variable. File names have the model in upper case and the scenario with underscores, such as `FRA_temperature_2030_HADGEM3-GC31-LL_SSP2_4_5.nc`. The temperature is in kelvin, in the variable `t2m` for ERA5 and `tas` for CMIP6.

### Where the past weather comes from

`reanalysis_source` picks the source of ERA5. Both give the same values, with data until about a week ago.

| `reanalysis_source` | Source | How it works |
|---|---|---|
| `cds` (`points`, the default, means `cds` here) | Copernicus Climate Data Store ([CDS](glossary.md#cds)) | Each request waits in a queue, from minutes to hours. For more than five codes, the script downloads a year of the whole globe into `gridded_weather/raw/temperature_<year>.nc` and cuts each code from it. For five or fewer, it downloads a year of each code within its bounds. |
| `arco` | [ARCO-ERA5](https://github.com/google-research/arco-era5), the analysis-ready ERA5 of Google Research on Google Cloud Storage | No account and no queue. It reads one global map per hour, a week at a time, for all codes at once (about 40 minutes a year). Values are rounded to 0.001 K. Google gives no commitment to keep it up to date. |

The climate models always come from the CDS, with the same five-code rule.

The files are large, about 5 GB a year for all codes. Check your disk space first.

### When files are downloaded again

ERA5 is published about five days after real time and updated daily until then. So a reanalysis file is downloaded again, at most once a day, when:

- it was written less than 7 days after the end of its year, so its last days may still change or be missing; or
- it is a past year and its last hour is before 23:00 on 31 December, such as a broken file.

Only the temperature reads ERA5 in the current year: west of UTC, the last hours of a local year fall in the first hours of the next year in UTC.

A file of a code is also downloaded or extracted again when the bounds of its shape change. A grid cut from a global file is extracted again when the global file is newer.

## Temperature

| Source | Years | Scenarios | Output file |
|---|---|---|---|
| ERA5 at the most populous cells (`reanalysis_source`: `points`, `cds` or `arco`) | 1990 to last year | – | `temperature/<code>_<year>.parquet` |
| CMIP6 climate models, from the gridded weather of the CDS | Current year to 2100 | Each model's scenarios | `temperature/<code>_<year>_<MODEL>_<SCENARIO>.parquet`, such as `FRA_2030_CESM2_SSP2_4_5.parquet` |

The temperature of a country or subdivision is the temperature where most of its people live: that of the most populous cell (**Top 1**) and the mean of the three most populous cells (**Top 3**).

### Most populous cells

1. Load the 0.25° [gridded population](#gridded-population) of the code for the closest grid year: 2000 to 2020 for a past year, or 2025 to 2100 of the SSP of the CMIP6 scenario (`SSP2` for `SSP2-4.5`). The grid is retrieved first if it is missing.
2. Weight each cell by the fraction of its area inside the shape, so a populous cell mostly across the border does not represent a small or narrow subdivision.
3. Rank the cells by this weighted population, and keep the top 1 and the top 3.
4. Take the temperature of the weather point closest to each cell. With a climate model, several cells can share one model cell; it then counts once per cell.

### Where the past temperature comes from

| `reanalysis_source` | Source |
|---|---|
| `points` (default) | The [ERA5 time series](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries) of the CDS at the ERA5 points of the most populous cells: a few MB for all years |
| `cds` or `arco` | The [gridded weather](#gridded-weather) of the code, downloaded if needed |

All three give the same values, because the population cells are on the ERA5 points.

With `points`, the series of a point, from 1990 to about a week ago, takes about 35 seconds and 4 MB. It is saved in `gridded_weather/raw/points/temperature_<latitude>_<longitude>.parquet`, such as `temperature_+48.75_+2.25.parquet`.

- **Updates**: ERA5 first publishes preliminary data, replaced by final data two to three months later. So the last 120 days of a saved series are downloaded again, at most once a day, when the CDS may have newer hours and the years you ask for reach into those 120 days. Earlier years are extracted again without a download.
- **Queue**: points are downloaded one at a time, since the CDS rejects more queued requests for this dataset. A rejected request is retried every minute, for up to an hour.
- **Status**: the CDS calls this dataset experimental. The grids remain available through `cds` and `arco`.

### Hourly values and local time

Each row is one hour, stored at its end in UTC. The electricity demand of an hour is its mean, so the temperature is too:

- **ERA5**: the mean of the instantaneous temperatures at the start and the end of the hour.
- **Climate models**: they give daily means. Each day is placed at noon UTC, the hours between are interpolated linearly, then averaged the same way. So the future hourly temperature has no daily cycle. Calendars of 365 or 360 days are converted to the standard calendar, and the missing days are interpolated.

A file holds the hours that start in its local year; the local hour, weekday, month and year of an hour are those of its start (23:00 to midnight on a Friday is on a Friday). To cover a whole local year, the script also reads the neighbouring years when they exist.

### Columns

| Column | Meaning |
|---|---|
| `Time (UTC)` (index) | End of the hour, UTC without time zone |
| `Local hour of the day` | Local hour of the start of the hour, 0 to 23 |
| `Local weekend indicator` | 1 if the hour starts on a local Saturday or Sunday, else 0 |
| `Local month of the year` | Local month, 1 to 12 |
| `Local year` | Local year |
| `Temperature - Top 1 (K)` | Temperature of the most populous cell |
| `Temperature - Top 3 (K)` | Mean temperature of the three most populous cells |
| `Monthly average temperature - Top 1 (K)` | Mean of Top 1 over the local month in this year |
| `Monthly average temperature rank - Top 1` | Rank of this month by its mean, 1 for the warmest; ties share an average rank |
| `Annual average temperature - Top 1 (K)` | Mean of Top 1 over the local year |
| `5 percentile temperature - Top 1 (K)` | 5th percentile of Top 1 over the local year |
| `95 percentile temperature - Top 1 (K)` | 95th percentile of Top 1 over the local year |

Only the hours that both Top 1 and Top 3 have are kept.

### When files are extracted again

A temperature file records the version of the processing, the `reanalysis_source` and the shape fingerprint in its Parquet metadata. It is extracted again when:

- it does not exist;
- it records another processing version, or none. The version changes when the extraction gives other values for the same weather, such as a new choice of cells;
- it records the fingerprint of another shape, or none, since the shape decides the cells and their weights;
- it is ERA5, written more than a day ago, and less than 7 days after the end of its year.

Extracting again reuses the weather already downloaded; only the weather of cells not used before is downloaded.

## Countries, subdivisions and shapes

Each [entity](glossary.md#entity) has a shape, which `utils/shapes.py` gives for any code:

- **Countries**: [Natural Earth](https://www.naturalearthdata.com/) at 1:50m, by ISO alpha-3 code or by name.
- **Standard subdivisions**, such as `USA_CAL`: the ISO 3166-2 subdivisions of Natural Earth at 1:50m.
- **Non-standard subdivisions, defined by the standard subdivisions that make them up**: built from Natural Earth at 1:10m and the definitions in `demandcast/shapes/subdivisions/` (see [Non-standard subdivisions](../guides/retrieve.md#non-standard-subdivisions)).

Small remote islands are cut away from Chile, Spain, Fiji, France, the Netherlands, Norway, New Zealand, Portugal, Russia, Chukotka (`RUS_CHU`) and the United States, together with the parts beyond 180° of longitude. They would add large weather downloads for little demand.

The grids of a code cover the **bounds** of its shape: its box widened by 1° on each side, kept within −180° and 180°, and rounded to 0.25°. Each NetCDF grid records its bounds. When the bounds move, such as after a run of `shapes/eia.py` or a new version of Natural Earth, the next retrieval cuts the population, GDP and weather grids of the code again from the global grids, and downloads again a weather grid that was downloaded for that code alone. A grid without recorded bounds is cut again from the global grid, but a weather grid downloaded alone is kept.

What depends on the whole shape, not only its bounds, records the shape's fingerprint instead: the population sums and the temperature. The fingerprint is a SHA-256 checksum of the shape with its coordinates rounded to 10⁻⁶ degrees, so another version of the geometry library gives the same checksum.

Each code also has a time zone, which sets its local years. A country with one time zone has that one, and otherwise the time zone of its capital. A subdivision has the time zone given for it in the YAML files of its data sources, or that of the centre of its shape.

## Order of the retrievals

The retrievals fetch most of what they need themselves:

- `temperature` retrieves the gridded population and gridded weather it needs, if missing or out of date.
- `population` downloads the global population grids for the shares of subdivisions, if needed.
- `gdp_ppp_per_capita` retrieves the gridded GDP PPP and population of codes without national data, if needed.

Retrieve `population` and `annual_electricity_demand_per_capita` before `electricity_demand`: without them, the cleaning skips the [annual flags](flags.md#annual-total-and-annual-change). All retrievals other than `electricity_demand` also need `checks/data_availability_summary.csv`, which comes with the code and which `check.py` writes again. The full order is in [Recommended order](../guides/retrieve.md#recommended-order).
