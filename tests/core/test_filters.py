from populate_secrets.core.filters import filter_env_values, parse_name_list

ENV_VALUES = {"APP_NAME": "hello", "DB_HOST": "localhost", "API_KEY": "abc"}


class TestParseNameList:
    def test_empty_string_yields_no_names(self):
        assert parse_name_list("") == []

    def test_splits_on_commas_and_trims(self):
        assert parse_name_list("A, B ,C") == ["A", "B", "C"]

    def test_ignores_blank_entries(self):
        assert parse_name_list("A,,B,") == ["A", "B"]


class TestFilterEnvValues:
    def test_no_filters_keeps_everything(self):
        assert filter_env_values(ENV_VALUES) == ENV_VALUES

    def test_include_drops_everything_not_named(self):
        assert filter_env_values(ENV_VALUES, include="APP_NAME") == {"APP_NAME": "hello"}

    def test_exclude_drops_named_vars(self):
        assert filter_env_values(ENV_VALUES, exclude="API_KEY") == {
            "APP_NAME": "hello",
            "DB_HOST": "localhost",
        }

    def test_exclude_wins_over_include(self):
        """A name in both lists must not be written."""
        assert filter_env_values(ENV_VALUES, include="APP_NAME,API_KEY", exclude="API_KEY") == {
            "APP_NAME": "hello",
        }

    def test_unknown_names_are_ignored(self):
        assert filter_env_values(ENV_VALUES, include="NOT_PRESENT") == {}

    def test_preserves_source_order(self):
        assert list(filter_env_values(ENV_VALUES)) == list(ENV_VALUES)
