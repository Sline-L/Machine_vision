#!/usr/bin/env python3
"""右键运行：实时相机 + Model1 engine + Scratch V5 / Missing Hole V1。"""

import sys

from gp.launch import EXPORTS, start

if __name__ == "__main__":
    sys.exit(start(locator=EXPORTS / "model1.engine"))
