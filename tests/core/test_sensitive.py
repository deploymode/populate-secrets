import pytest

from populate_secrets.core.sensitive import is_sensitive_name


@pytest.mark.parametrize("key", ["API_KEY", "MY_SECRET", "AUTH_TOKEN", "DB_PASSWORD"])
def test_credential_names_are_sensitive(key):
    assert is_sensitive_name(key) is True


@pytest.mark.parametrize("key", ["APP_NAME", "DB_HOST", "NODE_ENV"])
def test_ordinary_names_are_not_sensitive(key):
    assert is_sensitive_name(key) is False


def test_match_is_case_insensitive():
    assert is_sensitive_name("stripe_secret_key") is True
