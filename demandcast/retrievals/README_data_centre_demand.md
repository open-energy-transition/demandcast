# Data centre demand profiles

This note describes how the hourly electricity demand profile of data
centres in the Philippines (`PHL`) is built from measured UK data. It
covers two scripts, run in this order:

1. [UKPN data centre profiles](#ukpn-data-centre-profiles):
   [`ukpn_data_centres.py`](electricity_demand_data_sources/ukpn_data_centres.py)
   downloads the half-hourly demand of UK data centres and summarises
   it into average daily shapes.
2. [Philippines data centre demand](#philippines-data-centre-demand):
   [`phl_data_centre_demand.py`](electricity_demand_data_sources/phl_data_centre_demand.py)
   maps those shapes onto an hourly Philippine calendar and scales them
   to MW.

Neither script is a regular electricity demand data source (there is no
yaml file, and they are not run by `retrieve.py`). The UKPN data
describes individual sites, not the demand of a country or subdivision.

## UKPN data centre profiles

### Source

| Source | Coverage | What is used |
|---|---|---|
| [UK Power Networks (UKPN) Open Data Portal](https://ukpowernetworks.opendatasoft.com/explore/assets/ukpn-data-centre-demand-profiles/) | 1 January 2023 to the latest update, half-hourly | Utilisation ratio of each anonymised data centre site |

UKPN is a distribution network operator covering London, the South East
and the East of England. For each site, the dataset gives:

- `hh_utilisation_ratio`: the import apparent power (kVA) summed over
  the site's meter points, divided by the sum of their maximum import
  capacities (MIC, the capacity agreed in the connection agreement).
  A value of 0.4 means the site imported 40% of its agreed capacity.
- `dc_type`: the estimated data centre type (see below).
- `cleansed_voltage_level`: the voltage level of the connection.

The two data centre types are:

- **Co-located** (colocation): one operator provides the building,
  power and cooling, and many customers rent space for their own
  servers. The load of many tenants averages out, so it is very steady.
- **Enterprise**: a data centre owned and run by one organisation (for
  example a bank or a government department) for its own IT. Its load
  follows that organisation's working pattern more closely.

The type is estimated by UKPN, so it may be wrong for some sites. Very
large hyperscale campuses usually connect to the transmission network,
and are likely not in the data.

### Access

The dataset is only visible to registered users. Create a free account
on the [UKPN Open Data Portal](https://ukpowernetworks.opendatasoft.com),
generate an API key in the account settings, and add it to the `.env`
file of the `demandcast` folder:

```
UKPN_API_KEY=<your_key>
```

The whole dataset is downloaded in one request through the Parquet
export endpoint. An invalid key raises an error, and so does an empty
dataset, which is what the portal returns to accounts without access.

### Method

#### 1. Exclude unreliable sites

A site is excluded from the profiles if it meets any of these criteria
(set at the top of the script):

| Constant | Value | Excludes | Reason |
|---|---|---|---|
| `MIN_MEAN_UTILISATION` | 0.015 | Sites with a mean utilisation below the value | No import, or a meter that is not reporting. Dividing by a mean close to zero turns noise into very large values. |
| `MAX_ZERO_SHARE` | 0.8 | Sites whose utilisation is 0 in more than 80% of half-hours | The profile is dominated by short bursts of import, which are likely metering errors. |
| `MAX_MEDIAN_UTILISATION` | 1 | Sites whose median utilisation is above 1 | The import is above the capacity most of the time, so the capacity is likely wrong or out of date. |

All other values are kept as they are, including zeros (outages,
maintenance, or periods before a site starts importing) and occasional
values above 1 (short exceedances of the agreed capacity, or metering
errors). The log lists the sites excluded by each criterion.

With the data downloaded on 2026-09-25, 82 of 96 sites are included (68
co-located and 14 enterprise). Apart from the low-load sites, the
excluded sites are:

- Data Centre #93: zero almost always, apart from an 18-day burst in
  July 2025 reaching 4 times its capacity.
- Data Centre #32: zero 86% of the time, with short bursts.
- Data Centre #67: above its capacity for three years (median about
  1.4), then about 0.3 in 2026.

#### 2. Normalise each site

The utilisation of each site is divided by its mean over its whole
record:

```
normalised(site, t) = utilisation(site, t) / mean utilisation(site)
```

A value of 1 is the site's average. This removes the differences in
size and occupancy between sites, so that the shapes of their profiles
can be averaged, and so that a shape can be scaled to any other country.
Dividing by the mean (rather than the maximum) means that a profile with
a mean of 1, multiplied by an average demand, keeps the right total
energy.

#### 3. Average in two steps

Each profile is averaged first for each site, then across the sites of
each data centre type. Every site is weighted equally, so that sites
with longer records, or higher utilisation, do not dominate. The
`sites` column of each output gives the number of sites behind each
value.

All profiles use the local time of the data (`Europe/London`).

#### 4. Profiles

| Profile | Function | Grouped by |
|---|---|---|
| Diurnal | `get_diurnal_profiles` | Type, day type (weekday or weekend), local half-hour |
| Holiday | `get_holiday_profiles` | Type, day type (weekday, weekend, or bank holiday group), local half-hour |
| Seasonal | `get_seasonal_profiles` | Type, season, day type (weekday or weekend), local half-hour |
| Monthly | `get_monthly_profiles` | Type, month of the year |

- **Day types**: weekdays are Monday to Friday. In the diurnal and
  seasonal profiles, bank holidays count as the weekday or weekend day
  they fall on.
- **Bank holidays** are those of England, from the `holidays` package.
  They are grouped by `HOLIDAY_GROUPS`: Christmas and New Year
  (Christmas Day, Boxing Day, New Year's Day), Easter (Good Friday,
  Easter Monday), and other bank holidays (May Day, the Spring and Late
  Summer bank holidays, and one-off holidays such as the 2023
  Coronation). The data has 11, 8 and 13 days in these groups.
- **Seasons** are set by `SEASONS`: winter is December to February, and
  summer is June to August. Each site is normalised by the mean of its
  whole record before the seasons are selected, so that their levels can
  be compared.

Each profile has two values: `mean_utilisation` (the utilisation ratio)
and `mean_normalised` (the shape, 1 = site average). The shape (`mean_normalised`) is the
one to use for other countries.

#### 5. Site summary

`summarise_sites` gives one row per site (including the excluded
sites), with its type, voltage level, period covered, whether it is
included, and these statistics of its utilisation:

| Statistic | Definition |
|---|---|
| Mean, median, 5th and 95th percentile, maximum | Of the half-hourly utilisation ratio |
| Load factor | Mean / maximum. Close to 1 is a flat load. |
| Daily swing | Average daily (maximum − minimum), divided by the mean |
| Weekend / weekday ratio | Weekend mean / weekday mean |
| Monthly variation | Coefficient of variation of the monthly means |

### Outputs

Files are saved in `data/data_centre_demand_profiles/<date>/`, where
`<date>` is the day of the run:

| File | Content |
|---|---|
| `ukpn_data_centre_profiles.parquet` | The half-hourly data, as downloaded |
| `site_summary.csv` | Statistics of each site, and whether it is included |
| `diurnal_profiles.csv` / `.png` | Weekday and weekend shapes by type |
| `holiday_profiles.csv` / `.png` | Bank holiday shapes, compared with weekdays and weekends |
| `seasonal_profiles.csv` / `.png` | Summer and winter shapes, for weekdays and weekends |
| `monthly_profiles.csv` / `.png` | Monthly shape by type |
| `site_statistics.png` | Load factor and mean utilisation of the sites, by type |

The script also prints the median statistics of the included sites by
type.

### Results

With the data downloaded on 2026-09-25 (1 January 2023 to 17 September
2026):

**Data centre demand is nearly flat.** All average profiles stay within
about 0.91–1.12 of the site mean (0.94–1.07 for the weekday and weekend
shapes).

| | Co-located | Enterprise |
|---|---|---|
| Sites | 68 | 14 |
| Median mean utilisation of the sites | 0.20 | 0.21 |
| Weekday daily mean (range over the day) | 1.012 (0.964–1.061) | 1.015 (0.963–1.071) |
| Weekend daily mean (range over the day) | 0.971 (0.958–0.984) | 0.962 (0.942–0.983) |
| Christmas and New Year daily mean | 0.965 | 0.915 |
| Summer / winter weekday daily mean | 1.016 / 1.032 | 1.033 / 1.006 |

- **Weekday vs weekend is the clearest pattern.** Weekdays are about
  4–5% higher than weekends, with a working-hours rise that peaks at
  about 14:00–15:00. Weekends are almost flat.
- **Bank holidays are close to weekends.** The exception is Christmas
  and New Year at enterprise sites, about 5% below a weekend.
- **There is no clear seasonal pattern for co-located sites.** Winter is
  slightly higher than summer, and the monthly means (highest in
  January–February, lowest in October) do not follow cooling. They are
  likely affected by sites that start or stop importing during the
  record. Enterprise sites are 2–3% higher in summer, from few sites.
- **Utilisation is low.** Sites import about 20–25% of their agreed
  capacity on average, because connections are sized well above use.

## Philippines data centre demand

### Method

1. **Read the UKPN shapes.** The script reads `diurnal_profiles.csv`
   from the latest UKPN results folder (or from `UKPN_DATE`), and uses
   the `mean_normalised` column.
2. **Weight the data centre types.** The co-located and enterprise
   shapes are combined with the weights in `DC_TYPE_WEIGHTS`.
3. **Convert to hourly.** The two half-hours of each hour are averaged
   (for example, 00:00 and 00:30 give the hour starting at 00:00).
4. **Build the Philippine calendar.** Every hour from `START_DATE` to
   `END_DATE` (both included) is created in local time (`Asia/Manila`,
   UTC+8, no daylight saving time).
5. **Map the day types.** Monday to Friday uses the weekday shape, and
   Saturday and Sunday use the weekend shape. If
   `TREAT_HOLIDAYS_AS_WEEKENDS` is `True`, the public holidays of the
   Philippines (from the `holidays` package) also use the weekend shape.
   Each hour is matched by its **local clock hour**: 14:00 in Manila uses
   the UK shape at 14:00 London time, because the shape follows the local
   working day.
6. **Rescale to a mean of 1.** The profile is divided by its own mean
   over the period, so that annual energy matches the inputs, whatever
   the mix of weekdays, weekends and holidays.
7. **Scale to MW.** If the capacity parameters are set:

   ```
   average demand (MW) = CAPACITY_MW × UTILISATION × OCCUPANCY × PUE
   demand (MW, t)      = average demand × normalised demand(t)
   ```

### Settings

All settings are constants at the top of the script.

| Constant | Description |
|---|---|
| `START_DATE`, `END_DATE` | First and last day of the profile, as `DD-MM-YYYY` (both included). Periods of several years work. |
| `DC_TYPE_WEIGHTS` | Weight of the UKPN shape of each type, for example `{"Co-located": 1.0, "Enterprise": 0.0}` for co-located only |
| `TREAT_HOLIDAYS_AS_WEEKENDS` | Whether Philippine public holidays use the weekend shape |
| `CAPACITY_MW`, `UTILISATION`, `OCCUPANCY`, `PUE` | Parameters of the average demand. If `CAPACITY_MW`, `UTILISATION` or `OCCUPANCY` is `None`, only the normalised profile is saved. |
| `UKPN_DATE` | Date of the UKPN results to use (`YYYY-MM-DD`). `None` uses the latest. |

#### Choosing the capacity and PUE

The UKPN shapes are measured at the grid connection, so they already
include cooling and other non-IT loads. **Do not apply PUE to the
shape.** Whether PUE is needed depends only on what `CAPACITY_MW`
measures:

| `CAPACITY_MW` is… | PUE | Utilisation to use |
|---|---|---|
| Contracted (grid) capacity, which already includes cooling | `PUE = 1` | Grid import / contracted capacity. UKPN sites average about 0.20–0.25. |
| IT capacity, which excludes cooling | The PUE of the Philippines, assumed to be 1.5 | IT load / IT capacity, typically much higher than grid utilisation |

Mixing the two (for example, IT capacity with the UKPN grid utilisation
of about 0.2) gives a wrong average demand. If the capacity is in MVA,
multiply by a power factor (about 0.95–0.99) to get MW. As default, the `CAPACITY_MW` is in MW

### Output

Files are saved in `data/data_centre_demand_profiles/PHL/`, named
`phl_data_centre_demand_<start>_<end>_<YYYYmmdd-HHMMSS>.csv` and `.png`,
where the last part is the time of the run, so that runs do not
overwrite each other.

| Column | Description |
|---|---|
| `Time (UTC)` | Start of the hour in UTC |
| `Local time` | Start of the hour in `Asia/Manila` |
| `Day type` | `Weekday` or `Weekend` (including holidays, if enabled) |
| `Normalised demand` | Hourly shape, with a mean of 1 over the period |
| `Demand (MW)` | Hourly demand, if the capacity parameters are set |

The figure shows the hourly weekday and weekend shapes, and the first
two weeks of the profile.

## Running

From the `demandcast` folder:

```bash
uv run retrievals/electricity_demand_data_sources/ukpn_data_centres.py
uv run retrievals/electricity_demand_data_sources/phl_data_centre_demand.py
```

- The UKPN script saves into a folder named with the day of the run. The
  data is downloaded once per day: later runs on the same day read the
  saved Parquet file. Close the output CSV files (for example in Excel)
  before running it, or saving fails.
- The Philippine script only needs the UKPN results, not the API key. It
  uses the latest dated folder that contains `diurnal_profiles.csv`.

## Known limitations

- **The shape comes from the UK.** It assumes that data centres in the
  Philippines follow the same daily and weekly pattern of IT workload as
  in the UK area of UKPN.
- **No seasonality.** The Philippine profile only uses weekday and
  weekend shapes, so every week of the year is the same. In the UK,
  seasons change the co-located profile by at most a few percent.
- **Cooling is larger in the Philippines.** The UK shapes include UK
  cooling, which is small and uses outside air for much of the year.
  Cooling is a larger share of the load in a tropical climate and
  follows the daily temperature, so the real Philippine daily swing is
  likely slightly larger. A temperature-dependent PUE could be added
  (for example, with temperatures from
  [`temperature.py`](temperature.py)).
- **The UK fleet is colocation and enterprise sites.** New hyperscale or
  AI training sites may run at a higher and steadier utilisation, or
  with sharp swings from large training jobs.
- **The shape is an average of many sites.** It suits the total demand
  of many data centres, and is smoother than any single site.
- **Sites that grow or stop are included.** Some sites start importing,
  grow, or shut down during the record. Normalising by the whole-record
  mean makes their active periods look larger than their average. This
  mostly affects the monthly and seasonal profiles, much less the daily
  and weekly shapes.
- **The type is estimated by UKPN**, and the enterprise profiles are
  based on 14 sites only.
- **The holiday profiles rest on few days** (8–13 per group).
