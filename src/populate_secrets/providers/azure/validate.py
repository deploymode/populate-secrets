import re

KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
FORBIDDEN_VALUE_CHARS = ("\n", "\r", "\x00")


def validate_env_input(key, value):
    """Guard the `az` argv: reject keys and values it cannot carry safely."""
    if not KEY_PATTERN.match(key):
        raise ValueError(f"Invalid key format: {key}")

    if value and any(char in value for char in FORBIDDEN_VALUE_CHARS):
        raise ValueError(f"Invalid characters in value for key: {key}")
