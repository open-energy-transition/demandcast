# Quality flags and reviews

The cleaning of the electricity demand flags periods that look wrong but that no automatic rule can safely fix. This page explains each flag, and how you review flags so that DemandCast knows what to do with the flagged hours. Read [Electricity demand data](electricity-demand.md) first.

## What a flag is

A [flag](glossary.md#flag) marks a period of the cleaned demand that needs a human review. Flags never remove a value. The cleaning saves them in `<code>_<data source>_flags.parquet` next to the cleaned data. The combination flags the combined series in the same way, in `combined/<code>_flags.parquet`.

All the flags work on local days: the local day of the start of each hour. So a review of a flag applies to the hours of its local days.

| Flag | What it catches | Detection and thresholds | Period |
|---|---|---|---|
| `midday_dip` | Demand that leaves out growing rooftop solar | The quarterly midday index falls more than 0.05 below the median of the same quarter in all earlier years, and the change lasts | Quarter, `JJA 2022` |
| `midday_rise` | A change of what a series counts, such as when an operator starts adding embedded generation (EPIAS from 2020-12-30, ONS from 2023-04-29) or battery charging | The index rises more than 0.05 above the median of earlier years and more than 0.05 above the previous year with data, and the change lasts | Quarter |
| `time_lag` | Times read in the wrong time zone, at the wrong end of the intervals, or values that slip against their times | The quarter's daily profile must move by 1–3 whole hours to match the median profile of the same quarter, and the move leaves less than 40% of the squared difference | Quarter |
| `daylight_saving` | Wrong daylight saving time around a change of the clocks | The profile of the 14 days after the change must move by whole hours to match the 14 days before; see below | Local day of the change, `2021-03-28` |
| `annual_total` | Unit errors, a series that covers only part of a country, or the wrong country (countries only) | The annual demand is below 0.75 or above 1.33 times the annual demand per capita × population | Year, `2021` |
| `annual_change` | A change of what the series covers, or of its definition | Both the annual demand and its ratio to the annual demand per capita × population change by more than 10% from the year before (20% for a subdivision) | Year |
| `low_value` | Blackouts, errors of the source, or net demand that solar nearly covers at midday | An hour below 10% of the median demand of its local year | Local day, `2016-09-28` |

The quarters are December to February (`DJF`), March to May (`MAM`), June to August (`JJA`) and September to November (`SON`). December belongs to the next year: `DJF 2022` runs from 2021-12-01 to 2022-02-28.

## Midday dip and midday rise

The midday index of a day compares midday with the morning and the afternoon, in [solar time](glossary.md#solar-time). Solar time is UTC plus the longitude of a point inside the entity's shape divided by 15 degrees per hour.

1. Take the mean demand of the three hours whose middles fall between 10:30 and 13:30 solar time.
2. Divide it by the average of the mean of the two hours from 7:00 to 9:00 and the mean of the two hours from 15:00 to 17:00. A day without all seven hours has no index.
3. Take the median over the days of each quarter. A quarter needs at least 60 days with an index.
4. Compare it with the median of the same quarter in all earlier years. The first year of a quarter is never flagged.

A system without solar keeps its index within about 0.02 from year to year. The national demand of Great Britain without embedded solar drops from about 1.02 in 2011 to 0.87 in 2026 in summer. Using the median of earlier years, not their highest value, keeps one unusual year, such as a drought, from flagging all the years after it.

A rise must also be more than 0.05 above the previous year with data, because a change of definition is sudden. The midday demand of some Indian states rises slowly as their agricultural supply moves to the day, which should not be flagged.

A dip or rise is kept only if it lasts: the season before or after it, or the same season of the year before or after it, has the same flag, or it is in the last year with data for its quarter. A single season is noisy in small systems and moves with single events, such as the lockdowns, while embedded generation lasts.

The flag does not prove that solar is missing. The index also changes when the demand itself changes at midday. It cannot see solar that was already there when the series starts, as in California.

## Time lag

Demand follows the clocks, so its daily profile in local time stays at the same hours from year to year.

1. For each quarter with at least 60 days and a value at every hour of the day, compute the profile: the mean demand of each local hour, divided by the mean of the 24 hours.
2. If the same quarter has profiles in at least 3 years, take their median profile (all years, including this one).
3. Try moves of the profile from −3 to +3 hours. Keep the move with the smallest squared difference to the median profile.
4. Flag the quarter if that move is not zero and leaves less than 40% of the squared difference without a move.

Real errors leave 5% to 31%. A change of shape, such as a growing midday dip, leaves about half. The `value` of the flag is the number of hours by which the profile has to move later.

## Daylight saving

For each change of the clocks within the data:

1. Take the 14 days before the change, and the 14 days after it, skipping the first 24 hours after the change. Each side needs at least 12 days of hours and a value at every local hour.
2. Compute both profiles with the median of each hour, so that a few holidays, such as the carnival in Brazil, do not shift them.
3. Find the whole-hour move (as for the time lag) and the move in steps of 0.1 hours that best match the profile after to the profile before.
4. If the whole-hour move is zero, there is no flag.
5. If the profile moves with the clocks (it has to move later after the clocks go forward, or earlier after they go back), flag it. Real demand cannot do this, so the times of that part of the year are wrong, as in the winters of Northern Ireland on ENTSO-E.
6. If it moves against the clocks, flag it only if the 0.1-hour move differs by 0.75 hours or more from the usual move: the median move of the same changes (forward or back) in the other years, if there are at least 2, and zero otherwise.

Step 6 exists because some demand follows the sun more than the clocks, such as in the hot regions of Mexico, the north-east of Brazil, or South Australia with its rooftop solar. Its profile moves against each change by about the same part of an hour every year. A sudden change of weather right after a change of the clocks can still shift a heating profile, as in New Brunswick on 2026-03-08.

The flag covers the 14 days before to the 14 days after the local day of the change. Its `reference` is the usual move.

## Annual total and annual change

These flags need the [annual electricity demand per capita and the population](inputs.md) of the code. Retrieve them before the electricity demand. If either is missing, the annual flags are skipped, and the log says so.

1. Group the hours by local year. A year needs at least 90% of its hours.
2. The annual demand is the mean demand times the hours of the year, in TWh.
3. The expected demand is the annual demand per capita (kWh) times the population, in TWh. A subdivision uses the demand per capita of its country.
4. The ratio is the annual demand divided by the expected demand.

The demand that system operators measure differs from the statistics. It leaves out consumers outside their networks and can count or leave out losses and the use of power plants. For countries, the ratio is between 0.87 and 1.08. So `annual_total` (countries only) flags a ratio below 0.75 or above 1.33.

A subdivision's ratio can be from 0.2 to 3, so only `annual_change` applies to it. The ratio of a country changes by at most about 7% from one year to the next, since the demand per capita and the population follow the growth of the demand. `annual_change` flags a year when both the ratio and the demand change by more than 10% from the year before (20% for a subdivision). Requiring the demand to change too avoids flags when a source of the demand per capita is missing for a year. Small subdivisions change more with national shocks, hence their higher threshold.

## Low value

The demand of a whole country or subdivision rarely falls below a tenth of its usual level. A day is flagged if one of its hours is below 10% of the median demand of its local year. North Macedonia in 2025, for example, falls to 0.005 MW at midday against a median of 590 MW. The cleaning removes only values of zero or less, so these days stay in the data until a review decides.

## Flag files

| Column | Meaning |
|---|---|
| `start` | First local day of the flagged period |
| `end` | Last local day of the flagged period |
| `flag` | The flag name |
| `period` | The name of the period: a quarter (`JJA 2022`), a year (`2021`) or a day (`2021-03-28`) |
| `value` | Midday flags: the quarter's midday index. `time_lag` and `daylight_saving`: hours to move later. `annual_total`: the annual demand in TWh. `annual_change`: the ratio of the year. `low_value`: the lowest share of the year's median. |
| `reference` | Midday flags: the median of earlier years. `time_lag`: 0. `daylight_saving`: the usual move in hours. `annual_total`: the expected demand in TWh. `annual_change`: the ratio of the year before. `low_value`: 0.1. |

## Reviews of flags

A [review](glossary.md#review) records a person's [verdict](glossary.md#verdict) on a flag. The reviews are in `demandcast/checks/reviewed_flags.yaml`, which comes with the code. They decide which hours the combination uses and which hours can train the models.

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
| `data_source` | Yes | The data source of the flag, or `combined` for a flag of the combined series. |
| `code` | Yes | The code of the country or subdivision. |
| `flag` | Yes | The flag name, such as `midday_dip`. |
| `periods` | No | The `period` values that the review covers, as quoted strings. Without it, the review covers every period of that flag. |
| `verdict` | Yes | One of the verdicts below. |
| `note` | Yes | The evidence, in words. |

A misspelled field is an error, so a review of some periods never silently becomes a review of all of them. Quote the periods: `"2020"`, not `2020`. If several reviews match a flag, the first one in the file applies.

| Verdict | Meaning | Effect on the combined series |
|---|---|---|
| `source_error` | The data of the source is wrong. | The hours of the flagged days leave their source. They fill only hours that no other source gives, and are never eligible for training (`reviewed error`). |
| `reading_error` | DemandCast reads the data of the source wrongly. | Same as `source_error`. |
| `net_demand` | The data leaves out the demand that embedded generation supplies. | The hours stay in their source, but count as net demand in the ranking, and are not eligible for training (`net demand`). |
| `definition_change` | What the data of the source covers changes. | None: the review documents the flag. |
| `real_event` | The demand itself changes, such as a blackout or a lockdown. | None: the hours stay eligible. |
| `false_positive` | The flag comes from its rule, not from the data. | None. |

A review applies to the hours whose local start day is between the `start` and `end` of the flag. A review whose period no longer appears in the flags has no effect.

## Flags of the combined series

The flags of a combined series have the data source `combined`. Most of them come from the data of one source. The main source of a combined flag is the data source of most hours of the flagged period. If the main source has the same flag in the same period, the report of the flags shows the main source's review for it, whose effect already applies to that source's hours. So a flag that comes from the data of a source is reviewed once.

A flag that the main source does not have comes from the combination itself, such as a step where one source fills the hours after another. It needs its own review with `data_source: combined`. Such a review only changes eligibility: an error verdict makes the hours `reviewed error`, and `net_demand` makes them `net demand`. No other source replaces them.

## How to review flags

1. Retrieve the data. The log warns about each new flag and gives the path of the flag file.
2. Run the report of the flags (see the [check guide](../guides/check.md)):

    ```bash
    uv run check.py --config config/check_flags_config.yaml
    ```

3. Open `data/results/checks/flags_report.md` (or `.csv`). It lists the flags not reviewed, the reviewed flags with their verdicts, and the reviews or periods that match no flag, such as fixed errors or misspelled periods.
4. Look at each flag that is not reviewed, compare it with the `definition` of its source, and add a review to `checks/reviewed_flags.yaml`.
5. Run `assemble.py`, which combines the series again (see [When the combination runs again](electricity-demand.md#when-the-combination-runs-again)). You do not need to download again.
