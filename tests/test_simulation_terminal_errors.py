"""Synthetic endpoint-plane and tolerance classification regressions.

No game state, OS input, or controller changes. Preserve every failed
approach and distinguish signed geometric error from radial distance.
"""
import math
import unittest
from rift_taxi.contracts import TraceError
from rift_taxi.simulation_terminal_errors import decompose_endpoint_error, evaluate_terminal_errors


class TerminalErrorTests(unittest.TestCase):
    def test_signed_components_and_rotation_invariance(self):
        """Final-leg local axes must not depend on global route orientation."""
        a,b,p = (0.,0.,0.),(4.,0.,0.),(3.,0.,2.)
        expected = decompose_endpoint_error(p,a,b)
        self.assertEqual(expected["longitudinalXZ"],-1.)
        self.assertEqual(expected["lateralXZ"],2.)
        self.assertAlmostEqual(expected["radialXZ"],math.sqrt(5.))
        def rotate_translate(x):
            return (10.-x[2],x[1],7.+x[0])
        rotated = decompose_endpoint_error(*(rotate_translate(x) for x in (p,a,b)))
        self.assertEqual(expected,rotated)

    def test_degenerate_final_leg_refused(self):
        """Do not invent a tangent for coincident final vertices."""
        with self.assertRaises(TraceError):
            decompose_endpoint_error((1.,0.,1.),(0.,0.,0.),(0.,0.,0.))

    def test_frozen_error_distribution(self):
        """Pin the observed split between before-plane and beyond-plane failures."""
        report = evaluate_terminal_errors()
        self.assertEqual(len(report["cases"]),432)
        groups = report["summary"]
        self.assertEqual([r["geometricArrivals"] for r in groups],[108,106,96,72])
        self.assertEqual([r["settledOutside"] for r in groups],[0,0,5,5])
        self.assertEqual(groups[2]["outsideEndpointPlaneSides"],{"before-endpoint-plane":5})
        self.assertEqual(groups[3]["outsideEndpointPlaneSides"],{"beyond-endpoint-plane":5})
        self.assertEqual(groups[3]["outsideDominantComponents"],{"lateral":5})
        self.assertEqual(sum(r["transientExitThenReturn"] for r in groups),0)
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["liveArrivalVerified"])


if __name__ == "__main__":
    unittest.main()
