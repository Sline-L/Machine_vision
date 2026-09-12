#!/usr/bin/env python3
"""右键运行：实时相机 + 当前 .pt 模型（定位 YOLO，分类 EfficientNet-B0）。"""

import sys

from gp.launch import start

if __name__ == "__main__":
    sys.exit(start())
