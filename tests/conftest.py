"""Shared test configuration."""

import os

# Force pure-Python renderer in tests so that unit tests can call
# internal methods like _get_bg_pixel directly.
os.environ["FAMILYBOX_NO_FAST_RENDERER"] = "1"
