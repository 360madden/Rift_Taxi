"""Analytic controls for paired delay diagnostics."""
import random
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

    def test_diagnostics_independent_of_case_order(self):
        """Input row order is not part of the matched design identity."""
        report = fixture()
        expected = diagnose(report)
        random.Random(1729).shuffle(report["cases"])
        random.Random(73).shuffle(report["geometry"])
        self.assertEqual(diagnose(report), expected)

    def test_all_failure_route_has_no_terminal_measurements(self):
        """Relabel a known stratum as a separate route with no arrivals.

        Keep the original design complete and use the analytically known
        fixture outcomes, not the implementation under test, as the oracle.
        """
        report = fixture()
        # Every geometry contains successful low-speed cases; instead
        # exercise an all-failure report with all outcomes consistently false.
        for row in report["cases"]:
            row.update(status="timeout", geometricArrival=False,
                       settledWithinTolerance=False, arrivalAndDutyTarget=False,
                       settledErrorXZ=None, postArrivalDistanceXZ=None)
        for entry in report["profiles"] + report["byDelay"]:
            entry.update(geometricArrivals=0, settledWithinTolerance=0,
                         arrivalAndDutyTarget=0, settledOutside=0,
                         statusCounts={"timeout": entry["runs"]})
        for effect in report["matchedEffects"]:
            for field in effect["outcomes"]:
                effect["outcomes"][field] = dict(gained=0, lost=0, both=0, neither=144)
        result = diagnose(report)
        for level in result["routes"][0]["levels"]:
            self.assertEqual(level["matchedPairs"], 288)
            self.assertIsNone(level["maxSettledErrorXZ"])
            self.assertEqual(level["arrivedButUnsettled"], 0)
            for counts in level["outcomes"].values():
                self.assertEqual(counts, dict(baselineSuccesses=0, delayedSuccesses=0, lost=0, gained=0))

    def test_matched_gains_and_losses_do_not_cancel(self):
        """Swap the speed response at delayed levels.

        The marginal totals stay at 144 successes but each delayed pair
        flips. The speed-factor effect reverses at the affected delays;
        the two other factors retain their original analytic counts.
        """
        report = fixture()
        for row in report["cases"]:
            if row["nominalDelaySeconds"] == 0.:
                continue
            ok = not row["geometricArrival"]
            row.update(status="arrived" if ok else "timeout", geometricArrival=ok,
                       settledWithinTolerance=ok, arrivalAndDutyTarget=ok,
                       settledErrorXZ=.1 if ok else None, postArrivalDistanceXZ=0. if ok else None)
        for profile in report["profiles"]:
            if profile["nominalDelaySeconds"] == 0.:
                continue
            count = 36 if profile["speed"] == 3.4 else 0
            profile.update(geometricArrivals=count, settledWithinTolerance=count,
                           arrivalAndDutyTarget=count,
                           statusCounts={"arrived" if count else "timeout": 36})
        for effect in report["matchedEffects"]:
            if effect["factor"] == "speed" and effect["nominalDelaySeconds"] != 0.:
                for field in effect["outcomes"]:
                    effect["outcomes"][field] = dict(gained=144, lost=0, both=0, neither=0)
        for level in diagnose(report)["routes"][0]["levels"]:
            for counts in level["outcomes"].values():
                self.assertEqual(counts, dict(baselineSuccesses=144, delayedSuccesses=144, lost=144, gained=144))
