"""Portable review package tests, using an invented source export."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import io

from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import content_id, IDENTITY_FIELDS
from rift_taxi.world_review_package import create_package, open_package, main
from test_world_candidate_review import fixture


class PackageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        self.source=root/"candidate.json"
        self.path=root/"package.json"
        doc=fixture()
        identity={k:doc[k] for k in IDENTITY_FIELDS}
        identity["plannerResult"]=doc["plannerResult"]
        doc["candidateId"]=content_id(identity)
        self.raw=(json.dumps(doc,indent=3)+"\n").encode()
        self.source.write_bytes(self.raw)
        self.pin=hashlib.sha256(self.raw).hexdigest()
        self.package=create_package(self.source,expected_sha256=self.pin,source_commit="c"*40)

    def save(self,doc,repin=False):
        if repin:
            doc["packageId"]=content_id({k:v for k,v in doc.items() if k!="packageId"})
        self.path.write_text(json.dumps(doc),encoding="utf-8")

    def test_round_trip_original_bytes_without_source_file(self):
        self.save(self.package)
        self.assertEqual(base64.b64decode(self.package["originalBase64"]),self.raw)
        self.source.unlink()
        result=open_package(self.path,expected_package_id=self.package["packageId"])
        self.assertTrue(result["externalPackagePinMatched"])
        self.assertEqual(result["source"]["sha256"],self.pin)
        self.assertFalse(result["productionInputAuthorized"])
        self.assertEqual(result["points"][-1]["xyz"],[4.,0.,0.])

    def test_modified_envelope_or_encoded_source_refused(self):
        for change in ("classification","extra","bytes","pin"):
            doc=deepcopy(self.package)
            if change=="classification": doc["classification"]="qualified"
            elif change=="extra": doc["review"]={"physicalQualification":True}
            elif change=="bytes": doc["originalBase64"]=base64.b64encode(b"other").decode()
            else: doc["source"]["sha256"]="0"*64
            self.save(doc,repin=True)
            with self.subTest(change=change),self.assertRaises(TraceError):
                open_package(self.path)

    def test_external_pin_detects_replaced_revision(self):
        doc=deepcopy(self.package)
        doc["source"]["commit"]="d"*40
        self.save(doc,repin=True)
        self.assertIsNone(open_package(self.path)["externalPackagePinMatched"])
        with self.assertRaisesRegex(TraceError,"external package pin"):
            open_package(self.path,expected_package_id=self.package["packageId"])

    def test_cli_refuses_overwrite(self):
        args=["create",str(self.source),"--expected-sha256",self.pin,
              "--source-commit","c"*40,"--out",str(self.path)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),0)
        original=self.path.read_bytes()
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as ctx:
            main(args)
        self.assertEqual(ctx.exception.code,2)
        self.assertEqual(self.path.read_bytes(),original)
