"""Saved synthetic journey verification, no game or native source required."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.synthetic_journey_demo import journey
from rift_taxi.synthetic_journey_audit import verify_journey, audit_saved

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"samples"/"synthetic_continuous.json"


class JourneyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace=load_trace(SOURCE)
        cls.normal=journey(cls.trace,delay_steps=2)
        cls.failed=journey(cls.trace,approach_budget=.2)

    def test_valid_modes_and_failure_remain_distinct(self):
        for mode,delay in (("baseline",0),("baseline",2),("predict-near-goal",2),
                           ("predict-near-stall",2),("zero-delay-rejoin",0)):
            with self.subTest(mode=mode,delay=delay):
                report=journey(self.trace,approach_mode=mode,delay_steps=delay)
                before=deepcopy(report)
                audit=verify_journey(report,self.trace,terminal_budget=5.)
                self.assertEqual(report,before)
                self.assertEqual(audit["finalModelSettled"],report["summary"]["finalModelSettled"])
                self.assertFalse(audit["physicalQualification"])
        audit=verify_journey(self.failed,self.trace,terminal_budget=5.)
        self.assertFalse(audit["finalModelSettled"])

    def test_drain_and_correction_phase_corruption_refused(self):
        self.assertIsNotNone(self.normal["terminalCorrection"])
        for phase,key,change in (("passiveDrain","queueDrainSeconds",.01),
                                 ("terminalCorrection","extraSeconds",.01)):
            report=deepcopy(self.normal)
            report[phase][key]+=change
            with self.subTest(phase=phase),self.assertRaises(TraceError):
                verify_journey(report,self.trace,terminal_budget=5.)
        for phase,frames in (("passiveDrain","observations"),("terminalCorrection","frames")):
            report=deepcopy(self.normal)
            report[phase][frames][0]["xyz"][0]+=1.
            with self.assertRaises(TraceError):
                verify_journey(report,self.trace,terminal_budget=5.)

    def test_failed_approach_cannot_acquire_terminal_success(self):
        report=deepcopy(self.failed)
        report["terminalCorrection"]=deepcopy(self.normal["terminalCorrection"])
        report["summary"]["finalModelSettled"]=True
        with self.assertRaises(TraceError):
            verify_journey(report,self.trace,terminal_budget=5.)

    def test_summary_alias_and_forged_mode_refused(self):
        for field,value in (("totalDistanceXZ",999.),("geometricArrival",1),
                            ("totalForwardDutyRatio",float("nan")),("status","invented")):
            report=deepcopy(self.normal)
            report["summary"][field]=value
            with self.subTest(field=field),self.assertRaises(TraceError):
                verify_journey(report,self.trace,terminal_budget=5.)
        report=deepcopy(self.normal)
        report["experimentalApproachMode"]="predict-near-stall"
        with self.assertRaises(TraceError):
            verify_journey(report,self.trace,terminal_budget=5.)

    def test_pinned_saved_report_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"journey.json"
            raw=json.dumps(self.normal,allow_nan=False).encode()
            path.write_bytes(raw)
            pin=hashlib.sha256(raw).hexdigest()
            audit=audit_saved(SOURCE,path,terminal_budget=5.,expected_sha256=pin)
            self.assertTrue(audit["expectedSHA256Matched"])
            self.assertEqual(path.read_bytes(),raw)
            with self.assertRaisesRegex(TraceError,"SHA-256 mismatch"):
                audit_saved(SOURCE,path,terminal_budget=5.,expected_sha256="0"*64)
            path.write_bytes(raw.replace(b'"gameInputSent": false',b'"gameInputSent": true, "gameInputSent": false',1))
            with self.assertRaisesRegex(TraceError,"duplicate JSON key"):
                audit_saved(SOURCE,path,terminal_budget=5.)

    def test_cli_preserves_existing_output_and_requires_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            report=root/"journey.json"
            report.write_text(json.dumps(self.normal),encoding="utf-8")
            out=root/"audit.json"
            args=[sys.executable,"-B","-m","rift_taxi.synthetic_journey_audit",
                  str(SOURCE),str(report),"--out",str(out)]
            def run(extra):
                return subprocess.run(args+extra,cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(run([]).returncode,2)
            self.assertFalse(out.exists())
            good=run(["--terminal-budget","5"])
            self.assertEqual(good.returncode,0,good.stderr)
            raw=out.read_bytes()
            self.assertEqual(json.loads(raw)["status"],"verified-offline")
            self.assertEqual(run(["--terminal-budget","5"]).returncode,2)
            self.assertEqual(out.read_bytes(),raw)
