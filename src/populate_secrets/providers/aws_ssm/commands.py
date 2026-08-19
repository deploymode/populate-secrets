#############################################################
# Manage AWS SSM Parameter Store secrets
#
#############################################################

import botocore
import click

from ...core.filters import filter_env_values
from ...core.loader import load_env_values
from ...logging_config import logger
from .client import aws_session, ssm_client

HTTP_OK = 200


@click.group(name="aws-ssm", help="Manage AWS SSM Parameter Store parameters")
def aws_ssm_group():
    pass


def _require_credentials():
    session = aws_session()
    if session.get_credentials() is None:
        raise click.ClickException(
            "AWS credentials not found. Set them in the environment or configure a profile."
        )

    return session


def _load(env_file, json_file, include, exclude):
    if not env_file and not json_file:
        raise click.ClickException("Provide --env-file and/or --json-file")

    return filter_env_values(
        load_env_values(env_file=env_file, json_file=json_file),
        include=include,
        exclude=exclude,
    )


def _normalise_prefix(prefix):
    if prefix.endswith("/"):
        logger.info("Removing trailing slash from parameter store prefix")

    return prefix.rstrip("/")


def read_parameters(client, prefix):
    """Read the parameters written directly under a prefix, keyed by name.

    Not recursive: `write` only creates direct children, so anything deeper
    belongs to a different prefix and would collide on the bare key.
    """
    paginator = client.get_paginator("get_parameters_by_path")
    values = {}

    try:
        for page in paginator.paginate(Path=prefix, Recursive=False, WithDecryption=True):
            for parameter in page["Parameters"]:
                values[parameter["Name"].rsplit("/", 1)[-1]] = parameter["Value"]
    except botocore.exceptions.ClientError as e:
        raise click.ClickException(f"Failed to read parameters under {prefix}: {e}")

    return values


def _drop_existing(client, prefix, env_values):
    remote_values = read_parameters(client, prefix)

    for key in env_values:
        if key in remote_values:
            logger.info(f"Skipping {key} - already in parameter store")

    return {k: v for k, v in env_values.items() if k not in remote_values}


def compare_values(local_values, remote_values):
    return {
        "new": {k: v for k, v in local_values.items() if k not in remote_values},
        "changed": {
            k: v for k, v in local_values.items()
            if k in remote_values and remote_values[k] != v
        },
        "unchanged": {
            k: v for k, v in local_values.items()
            if k in remote_values and remote_values[k] == v
        },
        "remote_only": {k: v for k, v in remote_values.items() if k not in local_values},
    }


@aws_ssm_group.command(help="Populate parameter store from .env and/or JSON file")
@click.option(
    "--env-file",
    help="Path to .env file",
)
@click.option(
    "--json-file",
    help="Path to .json file containing an array of key/value objects",
)
@click.option(
    "--prefix",
    required=True,
    help="Path prefix for parameter store, e.g. /my-app/uat",
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
@click.option(
    "--skip-existing",
    is_flag=True,
    default=False,
    help="Only write variables that are not already in parameter store",
)
def write(env_file, json_file, prefix, include, exclude, skip_existing):
    session = _require_credentials()

    env_values = _load(env_file, json_file, include, exclude)

    if not env_values:
        logger.info("Nothing to write")
        return

    prefix = _normalise_prefix(prefix)

    client = ssm_client()

    if skip_existing:
        env_values = _drop_existing(client, prefix, env_values)

        if not env_values:
            logger.info("Nothing to write")
            return

    logger.info(f"Writing to region {session.region_name}")

    for key, value in env_values.items():
        if not value:
            logger.info(f"Skipping {key} due to empty value")
            continue

        param_path = f"{prefix}/{key}"

        try:
            response = client.put_parameter(
                Name=param_path, Value=value, Type="SecureString", Overwrite=True
            )
        except botocore.exceptions.ClientError as e:
            raise click.ClickException(f"Failed to write {param_path}: {e}")

        if response["ResponseMetadata"]["HTTPStatusCode"] == HTTP_OK:
            logger.info(f"Wrote {param_path}")
        else:
            logger.info(f"Failed to write {param_path}")

    logger.info("Done")


@aws_ssm_group.command(help="Compare .env and/or JSON file against parameter store")
@click.option(
    "--env-file",
    help="Path to .env file",
)
@click.option(
    "--json-file",
    help="Path to .json file containing an array of key/value objects",
)
@click.option(
    "--prefix",
    required=True,
    help="Path prefix for parameter store, e.g. /my-app/uat",
)
@click.option(
    "--include",
    help="Environment variables to include when comparing. Excludes all others. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
@click.option(
    "--exclude",
    help="Environment variables to exclude when comparing. CSV list, e.g. NODE_ENV,MY_VAR",
    default=""
)
@click.option(
    "--sensitive",
    is_flag=True,
    default=False,
    help="Show values as well as keys",
)
def diff(env_file, json_file, prefix, include, exclude, sensitive):
    session = _require_credentials()

    env_values = _load(env_file, json_file, include, exclude)
    prefix = _normalise_prefix(prefix)

    logger.info(f"Reading from region {session.region_name}")

    remote_values = read_parameters(ssm_client(), prefix)
    buckets = compare_values(env_values, remote_values)

    click.secho(f"Comparing {len(env_values)} local var(s) against {prefix}", fg="green")

    _report(buckets["new"], "+", "not in parameter store", "green", sensitive)
    _report(buckets["changed"], "~", "different in parameter store", "yellow", sensitive, remote_values)
    _report(buckets["remote_only"], "-", "only in parameter store", "cyan", sensitive)
    _report(buckets["unchanged"], "=", "same in parameter store", None, sensitive)


def _report(values, marker, label, colour, sensitive, remote_values=None):
    if not values:
        return

    click.secho(f"\n{len(values)} {label}:", fg=colour)

    for key in sorted(values):
        line = f"  {marker} {key}"
        if sensitive:
            if remote_values is not None:
                line += f": {remote_values[key]} -> {values[key]}"
            else:
                line += f": {values[key]}"

        click.secho(line, fg=colour)
