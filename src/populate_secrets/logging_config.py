import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s\t%(message)s",
    datefmt="%Y-%m-%d_%H:%M:%S",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger()
