#############################################################
# Manage Gitlab secrets
#
#############################################################

import os
from traceback import print_exc

import click
import gitlab
from gitlab.v4.objects.projects import Project

from ...core.filters import filter_env_values
from ...core.loader import load_env_values
from ...core.sensitive import is_sensitive_name
from ...logging_config import logger
from .client import gitlab_client


@click.group(name="gitlab", help="Manage Gitlab CI/CD variables")
def gitlab_group():
    pass


@gitlab_group.command(help="Populate Gitlab project vars")
@click.option(
    "--env-file",
    help="Path to .env file",
)
@click.option(
    "--json-file",
    help="Path to .json file containing an array of key/value objects",
)
@click.option(
    "--environment",
    required=True,
    help="Name of gitlab environment, e.g. `uat`",
)
@click.option(
    "--gitlab-host",
    required=True,
    help="Gitlab server host",
)
@click.option(
    "--project",
    required=True,
    help="Gitlab project name or ID",
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
    "--mask",
    is_flag=True,
    default=False,
    help="Mask variables with KEY, SECRET, TOKEN or PASSWORD in their name",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Produce debug output",
)
def write(env_file, json_file, environment, gitlab_host, project, include, exclude, mask, debug):
    try:
        gitlab_token = os.environ["GITLAB_TOKEN"]
    except KeyError:
        raise click.ClickException(
            f"GITLAB_TOKEN must be set. Get token from https://{gitlab_host}/-/profile/personal_access_tokens"
        )

    if not env_file and not json_file:
        raise click.ClickException("Provide --env-file and/or --json-file")

    env_values = filter_env_values(
        load_env_values(env_file=env_file, json_file=json_file),
        include=include,
        exclude=exclude,
    )

    # Create gitlab client
    gitlabClient = gitlab_client(gitlab_host, gitlab_token)
    if debug:
        gitlabClient.enable_debug()

    gitlabProject: Project

    try:
        gitlabProject = gitlabClient.projects.get(id=project)
    except gitlab.exceptions.GitlabHttpError:
        raise click.ClickException("Could not find project: {}".format(project))

    if not gitlabProject:
        raise click.ClickException("Could not find project: {}".format(project))

    # Get all existing vars
    gl_project_vars = gitlabProject.variables.list(get_all=True)
    logger.debug(gl_project_vars)
    gitlab_project_variable_keys_with_scope = list(map(lambda o: {"environment_scope": o.environment_scope, "key": o.key}, gl_project_vars))
    logger.debug(gitlab_project_variable_keys_with_scope)
    gitlab_project_variable_keys_by_scope = dict()
    for d in gitlab_project_variable_keys_with_scope:
        gitlab_project_variable_keys_by_scope.setdefault(
                    d["environment_scope"], []
                ).append(d["key"])

    logger.debug(gitlab_project_variable_keys_by_scope)

    for key, value in env_values.items():
        is_update = False

        # Write to Gitlab API
        try:
            if key in gitlab_project_variable_keys_by_scope.get(environment, []):
                is_update = True
                # Update
                project_var = [v for v in gl_project_vars if v.key == key][0]
                project_var.value = value
                if mask and is_sensitive_name(key):
                    project_var.masked = True
                project_var.save(filter={'environment_scope': environment})
            else:
                # Add
                payload = {
                    "key": key,
                    "value": value,
                    "environment_scope": environment,
                }

                if mask and is_sensitive_name(key):
                    payload["masked"] = True

                logger.debug(payload)

                gitlabProject.variables.create(payload)
        except gitlab.exceptions.GitlabHttpError:
            logger.info("Failed to write {} due to error from Gitlab API".format(key))
            print_exc()
            continue
        except gitlab.exceptions.GitlabError:
            logger.info("Failed to write {} due to unexpected Gitlab error".format(key))
            print_exc()
            continue

        logger.info(
            "Wrote {} variable {} to Gitlab API in environment {}".format(
                "updated" if is_update else "new", key, environment
            )
        )

    logger.info("Done")


@gitlab_group.command(help="Get Gitlab project vars")
@click.option(
    "--environment",
    required=True,
    help="Name of gitlab environment, e.g. `uat`",
)
@click.option(
    "--gitlab-host",
    required=True,
    help="Gitlab server host",
)
@click.option(
    "--project",
    required=True,
    help="Gitlab project name or ID",
)
@click.option(
    "--export",
    is_flag=True,
    help="Export variables to file: $scope.env",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Produce debug output",
)
def get(environment, gitlab_host, project, export, debug):
    try:
        gitlab_token = os.environ["GITLAB_TOKEN"]
    except KeyError:
        raise click.ClickException(
            f"GITLAB_TOKEN must be set. Get token from https://{gitlab_host}/-/profile/personal_access_tokens"
        )

    # Create gitlab client
    gitlabClient = gitlab_client(gitlab_host, gitlab_token)
    if debug:
        gitlabClient.enable_debug()

    logger.info(f"Loading project vars from {project}")

    try:
        gitlabProject = gitlabClient.projects.get(id=project)
    except gitlab.exceptions.GitlabHttpError:
        raise click.ClickException("Could not find project: {}".format(project))

    if not gitlabProject:
        raise click.ClickException("Could not find project: {}".format(project))

    click.secho(f"Getting vars from {gitlabProject.name} ({gitlabProject.id})", fg='green')

    gitlabProjectVariables = gitlabProject.variables.list(get_all=True)
    export_opened = set()
    for variable in sorted(gitlabProjectVariables, key=lambda v: v.key):
        scope = 'global' if variable.environment_scope == '*' else variable.environment_scope
        if scope == environment or scope == 'global':
            click.secho(f"[{variable.environment_scope}] {variable.key}={variable.value}", fg='yellow')

            if export:
                logger.debug(f"Writing {variable.key} to {scope}.env")
                mode = "a" if scope in export_opened else "w"
                with open(f"{scope}.env", mode) as f:
                    f.write(f"{variable.key}={variable.value}\n")
                export_opened.add(scope)

    logger.info("Done")


