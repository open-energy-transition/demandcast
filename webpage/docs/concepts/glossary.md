# Glossary

The terms of energy systems, weather and machine learning that this documentation uses, in alphabetical order. Each term has a link you can share, such as `glossary/#gross-demand`.

## A–C

### Annual electricity demand per capita

The electricity a country uses in a year divided by its population, in kWh per person. DemandCast multiplies it by the population to get the annual demand that the hourly forecast must add up to. See [Inputs](inputs.md).

### API key

A secret code that a website gives you to download its data. DemandCast reads the keys from `demandcast/.env`. See [Install](../getting-started/install.md#3-add-your-api-keys).

### ARCO-ERA5

A copy of [ERA5](#era5) on Google Cloud, readable without an account. One of the options of `reanalysis_source`.

### Bucket

A storage container in Google Cloud Storage. `sync.py` copies the data folder to and from a private bucket. See [Share the data folder](../guides/sync.md).

### CDS

The Copernicus Climate Data Store, which serves [ERA5](#era5) and the [CMIP6](#cmip6) climate projections. It needs the `CDS_API_KEY`.

### Climate model

A computer simulation of the future climate, such as `CESM2`. Each one gives a different possible future weather for the same [scenario](#scenario).

### CMIP6

The sixth Coupled Model Intercomparison Project: the set of [climate models](#climate-model) whose projections give the future temperature. Its scenarios are written like `SSP2-4.5`.

### Code

The name of an [entity](#entity): the ISO 3166 alpha-3 code of a country, such as `FRA`, or the code of the country and of a subdivision joined by an underscore, such as `USA_CAL`.

### Compiled data source

A data source that republishes the data of [system operators](#system-operator), such as the EIA or ENTSO-E. The combination prefers the operators' own data to a compiled copy.

### Cross-validation

A test of a model on [entities](#entity) that it never saw in training: each fold leaves out one entity (or one country with its subdivisions), trains on the rest, and measures the error on the one left out. It estimates the error for places without data. See [Cross-validate](../guides/cross-validate.md).

## D–F

### Data folder

The folder where the scripts write everything: `demandcast/data/`, or the folder named by the environment variable `DEMANDCAST_DATA_FOLDER`. See [Data folder](../reference/data-folder.md).

### Data source

A website or dataset that publishes hourly electricity demand, such as ENTSO-E. Each one has a Python module and a YAML file in `retrievals/electricity_demand_data_sources/`. See [Data sources](../reference/data-sources.md).

### Daylight saving time

The seasonal shift of clocks by one hour. DemandCast stores times in UTC, so a day in local time can have 23 or 25 hours.

### Embedded generation

Electricity generated inside the distribution networks or behind consumers' meters, such as rooftop solar. The network operators often do not see it, so their demand data can leave it out. See [net demand](#net-demand).

### Entity

A country or subdivision that DemandCast retrieves data for, trains on or forecasts, named by its [code](#code).

### ERA5

The global hourly record of past weather (a [reanalysis](#reanalysis)) produced by ECMWF, on a grid of 0.25° (about 25 km). DemandCast takes the past temperature from it.

### Feature

An input column that a model uses to predict the [target](#target), such as the temperature or the hour of the day. See [Models](models.md).

### Fingerprint

A checksum of everything that decided a file, such as the code, the reviews of flags or a shape, stored in the file. When the fingerprint no longer matches, the scripts make the file again.

### Flag

A mark on a period of the electricity demand that looks wrong and needs a person to look at it. A flag never removes values. See [Quality flags and reviews](flags.md).

## G–L

### GDP PPP

Gross domestic product at purchasing power parity: the value of what an economy produces, in international dollars that buy the same goods in every country. This makes incomes comparable across countries.

### Gross demand

All the electricity consumed, whatever generation supplies it, including rooftop solar and other [embedded generation](#embedded-generation). DemandCast models the gross demand. See [Electricity demand data](electricity-demand.md#gross-and-net-demand).

### IAMC scenario

A [scenario](#scenario) of the projections of annual electricity demand per capita: an [SSP](#ssp) with a target of radiative forcing, written like `SSP2-45`, or its baseline, `SSP2-Baseline`.

### Interval

The period that one value of a data source covers, such as 15 minutes or one hour. DemandCast stamps each value at the **end** of its interval.

### Load

Another word for electricity demand at a moment, in MW.

### Local day, local year { #local-day }

A day or a year in the local time of an entity, rather than in UTC. An hour belongs to the local day or year of its start.

### LSTM

Long short-term memory: a type of neural network for sequences. DemandCast offers it as an optional model. See [Models](models.md).

## M–R

### MAPE

Mean absolute percentage error: the average, over the hours, of the absolute error of each hour as a percentage of the actual demand of that hour. Hours of low demand weigh as much as hours of high demand. See [WAPE](#wape).

### Manifest

A JSON file that records where another file comes from. Two kinds exist:

- `<name>.manifest.json`, next to each assembled dataset, trained model and result, with the checksums of the file and of its inputs, the code version and the settings. The scripts check it before they use the file.
- `electricity_demand/raw/<data source>/manifest.json`, which lists the downloads (requests) of a data source and their versions.

See [Data folder](../reference/data-folder.md).

### Net demand

Demand that leaves out the part supplied by [embedded generation](#embedded-generation), as seen from the transmission network. On sunny days its midday dips as rooftop solar grows.

### Non-standard subdivision

A subdivision that is not an ISO 3166-2 region, such as a grid region. DemandCast defines its shape by the standard subdivisions that make it up, in `shapes/subdivisions/<ISO3>.yaml`.

### Reanalysis

A reconstruction of past weather, hour by hour on a grid, that combines observations with a weather model. [ERA5](#era5) is the one DemandCast uses.

### Related entities

Two entities whose areas overlap enough that the people of the shared area are at least 10% of the people of either one, such as a country and one of its regions. Training and cross-validation keep related entities together so that a model is never tested on data it has seen. See [Run checks](../guides/check.md).

### Resolution

The time between consecutive values of a data source, such as 15 minutes or one hour. DemandCast turns every resolution into hourly values.

### Review

Your decision about a [flag](#flag), written in `checks/reviewed_flags.yaml`. It gives a [verdict](#verdict) that decides what happens to the flagged hours. See [Quality flags and reviews](flags.md#reviews-of-flags).

## S–Z

### Scenario

One possible future. DemandCast uses three families: [SSP](#ssp) scenarios for population and GDP, [IAMC](#iamc-scenario) scenarios for the annual electricity demand per capita, and [CMIP6](#cmip6) scenarios for the climate.

### Solar time

Time set by the position of the sun rather than by the clock: noon is when the sun is highest. The midday flags use it, so that time zones and daylight saving do not move the midday hours.

### SSP

Shared Socioeconomic Pathway: one of five storylines of how the world's population and economy develop, from `SSP1` (sustainable growth) to `SSP5` (fossil-fuelled growth).

### System operator

The company that runs a power grid and measures its demand, such as RTE in France. Most demand data comes from them.

### Target

The value a model learns to predict. In DemandCast, it is the hourly demand relative to the annual demand, not the demand in MW. See [Models](models.md).

### Testing set, validation set, training set

The training set is the data a model learns from. The testing set is the data kept aside to measure its error, here the most recent year of each entity. The optional validation set is the year before, which XGBoost uses to decide when to stop training. See [Train and validate](../guides/train-validate.md).

### Verdict

The outcome of a [review](#review): `source_error`, `reading_error`, `net_demand`, `definition_change`, `real_event` or `false_positive`. See [Quality flags and reviews](flags.md#reviews-of-flags).

### WAPE

Weighted absolute percentage error: the sum of the absolute errors of all hours divided by the sum of the actual demand. Large systems and hours of high demand weigh the most. It is the main error measure of DemandCast. Lower is better.

### XGBoost

A widely used machine learning algorithm that builds many small decision trees, each correcting the errors of the previous ones. It is the default model of DemandCast. See [Models](models.md).
