import pytest

from populate_secrets.providers.azure.validate import validate_env_input


@pytest.mark.parametrize("key", ["APP_NAME", "A", "DB_HOST_2"])
def test_accepts_upper_snake_case_keys(key):
    validate_env_input(key, "value")


@pytest.mark.parametrize("key", ["app_name", "2FA_CODE", "APP-NAME", "APP NAME", ""])
def test_rejects_keys_az_cannot_carry(key):
    with pytest.raises(ValueError, match="Invalid key format"):
        validate_env_input(key, "value")


@pytest.mark.parametrize("value", ["line1\nline2", "carriage\rreturn", "null\x00byte"])
def test_rejects_values_with_control_characters(value):
    """These would truncate or split the value once passed through the az argv."""
    with pytest.raises(ValueError, match="Invalid characters in value"):
        validate_env_input("APP_NAME", value)


def test_accepts_empty_value():
    validate_env_input("APP_NAME", "")


def test_accepts_none_value():
    validate_env_input("APP_NAME", None)
