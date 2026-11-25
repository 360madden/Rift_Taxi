"""Rank observed synthetic route failure patterns using matched cases.

This is descriptive analysis, not a new holdout or a control policy.
Every delay level shares the same geometry, speed, yaw limit and dt.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from .delay_factorial_audit import audit, audit_bytes


def diagnose(report):
    """Count changes from zero delay; preserve gains as well as losses.

    Group by route and use all eight actuator/timestep profiles per start.
    Failed approaches stay in the denominator, and terminal errors are
    reported only when a geometric arrival has actually occurred.
    """
    audit(report)
    groups = defaultdict(dict)
    for row in report['cases']:
        k = (row['routeId'], row['geometryCase'], row['speed'],
             row['maxYawRate'], row['dt'])
        groups[k][row['nominalDelaySeconds']] = row
    by_route = defaultdict(list)
    for k, levels in groups.items():
        by_route[k[0]].append(levels)
    routes = []
    for route, entries in sorted(by_route.items()):
        levels = []
        for delay in (.11, .33):
            a = [e[0.] for e in entries]
            b = [e[delay] for e in entries]
            outcomes = {}
            for field in ('geometricArrival', 'settledWithinTolerance', 'arrivalAndDutyTarget'):
                outcomes[field] = {
                    'baselineSuccesses': sum(r[field] for r in a),
                    'delayedSuccesses': sum(r[field] for r in b),
                    'lost': sum(x[field] and not y[field] for x, y in zip(a, b)),
                    'gained': sum(not x[field] and y[field] for x, y in zip(a, b)),
                }
            # Overshoot/settling loss is distinguished from approach failure.
            levels.append({'delaySeconds': delay, 'matchedPairs': len(entries),
                           'outcomes': outcomes,
                           'arrivedButUnsettled': sum(r['geometricArrival'] and not r['settledWithinTolerance'] for r in b),
                           'maxSettledErrorXZ': max((r['settledErrorXZ'] for r in b if r['geometricArrival']), default=None)})
        routes.append({'routeId': route, 'levels': levels})
    # Deterministic ordering puts the largest observed arrival loss first.
    # These are development priorities only; no extrapolation to physical play.
    routes.sort(key=lambda r: (-r['levels'][1]['outcomes']['geometricArrival']['lost'],
                               -r['levels'][1]['outcomes']['settledWithinTolerance']['lost'], r['routeId']))
    return {'schema': 'taxi.synthetic-delay-diagnostics/1', 'matchedStarts': len(groups),
            'routes': routes, 'physicalQualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        raw = args.report.read_bytes()
        audit_bytes(raw, args.sha256)
        print(json.dumps(diagnose(json.loads(raw)), sort_keys=True, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        parser.exit(2, f'Diagnostics failed: {exc}\n')


if __name__ == '__main__':
    main()
