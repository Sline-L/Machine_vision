import unittest

from edgemedic.bench import load_cases, score_case


class BenchTests(unittest.TestCase):
    def test_all_bundled_cases_pass(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 5)
        failed = []
        for case in cases:
            result = score_case(case)
            if not result["ok"]:
                failed.append((case["case"], result))
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
