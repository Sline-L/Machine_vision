import json
import unittest

from edgemedic.rq1_dataset import build_cases, write_dataset
from edgemedic.rq1_represent import structured_view


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _flatten(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _flatten(value, f"{prefix}[{index}]")
    else:
        yield prefix, obj


class Rq1FormalParityTests(unittest.TestCase):
    def test_dataset_size_and_ids(self):
        cases = build_cases()
        self.assertEqual(len(cases), 30)
        families = {item["fault_family"] for item in cases}
        self.assertEqual(
            families,
            {"CAMERA_STALE", "INSPECTION_PAUSED", "SERIAL_FAIL", "WORKER_FAIL", "V5_OVERLOAD", "LOCATOR_OVERLOAD"},
        )

    def test_structured_does_not_add_named_fault(self):
        for case in build_cases():
            view = structured_view(case["state"])
            blob = json.dumps(view)
            self.assertNotIn("active_faults", view)
            self.assertNotIn("named_fault", blob)
            self.assertNotIn(case["ground_truth_fault"], json.dumps(view.get("components")))

    def test_measured_values_exist_in_raw_snapshot(self):
        skip_keys = {"capability_compare", "experience", "recent_actions"}
        for case in build_cases():
            snapshot = case["state"]
            view = structured_view(snapshot)
            raw_vals = {value for _, value in _flatten(snapshot) if not isinstance(value, (dict, list))}
            for key, value in _flatten({k: v for k, v in view.items() if k not in skip_keys}):
                if value in (None, [], {}):
                    continue
                if isinstance(value, (int, float, bool, str)):
                    self.assertIn(value, raw_vals, msg=f"{case['case_id']} {key}={value}")

    def test_write_roundtrip(self):
        path, payload = write_dataset()
        self.assertEqual(payload["independent_cases"], 30)
        self.assertTrue(path.is_file())
