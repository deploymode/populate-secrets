import json
import os

import click
from dotenv import dotenv_values

from ..logging_config import logger


def load_env_values(env_file=None, json_file=None):
    """Load variables from a .env file, a JSON file, or both.

    JSON values override .env values for the same key.
    """
    env_values = {}

    if env_file:
        if not os.path.exists(env_file):
            raise click.ClickException(f"Env file not found: {env_file}")
        logger.info(f"Loading env vars from {env_file}")
        env_values.update(dotenv_values(dotenv_path=env_file))

    if json_file:
        if not os.path.exists(json_file):
            raise click.ClickException(f"JSON file not found: {json_file}")
        logger.info(f"Loading env vars from {json_file}")
        env_values.update(load_env_values_from_json(json_file))

    return env_values


def load_env_values_from_json(json_file):
    """Read a JSON array of single-entry key/value objects into a dict."""
    with open(json_file) as f:
        json_data = json.load(f)

    return {key: entry[key] for entry in json_data for key in entry}
