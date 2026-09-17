from pathlib import Path
import unittest

from gp.app import build_parser


class CommandLineTests(unittest.TestCase):
    def test_web_defaults(self):
        args = build_parser().parse_args([])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 8000)

    def test_video_and_bind_arguments(self):
        args = build_parser().parse_args(
            ["--video", "fixtures/gears.mp4", "--host", "127.0.0.1", "--port", "9000"]
        )
        self.assertEqual(Path(args.video), Path("fixtures/gears.mp4"))
        self.assertEqual((args.host, args.port), ("127.0.0.1", 9000))


if __name__ == "__main__":
    unittest.main()
