"""Analytic controls for paired delay diagnostics."""
import unittest
from test_delay_factorial_audit import fixture
from rift_taxi.delay_factorial_diagnostics import diagnose


class DiagnosticTests(unittest.TestCase):
    def test_constant_delay_outcomes_have_no_matched_changes(self):
        # Fixture has 50% success independent of delay. It would be incorrect
        # to attribute its pre-existing failures to command delay.
        r = diagnose(fixture())
        self.assertEqual(r['matchedStarts'], 288)
        self.assertFalse(r['physicalQualification'])
        for level in r['routes'][0]['levels']:
            self.assertEqual(level['matchedPairs'], 288)
            self.assertEqual(level['arrivedButUnsettled'], 0)
            self.assertEqual(level['maxSettledErrorXZ'], .1)
            for counts in level['outcomes'].values():
                self.assertEqual(counts, dict(baselineSuccesses=144, delayedSuccesses=144, lost=0, gained=0))

    def test_bad_archive_rejected(self):
        r = fixture()
        r['cases'].pop()
        with self.assertRaises(ValueError):
            diagnose(r)
