"""GearPro Web application entry point."""

import argparse
import os
from pathlib import Path

from .config import AppConfig


def build_parser():
    parser = argparse.ArgumentParser(description="GearPro 齿轮视觉检测 Web 系统")
    parser.add_argument("--host", default=os.getenv("GEARPRO_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("GEARPRO_WEB_PORT", "8000")))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--video", type=Path, help="使用服务器上的视频文件进入测试模式")
    source.add_argument(
        "--replay",
        type=Path,
        help="从图片目录回放真实推理 cycle（不接摄像头）。不要用锁定的 test_scratch 调阈值。",
    )
    parser.add_argument("--replay-once", action="store_true", help="回放到最后一张后停止，不循环")
    parser.add_argument(
        "--control-port",
        type=int,
        default=int(os.getenv("GEARPRO_CONTROL_PORT", "8787")),
        help="本机 EdgeMedic Control API 端口，0 关闭",
    )
    parser.add_argument("--no-control", action="store_true", help="不启动 Control API")
    return parser


def build_application(config=None):
    from .web import create_app
    return create_app(config or AppConfig.from_environment())


def main(argv=None):
    args = build_parser().parse_args(argv)
    password = os.getenv("GEARPRO_WEB_PASSWORD", "")
    if args.host not in ("127.0.0.1", "localhost", "::1") and not password:
        raise SystemExit("局域网监听必须设置 GEARPRO_WEB_PASSWORD")
    config = AppConfig.from_environment()
    config.control_host = os.getenv("GEARPRO_CONTROL_HOST", "127.0.0.1")
    config.control_port = 0 if args.no_control else args.control_port
    if args.video is not None:
        video_path = args.video.expanduser().resolve()
        if not video_path.is_file():
            raise SystemExit(f"找不到视频文件：{video_path}")
        config.video_path = video_path
        config.replay_dir = None
        config.mode = "视频测试模式"
        config.serial_enabled = False
    if args.replay is not None:
        replay_dir = args.replay.expanduser().resolve()
        if not replay_dir.is_dir():
            raise SystemExit(f"找不到 replay 目录：{replay_dir}")
        config.replay_dir = replay_dir
        config.video_path = None
        config.replay_loop = not args.replay_once
        config.mode = "数据集回放模式"
        config.serial_enabled = False
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Web 依赖未安装，请运行 python -m pip install -r requirements.txt") from exc
    uvicorn.run(build_application(config), host=args.host, port=args.port, log_level="info")
    return 0
