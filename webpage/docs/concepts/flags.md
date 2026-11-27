# Quality flags and reviews

The cleaning flags periods of the electricity demand that look wrong but that no automatic rule can safely fix. This page explains each flag, and how a review decides what happens to the flagged hours. Read [Electricity demand data](electricity-demand.md) first.

## What a flag is

A [flag](glossary.md#flag) marks a period that needs a human review; it never removes a value. Flags are saved in `cleaned/<code>_<data source>_flags.parquet`, and those of the combined series in `combined/<code>_flags.parquet`. The log warns once per flag name, with its periods and the path of the file. All flags work on local days (the local day of the start of each hour), and a review applies to the hours of those days.

| Flag | What it catches | Rule | Period |
|---|---|---|---|
| `midday_dip` | Demand that leaves out growing rooftop solar | The quarter's midday index falls more than 0.05 below the median of the same quarter in all earlier years, and the change lasts | Quarter, `JJA 2022` |
| `midday_rise` | A change of what a series counts, such as an operator starting to add embedded generation (EPIAS from 2020-12-30, ONS from 2023-04-29) or battery charging | The index rises more than 0.05 above the median of earlier years and more than 0.05 above the previous year with data, and the change lasts | Quarter |
| `time_lag` | Times read in the wrong time zone or at the wrong end of the intervals, or values that slip against their times | The quarter's daily profile must move by 1–3 whole hours to match the median profile of the same quarter, and the move leaves less than 40% of the squared difference | Quarter |
| `daylight_saving` | Wrong daylight saving time around a change of the clocks | The profile of the 14 days after the change must move by whole hours to match the 14 days before (see below) | Local day of the change, `2021-03-28` |
| `annual_total` | Unit errors, a series covering only part of a country, or the wrong country (countries only) | The annual demand is below 0.75 or above 1.33 times the annual demand per capita × population | Year, `2021` |
| `annual_change` | A change of what the series covers, or of its definition | Both the annual demand and its ratio to the annual demand per capita × population change by more than 10% from the year before (20% for a subdivision) | Year |
| `low_value` | Blackouts, source errors, or net demand that solar nearly covers at midday | An hour below 10% of the median demand of its local year | Local day, `2016-09-28` |

The quarters are `DJF` (December to February), `MAM`, `JJA` and `SON`. December belongs to the next year: `DJF 2022` runs from 2021-12-01 to 2022-02-28.

## Midday dip and midday rise

The midday index of a day compares midday with the morning and the afternoon, in [solar time](glossary.md#solar-time). Solar time is UTC plus the longitude of a point inside the entity's shape divided by 15 degrees per hour.

1. Take the mean demand of the three hours whose middles fall between 10:30 and 13:30 solar time.
2. Divide it by the average of the mean of 7:00–9:00 and the mean of 15:00–17:00. A day without all seven hours has no index.
3. Take the median over the days of each quarter. A quarter needs at least 60 days with an index.
4. Compare it with the median of the same quarter in all earlier years. The first year of a quarter is never flagged.

A system without solar keeps its index within about 0.02 from year to year; the summer index of Great Britain without embedded solar drops from about 1.02 in 2011 to 0.87 in 2026. Using the median of earlier years, not their maximum, stops one unusual year, such as a drought, from flagging all later years.

A rise must also exceed the previous year with data by 0.05, because a change of definition is sudden, while the midday demand of some Indian states rises slowly as farm supply moves to the day.

A dip or rise is kept only if it lasts: the season before or after it, or the same season a year before or after, has the same flag, or it is in the last year with data for its quarter. A single season is noisy in small systems and moves with single events, such as the lockdowns.

The flag does not prove that solar is missing: the index also moves when midday demand itself changes. It cannot see solar that was already there when the series starts, as in California.

## Time lag

Demand follows the clocks, so its daily profile in local time stays at the same hours from year to year.

1. For each quarter with at least 60 days and a value at every hour of the day, compute the profile: the mean demand of each local hour divided by the mean of the 24 hours.
2. If the same quarter has profiles in at least 3 years, take their median profile (all years, this one included).
3. Try moves of the profile from −3 to +3 hours, and keep the one with the smallest squared difference to the median profile.
4. Flag the quarter if that move is not zero and leaves less than 40% of the squared difference without a move.

Real errors leave 5% to 31%; a change of shape, such as a growing midday dip, leaves about half.

## Daylight saving

For each change of the clocks within the data:

1. Take the 14 days before the change and the 14 days after it, skipping the first 24 hours after the change. Each side needs at least 12 days of hours and a value at every local hour.
2. Compute both profiles with the median of each hour, so that a few holidays, such as the carnival in Brazil, do not shift them.
3. Find the whole-hour move (as for the time lag) and the move in steps of 0.1 hours that best match the profile after to the profile before.
4. If the whole-hour move is zero, there is no flag.
5. If the profile moves with the clocks (later after they go forward, earlier after they go back), flag it. Real demand cannot do this, so the times are wrong, as in the winters of Northern Ireland on ENTSO-E.
6. If it moves against the clocks, flag it only if the 0.1-hour move differs by 0.75 hours or more from the usual move. The usual move is the median of the same changes (forward or back) in the other years if there are at least 2, and zero otherwise.

Step 6 exists because some demand follows the sun more than the clocks (hot regions of Mexico, north-east Brazil, South Australia with its rooftop solar): its profile moves against each change by about the same fraction of an hour every year. A sudden change of weather can still shift a heating profile, as in New Brunswick on 2026-03-08. The flag covers the 14 days before to the 14 days after the local day of the change.

## Annual total and annual change

These flags need the [annual electricity demand per capita and the population](inputs.md#annual-electricity-demand-per-capita) of the code, so retrieve them before the electricity demand. If either file is missing, both flags are skipped and an info message in the log says so.

1. Group the hours by local year. A year needs at least 90% of its hours.
2. The annual demand is the mean demand times the hours of the year, in TWh.
3. The expected demand is the annual demand per capita (kWh) times the population, in TWh. A subdivision uses the demand per capita of its country.
4. The ratio is the annual demand divided by the expected demand.

Measured demand differs from the statistics: it leaves out consumers outside the operators' networks, and may count or leave out losses and power plant use. For countries the ratio is between 0.87 and 1.08, hence the `annual_total` limits of 0.75 and 1.33. A subdivision's ratio can be anywhere from 0.2 to 3, so only `annual_change` applies to it.

The ratio of a country changes by at most about 7% a year. `annual_change` also requires the demand itself to change, which avoids flags when a source of the demand per capita misses a year. Small subdivisions change more with national shocks, hence their 20% threshold.

## Low value

The demand of a whole country or subdivision rarely falls below a tenth of its usual level; North Macedonia in 2025 falls to 0.005 MW at midday against a median of 590 MW. The cleaning removes only values of zero or less, so these days stay until a review decides.

## Flag files

| Column | Meaning |
|---|---|
| `start`, `end` | First and last local day of the flagged period |
| `flag` | The flag name |
| `period` | The name of the period: a quarter (`JJA 2022`), a year (`2021`) or a day (`2021-03-28`) |
| `value` | Midday flags: the quarter's midday index. `time_lag` and `daylight_saving`: hours by which the profile must move later. `annual_total`: the annual demand in TWh. `annual_change`: the ratio of the year. `low_value`: the lowest share of the year's median. |
| `reference` | Midday flags: the median of earlier years. `time_lag`: 0. `daylight_saving`: the usual move in hours. `annual_total`: the expected demand in TWh. `annual_change`: the ratio of the year before. `low_value`: 0.1. |

## Reviews of flags

A [review](glossary.md#review) records a person's [verdict](glossary.md#verdict) on a flag. Reviews live in `demandcast/checks/reviewed_flags.yaml`, which comes with the code, and decide which hours the combination uses and which can train the models.

```yaml
reviews:
  - data_source: aemo_nem
    code: AUS_SA1
    flag: low_value
    periods:
      - "2016-09-28"
    verdict: real_event
    note: The blackout of South Australia of 28 September 2016.
```

| Field | Required? | What it does |
|---|---|---|
| `data_source` | Yes | The data source of the flag, or `combined` for a flag of the combined series |
| `code` | Yes | The code of the country or subdivision |
| `flag` | Yes | The flag name, such as `midday_dip` |
| `periods` | No | The `period` values it covers, as quoted strings. Without it, the review covers every period of that flag. |
| `verdict` | Yes | One of the verdicts below |
| `note` | Yes | The evidence, in words |

A misspelled field is an error, so a review of some periods never silently becomes a review of all of them. Quote the periods: an unquoted `2020` or `2016-09-28` is read as a number or a date, which is an error. If several reviews match a flag, the first one in the file applies.

| Verdict | Meaning | Effect on the combined series |
|---|---|---|
| `source_error` | The data of the source is wrong. | The hours of the flagged days leave their source. They fill only hours that no other source gives, and are never eligible for training (`reviewed error`). |
| `reading_error` | DemandCast reads the source's data wrongly. | Same as `source_error`. |
| `net_demand` | The data leaves out the demand supplied by embedded generation. | The hours stay in their source, but rank as net demand and are not eligible for training (`net demand`). |
| `definition_change` | What the source's data covers changes. | None: the review documents the flag. |
| `real_event` | The demand itself changes, such as a blackout or a lockdown. | None: the hours stay eligible. |
| `false_positive` | The flag comes from its rule, not from the data. | None. |

A review applies to the hours whose local start day is between the flag's `start` and `end`. A review whose period no longer appears in the flags has no effect.

## Flags of the combined series

Combined flags have the data source `combined`. Their main source is the source of most hours of the flagged period. A combined flag takes:

1. the review with `data_source: combined` for that code, flag and period, if there is one;
2. otherwise, if the main source has the same flag in the same period, that source's review, whose effect already applies to its hours. So a flag that comes from the data of a source is reviewed once.

A flag that the main source does not have comes from the combination itself, such as a step where one source takes over from another, and needs its own review with `data_source: combined`. Such a review only changes eligibility (`reviewed error` or `net demand`); no other source replaces the hours.

## How to review flags

1. Retrieve the electricity demand; the log warns about each flag.
2. Run the report of the flags and open `data/results/checks/flags_report.md` (see the [check guide](../guides/check.md#report-of-the-flags)):

    ```bash
    uv run check.py --config config/check_flags_config.yaml
    ```

3. For each flag that is not reviewed, compare the demand with the `definition` of its source, and add a review to `checks/reviewed_flags.yaml`.
4. Run `assemble.py`, which combines the series again (see [When the combination runs again](electricity-demand.md#when-the-combination-runs-again)). You do not need to download again.
