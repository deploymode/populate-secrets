import json

import click
import pytest

from populate_secrets.core.loader import load_env_values


class TestLoadEnvValues:
    def test_reads_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=hello\nDB_HOST=localhost\n")

        assert load_env_values(env_file=str(env_file)) == {
            "APP_NAME": "hello",
            "DB_HOST": "localhost",
        }

    def test_reads_json_file(self, tmp_path):
        json_file = tmp_path / "vars.json"
        json_file.write_text(json.dumps([{"APP_NAME": "hello"}, {"DB_HOST": "localhost"}]))

        assert load_env_values(json_file=str(json_file)) == {
            "APP_NAME": "hello",
            "DB_HOST": "localhost",
        }

    def test_json_overrides_env_file_for_same_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME=from-env\n")
        json_file = tmp_path / "vars.json"
        json_file.write_text(json.dumps([{"APP_NAME": "from-json"}]))

        values = load_env_values(env_file=str(env_file), json_file=str(json_file))

        assert values == {"APP_NAME": "from-json"}

    def test_no_sources_returns_empty(self):
        assert load_env_values() == {}

    def test_missing_env_file_is_an_error(self, tmp_path):
        """A typo'd path must fail loudly rather than write nothing."""
        with pytest.raises(click.ClickException, match="Env file not found"):
            load_env_values(env_file=str(tmp_path / "absent.env"))

    def test_missing_json_file_is_an_error(self, tmp_path):
        with pytest.raises(click.ClickException, match="JSON file not found"):
            load_env_values(json_file=str(tmp_path / "absent.json"))
