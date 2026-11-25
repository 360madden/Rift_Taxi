"""Independent synthetic archive fixtures; no simulator or game dependency."""
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from itertools import product
import json
import unittest
from rift_taxi.delay_factorial_audit import audit, audit_bytes, read_report, MAX_REPORT_BYTES


def fixture():
    # Low speed arrives; high speed times out. This makes the expected
    # matched speed losses and other-factor unchanged counts analytic.
    factors = list(product((2.2, 3.4), (65., 140.), (.055, .11), (0., .11, .33)))
    rows = []
    for g, (s, y, dt, d) in product(range(1, 37), factors):
        ok = s == 2.2
        rows.append(dict(geometryCase=g, routeId='route', scenarioSHA256=hashlib.sha256(
            repr((g,s,y,dt)).encode()).hexdigest(), speed=s,maxYawRate=y,dt=dt,
            nominalDelaySeconds=d,delaySteps=round(d/dt),status='arrived' if ok else 'timeout',
            geometricArrival=ok,settledWithinTolerance=ok,arrivalAndDutyTarget=ok,
            forwardDutyRatio=1.,settledErrorXZ=.1 if ok else None,postArrivalDistanceXZ=0. if ok else None))
    def counts(n, a):
        return dict(runs=n,geometricArrivals=a,settledWithinTolerance=a,arrivalAndDutyTarget=a,
                    settledOutside=0,statusCounts={k:v for k,v in [('arrived',a),('timeout',n-a)] if v})
    return dict(schema='taxi.synthetic-delay-factorial/1',classification='SYNTHETIC_CLOSED_LOOP_ONLY',
        speedPolicy='turn-limited-ordered',gameInputSent=False,liveArrivalVerified=False,
        geometryCount=36,profileCount=24,simulationCount=864,
        geometry=[dict(geometryCase=g,routeId='route') for g in range(1,37)],cases=rows,
        profiles=[dict(speed=s,maxYawRate=y,dt=dt,nominalDelaySeconds=d,**counts(36,36 if s==2.2 else 0)) for s,y,dt,d in factors],
        byDelay=[dict(nominalDelaySeconds=d,**counts(288,144)) for d in (0.,.11,.33)],
        matchedEffects=[dict(factor=f,low=lo,high=hi,nominalDelaySeconds=d,pairs=144,
            outcomes={n:dict(gained=0,lost=144 if f=='speed' else 0,both=0 if f=='speed' else 72,neither=0 if f=='speed' else 72)
            for n in ('geometricArrival','settledWithinTolerance','arrivalAndDutyTarget')})
            for f,lo,hi in [('speed',2.2,3.4),('maxYawRate',65.,140.),('dt',.055,.11)] for d in (0.,.11,.33)])


class AuditTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(audit(fixture())['cases'],864)

    def test_corruptions(self):
        for field, mutate in [
            ('missing', lambda r:r['cases'].pop()),
            ('duplicate', lambda r:r['cases'].__setitem__(0,r['cases'][1])),
            ('hash', lambda r:r['cases'][0].__setitem__('scenarioSHA256','0'*64)),
            ('delay', lambda r:r['cases'][0].__setitem__('delaySteps',1)),
            ('settling', lambda r:r['cases'][0].__setitem__('settledErrorXZ',1.)),
            ('duty', lambda r:r['cases'][0].__setitem__('forwardDutyRatio',.2)),
            ('summary', lambda r:r['profiles'][0].__setitem__('runs',35)),
            ('effect', lambda r:r['matchedEffects'][0]['outcomes']['geometricArrival'].__setitem__('lost',143)),
            ('authority', lambda r:r.__setitem__('liveArrivalVerified',True)),
        ]:
            with self.subTest(field=field):
                r=fixture(); mutate(r)
                with self.assertRaises(ValueError): audit(r)

    def test_archive_digest(self):
        raw=json.dumps(fixture()).encode(); digest=hashlib.sha256(raw).hexdigest()
        self.assertEqual(audit_bytes(raw,digest)['profiles'],24)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            audit_bytes(raw+b' ',digest)

    def test_ambiguous_json_rejected_even_with_matching_digest(self):
        """Byte integrity alone cannot establish unambiguous JSON semantics."""
        raw = json.dumps(fixture()).encode()
        for extra in (b'"schema":"ignored",', b'"extra":NaN,', b'"extra":1e999,'):
            candidate = b'{' + extra + raw[1:]
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                audit_bytes(candidate, hashlib.sha256(candidate).hexdigest())

    def test_bool_does_not_masquerade_as_number(self):
        for field, value in (("geometryCase", True), ("nominalDelaySeconds", False),
                             ("forwardDutyRatio", True), ("postArrivalDistanceXZ", False)):
            r = fixture()
            r["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(r)

    def test_size_limit_for_bytes_and_file(self):
        """Oversized input must fail before hashing or JSON decoding."""
        raw = b" " * (MAX_REPORT_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "size limit"):
            audit_bytes(raw, hashlib.sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "oversize.json"
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "size limit"):
                read_report(path)

    def test_non_object_and_deep_json(self):
        for raw in (b"[]", b"null", b"[" * 2000 + b"]" * 2000):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                audit_bytes(raw, hashlib.sha256(raw).hexdigest())

    def test_cli_errors_and_success(self):
        """Both command-line consumers share the same admission behavior."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            raw = json.dumps(fixture()).encode()
            digest = hashlib.sha256(raw).hexdigest()
            for module in ("delay_factorial_audit", "delay_factorial_diagnostics"):
                base = [sys.executable, "-B", "-m", "rift_taxi." + module, str(path), "--sha256"]
                for existing, supplied, expected in ((False, digest, 2), (True, "0"*64, 2), (True, digest, 0)):
                    if existing:
                        path.write_bytes(raw)
                    else:
                        path.unlink(missing_ok=True)
                    result = subprocess.run(base + [supplied], capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if expected == 0:
                        self.assertFalse(json.loads(result.stdout)["physicalQualification"])
                    else:
                        self.assertIn("failed:", result.stderr)
                        self.assertEqual(result.stdout, "")
