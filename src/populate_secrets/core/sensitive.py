SENSITIVE_NAME_FRAGMENTS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def is_sensitive_name(key):
    """Whether a variable name looks like it holds a credential."""
    upper_key = key.upper()

    return any(fragment in upper_key for fragment in SENSITIVE_NAME_FRAGMENTS)
