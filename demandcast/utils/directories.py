# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions to read the folders structure
    and list yaml files in a specified folder.
"""

import os

import yaml


def read_folders_structure() -> dict[str, str]:
    """
    Read the folders structure.

    This function reads the folders structure from a yaml file located
    in the 'utils' directory. The yaml file should contain a dictionary
    where keys are folder names and values are their paths relative to
    the root folder. The root folder is determined as the parent
    directory of the current file's directory.

    Returns
    -------
    folders_structure : dict[str, str]
        A dictionary containing the folders structure, where keys are
        folder names and values are their paths.
    """
    # Get the absolute path to the root folder.
    root_folder = os.path.normpath(
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
    )

    # Define the default path to the yaml file.
    folders_structure_file_path = os.path.join(
        root_folder, "utils", "directories.yaml"
    )

    # Read the folders structure from the file.
    with open(folders_structure_file_path, "r") as file:
        folders_structure = yaml.safe_load(file)

    # Add the root folder to the folders structure.
    folders_structure["root_folder"] = root_folder

    # Iterate over the folders structure, concatenate the paths if
    # multiple folders are defined, and normalize the paths.
    for key, value in folders_structure.items():
        # Add the root folder to the path but skip the root folder key.
        if key != "root_folder":
            if isinstance(value, list):
                # If the value is a list, unpack the list.
                folders_structure[key] = os.path.join(root_folder, *value)
            else:
                folders_structure[key] = os.path.join(root_folder, value)

    return folders_structure


def list_yaml_files(folder: str) -> list[str]:
    """
    Get the paths of all yaml files in a specified folder.

    Parameters
    ----------
    folder : str
        The name of the folder from which to list the yaml files.

    Returns
    -------
    yaml_files : list[str]
        A list of paths to the yaml files in the specified folder.
    """
    # Get the path to specified folder.
    target_directory = read_folders_structure()[folder]

    # Get the path of all yaml files in the specified folder.
    yaml_file_paths = [
        os.path.join(target_directory, file)
        for file in os.listdir(target_directory)
        if file.endswith(".yaml")
    ]

    return yaml_file_paths
