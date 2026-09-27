"""src/Version.ini 版本配置测试(唯一来源)。"""

import re

from window.resources import get_version, version_ini_path


def test_version_ini_exists() -> None:
    assert version_ini_path().is_file()


def test_get_version_is_numeric() -> None:
    assert re.fullmatch(r"\d+(\.\d+){1,3}", get_version())
