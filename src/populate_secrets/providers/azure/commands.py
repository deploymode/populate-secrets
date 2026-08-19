#############################################################
# Manage Azure Pipelines variables and App Service settings
#
#############################################################

from subprocess import CalledProcessError

import click

from ...core.filters import filter_env_values
from ...core.loader import load_env_values
from ...core.sensitive import is_sensitive_name
from ...logging_config import logger
from . import az
from .validate import validate_env_input


def _load(env_file, json_file, include, exclude):
    if not env_file and not json_file:
        raise click.ClickException("Provide --env-file and/or --json-file")

    return filter_env_values(
        load_env_values(env_file=env_file, json_file=json_file),
        include=include,
        exclude=exclude,
    )


def _validated_items(env_values):
    for key, value in env_values.items():
        try:
            validate_env_input(key, value)
        except ValueError as e:
            logger.info(f"Skipping {key} - {e}")
            continue

        yield key, value


@click.group(name="azure-pipelines", help="Manage Azure Pipelines variables")
def azure_pipelines_group():
    pass


def _pipelines_args(action, pipeline_name, key, value):
    return [
        "pipelines", "variable", action,
        "--pipeline-name", pipeline_name,
        "--allow-override", "true",
        "--name", key,
        "--value", value,
        "--secret", "true" if is_sensitive_name(key) else "false",
    ]


@azure_pipelines_group.command(name="write", help="Populate Azure Pipelines variables")
@click.option(
    "--env-file",
    help="Path to .env file",
)
@click.option(
    "--json-file",
    help="Path to .json file containing an array of key/value objects",
)
@click.option(
    "--pipeline-name",
    required=True,
    help="Azure Pipelines name",
)
@click.option(
    "--include",
    help="Environment variables to include when writing. Excludes all others. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
@click.option(
    "--exclude",
    help="Environment variables to exclude when writing. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
def write_pipelines(env_file, json_file, pipeline_name, include, exclude):
    env_values = _load(env_file, json_file, include, exclude)

    az.ensure_devops_extension()

    for key, value in _validated_items(env_values):
        try:
            az.run_az(_pipelines_args("create", pipeline_name, key, value))
        except CalledProcessError:
            # The variable already exists — create is not idempotent.
            try:
                az.run_az(_pipelines_args("update", pipeline_name, key, value))
            except CalledProcessError:
                logger.info(f"Failed to write {key} to Azure Pipelines")
                continue

        logger.info(f"Wrote {key} to Azure Pipelines")

    logger.info("Done")


@click.group(name="azure-appservice", help="Manage Azure App Service settings")
def azure_appservice_group():
    pass


@azure_appservice_group.command(name="write", help="Populate Azure App Service app settings")
@click.option(
    "--env-file",
    help="Path to .env file",
)
@click.option(
    "--json-file",
    help="Path to .json file containing an array of key/value objects",
)
@click.option(
    "--app-name",
    required=True,
    help="Azure App Service app name",
)
@click.option(
    "--resource-group",
    required=True,
    help="Azure App Service resource group",
)
@click.option(
    "--include",
    help="Environment variables to include when writing. Excludes all others. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
@click.option(
    "--exclude",
    help="Environment variables to exclude when writing. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
def write_appservice(env_file, json_file, app_name, resource_group, include, exclude):
    env_values = _load(env_file, json_file, include, exclude)

    base_args = [
        "webapp", "config", "appsettings", "set",
        "--resource-group", resource_group,
        "--name", app_name,
        "--settings",
    ]

    for key, value in _validated_items(env_values):
        try:
            az.run_az(base_args + [f"{key}={value}"])
        except CalledProcessError:
            logger.info(f"Failed to write {key} to Azure App Service")
            continue

        logger.info(f"Wrote {key} to Azure App Service")

    logger.info("Done")
