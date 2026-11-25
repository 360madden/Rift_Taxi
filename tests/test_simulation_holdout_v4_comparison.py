"""V4 protocol tests; generated results remain offline-only."""
import json
import unittest

from rift_taxi.simulation_holdout_v4_comparison import (
    candidate_lookahead, evaluate, OUTCOMES, summarize,
)


class V4ComparisonTests(unittest.TestCase):
    def test_zero_delay_and_bounded_candidate(self):
        self.assertEqual(candidate_lookahead(3.1, 0.), 1.5)
        self.assertAlmostEqual(candidate_lookahead(2.8, .12), 1.836)
        self.assertEqual(candidate_lookahead(20., 2.), 3.)

    def test_screen_rejects_loss_despite_improved_marginals(self):
        # Analytic control: net successes improve but a baseline success
        # is lost. The strict research screen must reject the candidate.
        def outcome(ok):
            return dict.fromkeys(OUTCOMES, ok)
        rows = []
        for delay in (0., .12, .36):
            pairs = [(True, True), (False, False)] if delay == 0. else [
                (True, False), (False, True), (False, True)]
            rows.extend(dict(delaySeconds=delay, baseline=outcome(a), candidate=outcome(b))
                        for a, b in pairs)
        summaries, gate = summarize(rows)
        self.assertTrue(gate["zeroDelayExactMatch"])
        self.assertTrue(gate["nonzeroDelaySettledGain"])
        self.assertFalse(gate["noBaselineSuccessLosses"])
        self.assertFalse(gate["meritsFurtherOfflineInvestigation"])
        self.assertEqual(summaries[1]["outcomes"]["geometricArrival"],
                         dict(both=0, lost=1, gained=2, neither=0))

    def test_complete_v4_comparison(self):
        report = evaluate()
        self.assertEqual((report["pairs"], report["simulations"]), (216, 432))
        self.assertEqual(len(report["rows"]), 216)
        self.assertFalse(report["physicalQualification"])
        self.assertFalse(report["gameInputSent"])
        self.assertTrue(report["researchScreen"]["zeroDelayExactMatch"])
        for group in report["summaries"]:
            self.assertEqual(group["pairs"], 72)
            for counts in group["outcomes"].values():
                self.assertEqual(sum(counts.values()), 72)
        for row in report["rows"]:
            for name in ("baseline", "candidate"):
                outcome = row[name]
                if not outcome["geometricArrival"]:
                    self.assertIsNone(outcome["settledErrorXZ"])
                    self.assertFalse(outcome["settledWithinTolerance"])
        # The research gate may reject the candidate. That is a valid
        # experimental result, not a reason to fail the regression suite.
        print("V4_COMPARISON " + json.dumps(
            {"summaries": report["summaries"], "researchScreen": report["researchScreen"]},
            sort_keys=True, allow_nan=False))
