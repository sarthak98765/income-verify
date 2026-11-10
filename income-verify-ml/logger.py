import logging
import sys

custom_logger = logging.getLogger("income-verify")
custom_logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
custom_logger.addHandler(handler)
