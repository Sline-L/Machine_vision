#!/usr/bin/env python3
"""右键运行：实时相机 + YOLO TensorRT engine + 当前分类 .pt。"""

import sys

from gp.launch import EXPORTS, start

if __name__ == "__main__":
    sys.exit(start(locator=EXPORTS / "model1.engine"))
