"""Shared test configuration."""

import os
import sys
from pathlib import Path

# src/ 布局：把包根加入 sys.path（项目未配置安装型 build-system，无下载依赖）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Force pure-Python renderer in tests so that unit tests can call
# internal methods like _get_bg_pixel directly.
os.environ["FAMILYBOX_NO_FAST_RENDERER"] = "1"
