"""Worker rebuild and inspect-count hooks required by later Control."""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gp.frames import LatestFrame
from gp.types import InspectionResult
from gp.worker import InspectionWorker


class FakeInspector:
    def inspect(self, frame):
        del frame
        return InspectionResult(None)


class WorkerHookTests(unittest.TestCase):
    def setUp(self):
        self.results = []
        self.config = SimpleNamespace(video_path=None, inference_interval=0.01)
        self.frames = LatestFrame()
        self.worker = InspectionWorker(
            self.config,
            self.frames,
            on_result=self.results.append,
            on_status=lambda _message: None,
            on_error=lambda _message: None,
            on_video_complete=lambda _path: None,
        )

    def test_bump_inspect_is_monotonic_and_thread_safe(self):
        counts = []

        def run():
            for _ in range(50):
                counts.append(self.worker.bump_inspect())

        threads = [threading.Thread(target=run) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(self.worker.inspect_count, 200)
        self.assertEqual(len(set(counts)), 200)

    def test_drop_inspector_clears_loaded_model_without_second_thread(self):
        self.worker._inspector = FakeInspector()
        self.worker.start_inspection()
        self.worker.drop_inspector()
        self.assertFalse(self.worker.active)
        self.assertFalse(self.worker.model_loaded)

    def test_camera_cycle_records_freshness_and_count(self):
        import numpy as np

        self.worker.on_result = lambda result: (self.results.append(result), self.worker.pause())
        self.worker._inspector = FakeInspector()
        self.frames.publish(np.zeros((4, 4, 3), dtype=np.uint8))
        self.worker.start_inspection()
        self.worker._inspect_camera(self.worker._inspector)
        self.assertEqual(self.worker.inspect_count, 1)
        self.assertEqual(len(self.results), 1)
        result = self.results[0]
        self.assertEqual(result.source_frame_seq, 1)
        self.assertIsNotNone(result.inspection_age_ms)
        self.assertEqual(result.frame_lag, 0)
