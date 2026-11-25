<h1 align="center"><b>DemandCast</b></h1>

<h2 align="center"><b>Global hourly electricity demand forecasting</b></h2>

<p align="center">
    <a href="https://github.com/open-energy-transition/demandcast/actions/workflows/ci.yml"><img src="https://github.com/open-energy-transition/demandcast/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
    <a href="https://arxiv.org/abs/2510.08000"><img src="https://img.shields.io/badge/arXiv-2510.08000-b31b1b" alt="arXiv paper"></a>
    <a href="https://doi.org/10.5281/zenodo.18374351"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.18374351.svg" alt="Dataset DOI"></a>
    <a href="https://scorecard.dev/viewer/?uri=github.com/open-energy-transition/demandcast"><img src="https://api.scorecard.dev/projects/github.com/open-energy-transition/demandcast/badge" alt="OpenSSF Scorecard"></a>
    <a href="https://github.com/open-energy-transition/demandcast/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License: AGPL-3.0"></a>
</p>

<h3 align="center"><b>A project developed by</b></h3>

<p align="center">
    <a href="https://openenergytransition.org/">
        <img src="webpage/docs/figures/oet_logo.png" alt="OET Logo" width="256"/>
    </a>
</p>

<h3 align="center"><b>Supported by</b></h3>

<p align="center">
    <a href="https://www.breakthroughenergy.org/">
        <img src="webpage/docs/figures/be_logo.png" alt="Breakthrough Energy Logo" width="512"/>
    </a>
</p>

DemandCast collects hourly electricity demand, weather and socio-economic data from public sources, cleans and combines the electricity demand, and trains machine learning models that generate hourly time series of the gross electricity demand for future years, or for countries and subdivisions without data, to support energy planning studies.

<!-- status:start -->
As of 25 November 2026, DemandCast has retrieval modules for the hourly electricity demand of **46 countries and 194 subdivisions**, in 76 countries, from **47 data sources**, with about **2,175 years of data** in total since 1994, in the periods that the data sources cover, before the cleaning and the selection of the complete years for training.
<!-- status:end -->

![Countries and subdivisions for which retrieval modules of electricity demand data are available](webpage/docs/status/available_entities.png)

The trained model and the forecasted hourly electricity demand of 184 countries and 135 subdivisions from 2000 to 2025 are in this [Zenodo repository](https://doi.org/10.5281/zenodo.18374351).

## Documentation

The [documentation](https://open-energy-transition.github.io/demandcast/) describes DemandCast, its data sources and its [current state](https://open-energy-transition.github.io/demandcast/status/), and has the [getting started guide](https://open-energy-transition.github.io/demandcast/getting_started/) and the [architecture](https://open-energy-transition.github.io/demandcast/architecture/) of the code. To contribute, read the [contributing guidelines](CONTRIBUTING.md).

## Citation

If you use DemandCast in your work, please cite the [paper](https://arxiv.org/abs/2510.08000). [CITATION.cff](CITATION.cff), behind GitHub's "Cite this repository" button, gives the reference, and the [documentation](https://open-energy-transition.github.io/demandcast/#citation) its BibTeX.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
