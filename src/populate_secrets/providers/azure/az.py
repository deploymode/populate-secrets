from subprocess import CalledProcessError, run

import click


def run_az(args):
    """Run an `az` command, raising CalledProcessError on a non-zero exit."""
    try:
        return run(["az", *args], check=True, capture_output=True)
    except FileNotFoundError:
        raise click.ClickException("Command `az` not found. Install the Azure CLI.")


def ensure_devops_extension():
    try:
        run_az(["pipelines", "--help"])
    except CalledProcessError:
        raise click.ClickException(
            "Install Azure Devops extension: `az extension add --name azure-devops`"
        )
