"""Tests for the azure-pipelines and azure-appservice provider commands.

The `az` CLI is never executed: these assert the argv the commands construct.
"""

from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

import click.testing
import pytest

from populate_secrets.cli import cli


@pytest.fixture
def run_az():
    with patch("populate_secrets.providers.azure.az.run_az") as mock_run_az:
        yield mock_run_az


def _invoke(args):
    runner = click.testing.CliRunner()
    return runner.invoke(cli, args)


def _argv_calls(run_az):
    """The az argv lists, excluding the `az pipelines --help` availability probe."""
    return [call.args[0] for call in run_az.call_args_list if call.args[0][:2] != ["pipelines", "--help"]]


def _env_file(tmp_path, content):
    env_file = tmp_path / ".env"
    env_file.write_text(content)
    return str(env_file)


class TestPipelinesWrite:
    def test_creates_variable_with_allow_override(self, tmp_path, run_az):
        result = _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\n"),
            "--pipeline-name", "my-pipeline",
        ])

        assert result.exit_code == 0, result.output
        assert _argv_calls(run_az) == [[
            "pipelines", "variable", "create",
            "--pipeline-name", "my-pipeline",
            "--allow-override", "true",
            "--name", "APP_NAME",
            "--value", "hello",
            "--secret", "false",
        ]]

    def test_sensitive_names_are_marked_secret(self, tmp_path, run_az):
        _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "API_KEY=abc\n"),
            "--pipeline-name", "my-pipeline",
        ])

        assert _argv_calls(run_az)[0][-2:] == ["--secret", "true"]

    def test_falls_back_to_update_when_create_fails(self, tmp_path, run_az):
        """`az pipelines variable create` fails for a variable that already exists."""
        # The first result answers the `az pipelines --help` probe.
        run_az.side_effect = [MagicMock(), CalledProcessError(1, "az"), MagicMock()]

        result = _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\n"),
            "--pipeline-name", "my-pipeline",
        ])

        assert result.exit_code == 0, result.output
        actions = [argv[2] for argv in _argv_calls(run_az)]
        assert actions == ["create", "update"]

    def test_invalid_key_is_skipped_without_calling_az(self, tmp_path, run_az):
        result = _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "lower_case=hello\n"),
            "--pipeline-name", "my-pipeline",
        ])

        assert result.exit_code == 0, result.output
        assert _argv_calls(run_az) == []

    def test_excluded_vars_are_not_written(self, tmp_path, run_az):
        _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\nAPI_KEY=abc\n"),
            "--pipeline-name", "my-pipeline",
            "--exclude", "API_KEY",
        ])

        written = [argv[argv.index("--name") + 1] for argv in _argv_calls(run_az)]
        assert written == ["APP_NAME"]

    def test_missing_devops_extension_is_reported(self, tmp_path, run_az):
        run_az.side_effect = CalledProcessError(2, "az")

        result = _invoke([
            "azure-pipelines", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\n"),
            "--pipeline-name", "my-pipeline",
        ])

        assert result.exit_code == 1
        assert "azure-devops" in result.output
        assert "Traceback" not in result.output


class TestAppServiceWrite:
    def test_sets_one_setting_per_variable(self, tmp_path, run_az):
        result = _invoke([
            "azure-appservice", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\n"),
            "--app-name", "my-app",
            "--resource-group", "my-group",
        ])

        assert result.exit_code == 0, result.output
        assert _argv_calls(run_az) == [[
            "webapp", "config", "appsettings", "set",
            "--resource-group", "my-group",
            "--name", "my-app",
            "--settings", "APP_NAME=hello",
        ]]

    def test_a_failed_variable_does_not_stop_the_rest(self, tmp_path, run_az):
        run_az.side_effect = [CalledProcessError(1, "az"), MagicMock()]

        result = _invoke([
            "azure-appservice", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\nDB_HOST=localhost\n"),
            "--app-name", "my-app",
            "--resource-group", "my-group",
        ])

        assert result.exit_code == 0, result.output
        assert len(_argv_calls(run_az)) == 2

    def test_does_not_probe_for_the_devops_extension(self, tmp_path, run_az):
        """App Service settings use the core az CLI, not the azure-devops extension."""
        _invoke([
            "azure-appservice", "write",
            "--env-file", _env_file(tmp_path, "APP_NAME=hello\n"),
            "--app-name", "my-app",
            "--resource-group", "my-group",
        ])

        probes = [c for c in run_az.call_args_list if c.args[0][:2] == ["pipelines", "--help"]]
        assert probes == []


class TestInputGuards:
    def test_pipelines_requires_an_input_file(self, run_az):
        result = _invoke(["azure-pipelines", "write", "--pipeline-name", "my-pipeline"])

        assert result.exit_code == 1
        assert "--env-file" in result.output

    def test_appservice_requires_an_input_file(self, run_az):
        result = _invoke([
            "azure-appservice", "write", "--app-name", "my-app", "--resource-group", "my-group",
        ])

        assert result.exit_code == 1
        assert "--env-file" in result.output
