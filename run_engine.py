#!/usr/bin/env python3
"""右键运行：实时相机 + Model1 TensorRT engine + Scratch V5 Model2。"""

import sys

from gp.launch import start
from gp.profiles import ENGINE_LOCATOR

if __name__ == "__main__":
    sys.exit(start(locator=ENGINE_LOCATOR))
