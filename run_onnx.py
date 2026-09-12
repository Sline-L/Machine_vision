#!/usr/bin/env python3
"""右键运行：实时相机 + YOLO ONNX（本机 ORT 只有 CPU，仅用来对比，不要当产线格式）。"""

import sys

from gp.launch import EXPORTS, start

if __name__ == "__main__":
    sys.exit(start(locator=EXPORTS / "model1.onnx"))
