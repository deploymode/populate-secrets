from ..logging_config import logger


def parse_name_list(csv_value):
    """Split a CSV option value into variable names, ignoring blanks."""
    if not csv_value:
        return []

    return [name.strip() for name in csv_value.split(",") if name.strip()]


def filter_env_values(env_values, include="", exclude=""):
    """Keep only the variables selected by the --include/--exclude options.

    A non-empty include list excludes everything not named in it.
    """
    names_to_include = parse_name_list(include)
    names_to_exclude = parse_name_list(exclude)

    if names_to_include:
        logger.info("Including: {}".format("; ".join(names_to_include)))

    if names_to_exclude:
        logger.info("Excluding: {}".format("; ".join(names_to_exclude)))

    filtered = {}
    for key, value in env_values.items():
        if names_to_include and key not in names_to_include:
            continue

        if key in names_to_exclude:
            logger.info(f"Skipping {key}")
            continue

        filtered[key] = value

    return filtered
