"""Verify the prespecified scenario grid without evaluating its outcomes."""
from itertools import product
import unittest

from rift_taxi.simulation_holdout_v4_design import scenarios, ROUTES, OFFSETS, HEADINGS, PROFILES, DELAYS_SECONDS


class HoldoutV4DesignTests(unittest.TestCase):
    def test_complete_unique_grid(self):
        rows = scenarios()
        self.assertEqual(len(rows), 72)
        self.assertEqual(len({r["scenarioSHA256"] for r in rows}), 72)
        actual = {(s["routeId"], s["lateralOffset"], s["headingOffsetDegrees"],
                   s["speed"], s["maxYawRate"], s["dt"])
                  for r in rows for s in (r["scenario"],)}
        expected = {(name, o, h, *profile)
                    for (name, _), o, h, profile in product(ROUTES, OFFSETS, HEADINGS, PROFILES)}
        self.assertEqual(actual, expected)
        self.assertEqual(sum(len(r["delaySteps"]) for r in rows), 216)

    def test_delay_identity_and_repeatability(self):
        rows = scenarios()
        self.assertEqual(rows, scenarios())
        for r in rows:
            for n, seconds in zip(r["delaySteps"], DELAYS_SECONDS):
                self.assertAlmostEqual(n * r["scenario"]["dt"], seconds, places=12)
                self.assertIn(n, range(11))
            self.assertNotIn("outcomes", r)
