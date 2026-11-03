# DemandCast release

This record has the forecasted hourly electricity demand of DemandCast, the machine learning models that forecast it and that were validated, and the inputs of the forecasts. The code is in the GitHub repository [open-energy-transition/demandcast](https://github.com/open-energy-transition/demandcast), and its documentation at [open-energy-transition.github.io/demandcast](https://open-energy-transition.github.io/demandcast/).

Each file has a manifest, `<file>.manifest.json`, with its checksum, the version of the code that made it, its settings and the files that it comes from.

## Files

- `xgboost_model_<time>.json`: the model that gives the forecasts, trained on all the years of the training data. Its manifest lists the countries, subdivisions and local years of the training.
- `all_<time>.parquet` of the forecasts: the forecasted hourly electricity demand in MW of each country and subdivision, by the end of each hour in UTC, with the inputs of the model.
- `forecasts_on_historical_period.parquet`: the same forecasts with three columns: the time, by the end of each hour in UTC, the code of the country or subdivision and the forecasted demand in MW. It has the name and the columns of the file of the first release.
- `assembled_data_for_forecasting_<time>.parquet`: the inputs of the forecasts, by hour: the local calendar and public holidays, the temperature, the GDP PPP per capita, the annual electricity demand per capita and the population.
- The validation: the model trained without the most recent year of each country and subdivision, `xgboost_model_<time>.json`, its error on that year for each country and subdivision, `all_<time>.parquet` and `.csv`, and their summary by group, `summary_<time>.csv`.
- The cross-validation: the error of each country and subdivision, held out of the training in turn, `all_<time>.parquet` and `.csv`, their summary, `summary_<time>.csv`, and the model of each fold, named after the country or subdivision that it holds out, in `models_<time>.zip`.

The hourly electricity demand of the data sources is not in the record, since the licences of many of them do not allow its redistribution.

## Replication

To forecast again, install DemandCast at the version in the manifests and run `forecast.py` with the model and the assembled data for forecasting of this record:

```yaml
model_path: <path to xgboost_model_<time>.json>
data_path: <path to assembled_data_for_forecasting_<time>.parquet>
```

The errors of the validation and of the cross-validation need the hourly electricity demand, which DemandCast retrieves from the data sources: some need an API key or a free account, and some files are downloaded by hand (see the [data retrieval](https://open-energy-transition.github.io/demandcast/retrieval/) page). With the retrieved data, `assemble.py`, `validate.py` and `cross_validate.py`, with the settings in the manifests, give the errors again, and the models of this record can be scored on the same data. The manifests have the checksum of the assembled data of the training, which tells whether the retrieved data is the same: the data sources revise their data, so it can differ.

## Sources and licences

The model and the forecasts are licensed under CC BY 4.0. Their inputs come from these sources, under their own terms:

| Input | Source | Licence |
|---|---|---|
| Temperature | ERA5 hourly data on single levels (Hersbach et al., 2023, [doi:10.24381/cds.adbb2d47](https://doi.org/10.24381/cds.adbb2d47)), at the most populous cells of each country and subdivision | Licence to use Copernicus Products |
| Population | World Bank, [SP.POP.TOTL](https://data.worldbank.org/indicator/SP.POP.TOTL); the share of a subdivision from the Gridded Population of the World v4.11 (CIESIN, 2018, [doi:10.7927/H49C6VHW](https://doi.org/10.7927/H49C6VHW)) | CC BY 4.0 |
| GDP PPP per capita | World Bank, [NY.GDP.PCAP.PP.KD](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD); International Monetary Fund, World Economic Outlook database; the GDP of a subdivision from the gridded GDP of Wang and Sun (2022, [Zenodo 7898409](https://zenodo.org/records/7898409)) | CC BY 4.0; IMF terms of use; CC BY 4.0 |
| Annual electricity demand per capita | Ember, [Yearly Electricity Data](https://ember-energy.org/data/yearly-electricity-data/); World Bank, [EG.USE.ELEC.KH.PC](https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC), from the IEA, where Ember has no data | CC BY 4.0 |
| Public holidays | [holidays](https://github.com/vacanza/holidays) Python package | MIT |

Attributions:

- Contains modified Copernicus Climate Change Service information. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.
- Source: International Monetary Fund, World Economic Outlook database, [imf.org/en/Publications/WEO](https://www.imf.org/en/Publications/WEO). The values are transformed: completed with those of the World Bank and allocated to subdivisions. Their commercial reuse needs the permission of the IMF ([copyright@imf.org](mailto:copyright@imf.org)), under its [terms](https://www.imf.org/en/about/copyright-and-terms).
- Ember, Yearly Electricity Data; World Bank, World Development Indicators; CIESIN, Gridded Population of the World v4.11; Wang and Sun (2022), gridded GDP.
