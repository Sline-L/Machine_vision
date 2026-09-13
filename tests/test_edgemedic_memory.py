import tempfile
import unittest
from pathlib import Path

from edgemedic.memory import MIN_REPEATED_SUCCESS, EpisodeStore
from edgemedic.reasoner import parse_tool_json


class EpisodeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = EpisodeStore(Path(self.dir.name) / "episodes.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_one_success_is_not_a_rule(self):
        self.store.record("CAMERA_STALE", "restart_camera", {}, True)
        self.assertIsNone(self.store.suggest("CAMERA_STALE"))

    def test_repeated_success_can_suggest(self):
        for _ in range(MIN_REPEATED_SUCCESS):
            self.store.record("CAMERA_STALE", "restart_camera", {}, True)
        suggested = self.store.suggest("CAMERA_STALE")
        self.assertEqual(suggested["name"], "restart_camera")

    def test_config_only_does_not_enter_memory(self):
        self.store.record("LOCATOR_OVERLOAD", "set_locator_profile", {"profile": "trt_fast"}, verify_level="config")
        self.assertIsNone(self.store.suggest("LOCATOR_OVERLOAD"))
        self.assertEqual(sum(self.store.successes.values()), 0)

    def test_function_success_can_accumulate(self):
        for _ in range(MIN_REPEATED_SUCCESS):
            self.store.record("LOCATOR_OVERLOAD", "set_locator_profile", {"profile": "trt_fast"}, verify_level="function")
        suggested = self.store.suggest("LOCATOR_OVERLOAD")
        self.assertEqual(suggested["params"]["profile"], "trt_fast")

    def test_more_failures_than_wins_not_suggested(self):
        for _ in range(MIN_REPEATED_SUCCESS):
            self.store.record("SERIAL_FAIL", "reconnect_serial", {}, True)
        for _ in range(MIN_REPEATED_SUCCESS + 1):
            self.store.record("SERIAL_FAIL", "reconnect_serial", {}, False)
        self.assertIsNone(self.store.suggest("SERIAL_FAIL"))


class ReasonerParseTests(unittest.TestCase):
    def test_extracts_json_object(self):
        text = 'Sure.\n{"tool": "set_inference_profile", "params": {"profile": "SPARSE"}}\n'
        action = parse_tool_json(text)
        self.assertEqual(action["name"], "set_inference_profile")
        self.assertEqual(action["params"]["profile"], "SPARSE")

    def test_rejects_shell_and_unimplemented_profile(self):
        self.assertIsNone(parse_tool_json('{"tool": "shell", "params": {"cmd": "reboot"}}'))
        self.assertIsNone(parse_tool_json('{"tool": "set_inference_profile", "params": {"profile": "CLASSIFY_ONLY"}}'))
        action = parse_tool_json('{"tool": "set_locator_profile", "params": {"profile": "pt_safe"}}')
        self.assertEqual(action["name"], "set_locator_profile")
        trt = parse_tool_json('{"tool": "set_inference_profile", "params": {"profile": "TRT_FAST"}}')
        self.assertEqual(trt["params"]["profile"], "TRT_FAST")

    def test_close_typo_maps_to_whitelist(self):
        action = parse_tool_json('{"tool": "econnect_serial", "params": {}}')
        self.assertEqual(action["name"], "reconnect_serial")
        action = parse_tool_json('{"tool": "restart_cmera", "params": {}}')
        self.assertEqual(action["name"], "restart_camera")

    def test_does_not_confuse_restart_worker_with_camera(self):
        self.assertEqual(parse_tool_json('{"tool": "restart_worker", "params": {}}')["name"], "restart_worker")
        self.assertIsNone(parse_tool_json('{"tool": "restart", "params": {}}'))

    def test_strips_think_and_reads_json(self):
        text = "<think>planning</think>\n{\"tool\": \"restart_camera\", \"params\": {}}\n"
        self.assertEqual(parse_tool_json(text)["name"], "restart_camera")


if __name__ == "__main__":
    unittest.main()
