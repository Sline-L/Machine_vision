#!/usr/bin/env python3
"""右键运行（仅 NX）：把 model1.pt 编成 TensorRT engine。完成后用 run_engine.py 启动。"""

import sys

from gp.export_engine import DEFAULT_DEST, export_locator_engine


if __name__ == "__main__":
    try:
        path = export_locator_engine()
    except Exception as exc:
        print(f"导出失败：{exc}", file=sys.stderr)
        sys.exit(1)
    print(f"已生成 {path}")
    print("请右键运行 run_engine.py")
