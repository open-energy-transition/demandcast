<h1 align="center"><b>DemandCast</b></h1>

<h2 align="center"><b>Global hourly electricity demand forecasting</b></h2>

<h3 align="center"><b>A project developed by</b></h3>

<p align="center">
    <a href="https://openenergytransition.org/">
        <img src="figures/oet_logo.png" alt="OET Logo" width="256"/>
    </a>
</p>

<h3 align="center"><b>Supported by</b></h3>

<p align="center">
    <a href="https://www.breakthroughenergy.org/">
        <img src="figures/be_logo.png" alt="Breakthrough Energy Logo" width="512"/>
    </a>
</p>

## About

DemandCast is a Python-based project focused on collecting, processing, and forecasting hourly electricity demand data. The aim of this project is to support energy planning studies by using machine learning models to generate hourly time series of future electricity demand or for countries without available data.

DemandCast models the **gross electricity demand**: the electricity consumed, whatever generation supplies it, including the part that rooftop solar and other generation embedded in the distribution networks supply. Energy system models can then represent that generation explicitly, without counting it twice. Where a data source leaves it out, DemandCast adds an estimate of it when one is published, and flags the series otherwise (see [Data Retrieval](retrieval.md#gross-demand)).

### Features

- Retrieval of hourly and sub-hourly electricity demand data from public sources.
- Retrieval of weather and socio-economic data.
- Cleaning and quality flags of the electricity demand, and combination of the data sources of each country or subdivision into one hourly series.
- Training and validation of machine learning models.
- Forecasting using trained machine learning models.
- Modular design for adding new countries or data sources.
- Support for reproducible, containerized development.

#### Feature roadmap

The project is in active development and we are always looking for suggestions and contributions. Below is a non-exhaustive list of planned features:

- Add support to forecast electricity demand in user-defined subnational regions.
- Enhance model training by integrating new datasets:
    - New countries and subdivisions with available electricity demand data,
    - Sectoral electricity demand (agriculture, industry, transport, buildings),
    - Adoption of EVs, air conditioning, and heat pumps.
- Add and test new machine learning models for forecasting (e.g., [timesfm](https://github.com/google-research/timesfm)).
- Improve validation by considering simultaneity of peaks between actual and forecast electricity demand.
- Package the project for easier installation and usage.

## Documentation

The documentation is currently hosted on GitHub pages connected to this repository. It is built with [mkdocs](https://github.com/squidfunk/mkdocs-material).

To run it locally:

```bash
cd webpage
uv run mkdocs serve
```

Other online resources include:

- [Paper](https://arxiv.org/abs/2510.08000) accepted at the [NeurIPS 2025 Workshop](https://www.climatechange.ai/papers/neurips2025/42): Tackling Climate Change with Machine Learning.
- [Poster](https://s3.us-east-1.amazonaws.com/climate-change-ai/papers/neurips2025/42/poster.pdf) presented at the NeurIPS 2025 Workshop.
- [Video presentation](https://slideslive.com/39052515/demandcast-global-hourly-electricity-demand-forecasting) recorded for the NeurIPS 2025 Workshop.

## Contributing

We welcome contributions in the form of:

- Country-specific data retrieval modules
- New or improved forecasting models
- Documentation and testing enhancements

Please read the [contributing guidelines](https://github.com/open-energy-transition/demandcast/blob/main/CONTRIBUTING.md) before opening a pull request, and follow our [Code of Conduct](https://github.com/open-energy-transition/demandcast/blob/main/CODE_OF_CONDUCT.md). Issues labelled [good first issue](https://github.com/open-energy-transition/demandcast/labels/good%20first%20issue) are a good place to start.

We also would like to hear your feedback and suggestions. You can share your thoughts by completing this short [survey](https://forms.gle/nMYvCAfzbrUDjqRQ8).

## How DemandCast works

![DemandCast](figures/demandcast_illustration.png)

The [architecture](architecture.md) page describes the scripts, the folders of the code and of the data, and how the modules depend on each other.

## Data sources

The table below provides an overview of the data sources currently used in DemandCast for hourly and sub-hourly electricity demand, weather, and socio-economic data for both historical and future periods.

|Data type|Data sources for the historical period|Data sources for the future period|
|---|---|---|
|Hourly and sub-hourly<br>electricity demand|Various public sources listed in the<br>[Awesome Electricity Demand repository](https://github.com/open-energy-transition/Awesome-Electricity-Demand)| -- |
|Temperature|[ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)|[CMIP6](https://cds.climate.copernicus.eu/datasets/projections-cmip6)|
|Gridded population|[SEDAC GPW v4](https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/browseui/#sedac-popdensity-yeargrid5yr-v4.11/)|[Wang X. et al. (2022)](https://doi.org/10.6084/m9.figshare.19608594)|
|National population|[World Bank](https://data.worldbank.org/indicator/SP.POP.TOTL)|[IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp)|
|Gridded GDP, PPP|[Wang T. et al. (2022)](https://zenodo.org/records/7898409)|[Wang T. et al. (2022)](https://zenodo.org/records/7898409)|
|National GDP per capita, PPP|[World Bank](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD), [IMF](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)&INDICATOR=NGDPRPPPPC)|[IIASA SSP Database](https://data.ece.iiasa.ac.at/ssp)|
|National annual electricity<br>demand per capita|[Ember](https://ember-energy.org/data/yearly-electricity-data/), completed by the [World Bank](https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC) scaled to Ember|[IIASA SSP Database](https://tntcat.iiasa.ac.at/SspDb)|

The map below shows the countries and subdivisions for which retrieval modules of electricity demand data are currently available in DemandCast. The [current state](status.md) page gives their numbers, shows them by GDP and electricity demand per capita, and shows the forecast errors of the models.

![Countries and subdivisions for which retrieval modules of electricity demand data are available](status/available_entities_light_mode.png#only-light)
![Countries and subdivisions for which retrieval modules of electricity demand data are available](status/available_entities_dark_mode.png#only-dark)

You can find the code that we used to retrieve the data in their respective files inside the [demandcast/retrievals](https://github.com/open-energy-transition/demandcast/tree/main/demandcast/retrievals) folder.

The retrieved data is not redistributed, since the licences of many data sources do not allow it: DemandCast retrieves it from the sources, and the people who work on it share their data folders through a private bucket (see [sharing and publishing](publishing.md)). The trained model and its forecasts are published on Zenodo (see below).

## Dataset of global forecasts

Forecasted hourly electricity demand for 184 countries from 2000 to 2024 is available in this [Zenodo repository](https://doi.org/10.5281/zenodo.18374351).

Forecasts for future years, including different climate models and scenarios, will be included in a future release. However, DemandCast is already capable of generating these forecasts for users who wish to produce them independently.

## Getting started

The [getting started guide](getting_started.md) installs DemandCast and goes from the retrieval of the data to a forecast. To change the code, add a data source or a model, see the [contributing guidelines](https://github.com/open-energy-transition/demandcast/blob/main/CONTRIBUTING.md).

## Citation

If you use DemandCast in your work, please cite the [paper](https://arxiv.org/abs/2510.08000). GitHub's "Cite this repository" button, generated from [CITATION.cff](https://github.com/open-energy-transition/demandcast/blob/main/CITATION.cff), provides the reference in other formats.

```bibtex
@inproceedings{steijn2025demandcast,
  title     = {DemandCast: Global hourly electricity demand forecasting},
  author    = {Steijn, Kevin and Goli, Vamsi Priya and Antonini, Enrico},
  booktitle = {NeurIPS 2025 Workshop: Tackling Climate Change with Machine Learning},
  year      = {2025},
  doi       = {10.48550/arXiv.2510.08000},
  url       = {https://arxiv.org/abs/2510.08000}
}
```

## Maintainers

The project is maintained by the [Open Energy Transition](https://openenergytransition.org/) team. The team members currently involved in this project are:

- [Enrico Antonini](https://github.com/eantonini) (enrico.antonini at openenergytransition dot org)
- [Vamsi Priya Goli](https://github.com/Vamsipriya22) (goli.vamsi at openenergytransition dot org)

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
