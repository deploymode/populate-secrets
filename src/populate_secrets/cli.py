import click

from .providers.aws_ssm.commands import aws_ssm_group
from .providers.azure.commands import azure_appservice_group, azure_pipelines_group
from .providers.gitlab.commands import gitlab_group


@click.group()
def cli():
    pass


cli.add_command(gitlab_group)
cli.add_command(aws_ssm_group)
cli.add_command(azure_pipelines_group)
cli.add_command(azure_appservice_group)


if __name__ == "__main__":
    cli()
