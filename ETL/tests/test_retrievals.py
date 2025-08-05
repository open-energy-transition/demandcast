# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests to verify that the retrievals modules
    in the ETL utility package have all essential functions implemented.
"""

import importlib

import pytest
import utils.entities


def test_retrievals_functions():
    """
    Test if all retrievals functions are implemented.

    This test checks if the retrievals module has all the essential
    functions implemented.
    """
    # Define the list of essential functions that should be implemented
    # in each retrievals module.
    essential_functions = [
        "redistribute",
        "get_available_requests",
        "get_url",
        "download_and_extract_data",
    ]

    # Get the list of data sources.
    data_sources = utils.entities.read_data_sources()

    # Iterate through each data source.
    for data_source in data_sources:
        # Get the module name for the data source.
        module_name = f"retrievals.{data_source}"

        # Import the module.
        module = importlib.import_module(module_name)

        # Get the list of functions in the module.
        functions_in_module = [
            f
            for f in dir(module)
            if callable(getattr(module, f)) and not f.startswith("__")
        ]

        # Check if all essential functions are implemented.
        for essential_function in essential_functions:
            for function_in_module in functions_in_module:
                if essential_function in function_in_module:
                    break
            else:
                pytest.fail(
                    f"Function '{essential_function}' is not implemented in "
                    f"module '{module_name}'."
                )
