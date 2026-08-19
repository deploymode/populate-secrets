"""Tests for the aws-ssm provider commands.

Mocks only at the AWS API boundary, using botocore's Stubber so the request
parameters are validated against the real SSM service model.
"""

import json
from unittest.mock import MagicMock, patch

import boto3
import click.testing
import pytest
from botocore.stub import Stubber

from populate_secrets.cli import cli

REGION = "ap-southeast-2"


@pytest.fixture
def ssm_stub():
    client = boto3.client(
        "ssm",
        region_name=REGION,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    with Stubber(client) as stubber:
        yield client, stubber


def _put_parameter_params(name, value):
    return {"Name": name, "Value": value, "Type": "SecureString", "Overwrite": True}


def _put_parameter_response(version=1):
    return {
        "Version": version,
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }


def _invoke(client, args, credentials=object()):
    session = MagicMock()
    session.region_name = REGION
    session.get_credentials.return_value = credentials

    with patch("populate_secrets.providers.aws_ssm.commands.ssm_client", return_value=client):
        with patch("populate_secrets.providers.aws_ssm.commands.aws_session", return_value=session):
            runner = click.testing.CliRunner()
            return runner.invoke(cli, args)


class TestWrite:
    def test_writes_each_var_as_a_securestring(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\nAPI_KEY=abc\n")

        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/APP_NAME", "hello")
        )
        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/API_KEY", "abc")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_trailing_slash_is_stripped_from_prefix(self, tmp_path, ssm_stub):
        """Without this the parameter path would contain a double slash."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/APP_NAME", "hello")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat/",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_empty_values_are_skipped(self, tmp_path, ssm_stub):
        """SSM rejects an empty parameter value, so those vars must not be sent."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\nEMPTY=\n")

        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/APP_NAME", "hello")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_json_file_vars_are_written(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        json_file = tmp_path / "vars.json"
        json_file.write_text(json.dumps([{"APP_NAME": "hello"}]))

        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/APP_NAME", "hello")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--json-file", str(json_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_excluded_vars_are_not_written(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\nAPI_KEY=abc\n")

        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/APP_NAME", "hello")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file),
            "--prefix", "/app/uat", "--exclude", "API_KEY",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_aws_error_reports_the_failing_parameter(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        stubber.add_client_error("put_parameter", service_error_code="AccessDeniedException")

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 1
        assert "/app/uat/APP_NAME" in result.output
        assert "Traceback" not in result.output


def _get_parameters_by_path_params(prefix):
    return {"Path": prefix, "Recursive": False, "WithDecryption": True}


def _parameters_response(values, next_token=None):
    response = {
        "Parameters": [
            {"Name": name, "Value": value, "Type": "SecureString"}
            for name, value in values.items()
        ]
    }
    if next_token:
        response["NextToken"] = next_token

    return response


class TestDiff:
    def test_reports_new_changed_and_unchanged_vars(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("NEW_VAR=n\nCHANGED_VAR=local\nSAME_VAR=s\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({
                "/app/uat/CHANGED_VAR": "remote",
                "/app/uat/SAME_VAR": "s",
                "/app/uat/REMOTE_ONLY": "r",
            }),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        assert "+ NEW_VAR" in result.output
        assert "~ CHANGED_VAR" in result.output
        assert "= SAME_VAR" in result.output
        assert "- REMOTE_ONLY" in result.output
        stubber.assert_no_pending_responses()

    def test_values_are_hidden_unless_sensitive_is_passed(self, tmp_path, ssm_stub):
        """Decrypted secrets should not reach the terminal by default."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=local-secret\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/API_KEY": "remote-secret"}),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        assert "API_KEY" in result.output
        assert "local-secret" not in result.output
        assert "remote-secret" not in result.output

    def test_sensitive_shows_both_sides_of_a_change(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=local-secret\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/API_KEY": "remote-secret"}),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file),
            "--prefix", "/app/uat", "--sensitive",
        ])

        assert "remote-secret -> local-secret" in result.output

    def test_reads_every_page_of_parameters(self, tmp_path, ssm_stub):
        """Prefixes with more than one page of parameters must not report
        page-two vars as missing."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("PAGE_TWO_VAR=v\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/PAGE_ONE_VAR": "1"}, next_token="more"),
            _get_parameters_by_path_params("/app/uat"),
        )
        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/PAGE_TWO_VAR": "v"}),
            dict(_get_parameters_by_path_params("/app/uat"), NextToken="more"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        assert "= PAGE_TWO_VAR" in result.output
        stubber.assert_no_pending_responses()

    def test_excluded_vars_are_not_compared(self, tmp_path, ssm_stub):
        """The diff must filter exactly as the write it previews would."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\nAPI_KEY=abc\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({}),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file),
            "--prefix", "/app/uat", "--exclude", "API_KEY",
        ])

        assert "APP_NAME" in result.output
        assert "API_KEY" not in result.output

    def test_trailing_slash_is_stripped_from_prefix(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({}),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat/",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_read_error_is_reported(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        stubber.add_client_error(
            "get_parameters_by_path", service_error_code="AccessDeniedException"
        )

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 1
        assert "/app/uat" in result.output
        assert "Traceback" not in result.output

    def test_missing_credentials_fails_before_reading(self, tmp_path, ssm_stub):
        client, _ = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        result = _invoke(client, [
            "aws-ssm", "diff", "--env-file", str(env_file), "--prefix", "/app/uat",
        ], credentials=None)

        assert result.exit_code == 1
        assert "AWS credentials not found" in result.output


class TestWriteSkipExisting:
    def test_only_writes_vars_missing_from_parameter_store(self, tmp_path, ssm_stub):
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("NEW_VAR=n\nEXISTING_VAR=local\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/EXISTING_VAR": "remote"}),
            _get_parameters_by_path_params("/app/uat"),
        )
        stubber.add_response(
            "put_parameter", _put_parameter_response(), _put_parameter_params("/app/uat/NEW_VAR", "n")
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file),
            "--prefix", "/app/uat", "--skip-existing",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_existing_var_is_skipped_even_when_the_value_differs(self, tmp_path, ssm_stub):
        """The flag means 'do not touch what is already there', so a changed
        value is left alone rather than overwritten."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=local\n")

        stubber.add_response(
            "get_parameters_by_path",
            _parameters_response({"/app/uat/EXISTING_VAR": "remote"}),
            _get_parameters_by_path_params("/app/uat"),
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file),
            "--prefix", "/app/uat", "--skip-existing",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()

    def test_parameter_store_is_not_read_without_the_flag(self, tmp_path, ssm_stub):
        """A plain write must not need the extra read permissions."""
        client, stubber = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=local\n")

        stubber.add_response(
            "put_parameter",
            _put_parameter_response(),
            _put_parameter_params("/app/uat/EXISTING_VAR", "local"),
        )

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 0, result.output
        stubber.assert_no_pending_responses()


class TestWriteGuards:
    def test_missing_credentials_fails_before_loading(self, tmp_path, ssm_stub):
        client, _ = ssm_stub
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\n")

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(env_file), "--prefix", "/app/uat",
        ], credentials=None)

        assert result.exit_code == 1
        assert "AWS credentials not found" in result.output
        assert "Traceback" not in result.output

    def test_no_input_file_is_an_error(self, ssm_stub):
        client, _ = ssm_stub

        result = _invoke(client, ["aws-ssm", "write", "--prefix", "/app/uat"])

        assert result.exit_code == 1
        assert "--env-file" in result.output

    def test_missing_env_file_is_an_error(self, tmp_path, ssm_stub):
        client, _ = ssm_stub

        result = _invoke(client, [
            "aws-ssm", "write", "--env-file", str(tmp_path / "absent.env"), "--prefix", "/app/uat",
        ])

        assert result.exit_code == 1
        assert "Env file not found" in result.output