@gitlab_group.command(name="list", help="List Gitlab project vars for an environment")
@click.option(
    "--environment",
    required=True,
    help="Name of gitlab environment, e.g. `uat`",
)
@click.option(
    "--gitlab-host",
    required=True,
    help="Gitlab server host",
)
@click.option(
    "--project",
    required=True,
    help="Gitlab project name or ID",
)
@click.option(
    "--sensitive",
    is_flag=True,
    default=False,
    help="Show all values including masked ones",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Produce debug output",
)
def list_vars(environment, gitlab_host, project, sensitive, debug):
    try:
        gitlab_token = os.environ["GITLAB_TOKEN"]
    except KeyError:
        raise click.ClickException(
            f"GITLAB_TOKEN must be set. Get token from https://{gitlab_host}/-/profile/personal_access_tokens"
        )

    gitlabClient = gitlab_client(gitlab_host, gitlab_token)
    if debug:
        gitlabClient.enable_debug()

    try:
        gitlabProject = gitlabClient.projects.get(id=project)
    except gitlab.exceptions.GitlabHttpError:
        raise click.ClickException(
            "Could not find project: {}".format(project)
        )

    if not gitlabProject:
        raise click.ClickException("Could not find project: {}".format(project))

    click.secho(
        f"Variables for {gitlabProject.name} ({gitlabProject.id}) — environment: {environment}",
        fg="green",
    )

    variables = gitlabProject.variables.list(get_all=True)

    env_vars = []
    for v in variables:
        scope = "global" if v.environment_scope == "*" else v.environment_scope
        if scope == environment or scope == "global":
            env_vars.append(v)

    if not env_vars:
        click.secho("No variables found.", fg="yellow")
        return

    # Determine column widths
    max_key_len = max(len(v.key) for v in env_vars)
    max_scope_len = max(len(v.environment_scope) for v in env_vars)

    for v in env_vars:
        if sensitive or not v.masked:
            display_value = v.value
        else:
            display_value = "********"

        scope_label = v.environment_scope
        key_col = v.key.ljust(max_key_len)
        scope_col = scope_label.ljust(max_scope_len)
        masked_label = " [masked]" if v.masked else ""

        click.echo(f"  {scope_col}  {key_col}  {display_value}{masked_label}")

    click.secho(f"\n{len(env_vars)} variable(s) found.", fg="green")


@gitlab_group.command(help="Download Gitlab project vars to an .env file")
@click.option(
    "--environment",
    required=True,
    help="Name of gitlab environment, e.g. `uat`",
)
@click.option(
    "--gitlab-host",
    required=True,
    help="Gitlab server host",
)
@click.option(
    "--project",
    required=True,
    help="Gitlab project name or ID",
)
@click.option(
    "--output-dir",
    default=".",
    help="Directory to save the .env file (default: current directory)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Produce debug output",
)
def download(environment, gitlab_host, project, output_dir, debug):
    try:
        gitlab_token = os.environ["GITLAB_TOKEN"]
    except KeyError:
        raise click.ClickException(
            f"GITLAB_TOKEN must be set. Get token from https://{gitlab_host}/-/profile/personal_access_tokens"
        )

    if not os.path.isdir(output_dir):
        raise click.ClickException(f"Output directory does not exist: {output_dir}")

    gitlabClient = gitlab_client(gitlab_host, gitlab_token)
    if debug:
        gitlabClient.enable_debug()

    try:
        gitlabProject = gitlabClient.projects.get(id=project)
    except gitlab.exceptions.GitlabHttpError:
        raise click.ClickException("Could not find project: {}".format(project))

    if not gitlabProject:
        raise click.ClickException("Could not find project: {}".format(project))

    click.secho(
        f"Downloading vars from {gitlabProject.name} ({gitlabProject.id}) — environment: {environment}",
        fg="green",
    )

    variables = gitlabProject.variables.list(get_all=True)

    env_vars = []
    for v in variables:
        scope = "global" if v.environment_scope == "*" else v.environment_scope
        if scope == environment or scope == "global":
            env_vars.append(v)

    if not env_vars:
        click.secho("No variables found.", fg="yellow")
        return

    env_vars.sort(key=lambda v: v.key)

    output_path = os.path.join(output_dir, f"{environment}.env")

    if os.path.exists(output_path):
        click.secho(f"File already exists: {output_path}", fg="yellow")
        choice = click.prompt(
            "Choose action",
            type=click.Choice(["overwrite", "rename", "cancel"], case_sensitive=False),
            default="cancel",
        )
        if choice == "cancel":
            click.secho("Cancelled.", fg="red")
            return
        elif choice == "rename":
            n = 1
            while True:
                output_path = os.path.join(output_dir, f"{environment}-{n}.env")
                if not os.path.exists(output_path):
                    break
                n += 1

    with open(output_path, "w") as f:
        for v in env_vars:
            f.write(f"{v.key}={v.value}\n")

    click.secho(f"Saved {len(env_vars)} variable(s) to {output_path}", fg="green")
