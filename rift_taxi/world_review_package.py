"""Self-contained, read-only world-candidate review package.

Stores exact original bytes, not regenerated JSON or upstream file locators.
No cached review claims are trusted: reopening always recomputes the review.
This is not the proposed execution-ready world bundle or a Detour runtime.
"""
import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path

from .contracts import TraceError, _read_bounded, _strict_json
from .world_candidate_review import MAX_BYTES, HEX, content_id, require, review_bytes

SCHEMA = "taxi.world-review-package/1"
MAX_ENCODED = 4 * ((MAX_BYTES + 2)//3)
MAX_PACKAGE_BYTES = MAX_ENCODED + 4096


def create_package(candidate, *, expected_sha256, source_commit):
    raw = _read_bounded(Path(candidate),MAX_BYTES,"RiftWorld candidate")
    review = review_bytes(raw,expected_sha256=expected_sha256,source_commit=source_commit)
    body = {"schema":SCHEMA,"classification":"OFFLINE_REVIEW_ONLY",
            "source":review["source"],"originalBase64":base64.b64encode(raw).decode("ascii")}
    return {**body,"packageId":content_id(body)}


def open_package(path, *, expected_package_id=None):
    """Check exact envelope, digest, original byte pin and semantic review.

    An external package ID can detect replacement of the entire self-consistent
    envelope. Without it, the embedded hashes demonstrate consistency only.
    """
    raw = _read_bounded(Path(path),MAX_PACKAGE_BYTES,"world review package")
    doc = _strict_json(raw,"world review package")
    require(isinstance(doc,dict) and set(doc)=={"schema","classification","source","originalBase64","packageId"},
            "package fields mismatch")
    require(doc["schema"]==SCHEMA and doc["classification"]=="OFFLINE_REVIEW_ONLY",
            "package classification mismatch")
    body = {k:v for k,v in doc.items() if k!="packageId"}
    require(isinstance(doc["packageId"],str) and HEX.fullmatch(doc["packageId"])
            and content_id(body)==doc["packageId"],"package identity mismatch")
    if expected_package_id is not None:
        require(isinstance(expected_package_id,str) and HEX.fullmatch(expected_package_id)
                and expected_package_id==doc["packageId"],"external package pin mismatch")
    src = doc["source"]
    require(isinstance(src,dict) and set(src)=={"repository","commit","sha256"}
            and src["repository"]=="RiftWorld","invalid package source")
    encoded = doc["originalBase64"]
    require(isinstance(encoded,str) and 0<len(encoded)<=MAX_ENCODED,
            "invalid encoded source length")
    try:
        original=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise TraceError("world candidate: invalid encoded source") from exc
    require(base64.b64encode(original).decode("ascii")==encoded,"noncanonical source encoding")
    review=review_bytes(original,expected_sha256=src["sha256"],source_commit=src["commit"])
    return {**review,"packageId":doc["packageId"],
            "externalPackagePinMatched":True if expected_package_id is not None else None}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="operation",required=True)
    make=sub.add_parser("create")
    make.add_argument("candidate",type=Path)
    make.add_argument("--expected-sha256",required=True)
    make.add_argument("--source-commit",required=True)
    make.add_argument("--out",type=Path,required=True)
    check=sub.add_parser("inspect")
    check.add_argument("package",type=Path)
    check.add_argument("--expected-package-id")
    a=p.parse_args(argv)
    try:
        if a.operation=="create":
            package=create_package(a.candidate,expected_sha256=a.expected_sha256,
                                   source_commit=a.source_commit)
            encoded=json.dumps(package,sort_keys=True,allow_nan=False)+"\n"
            # Exclusive creation, no replacement of an existing package.
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
            result={"schema":SCHEMA,"packageId":package["packageId"],
                    "source":package["source"],"physicalQualification":False,
                    "productionInputAuthorized":False}
        else:
            result=open_package(a.package,expected_package_id=a.expected_package_id)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0
    except (TraceError,OSError,ValueError,RecursionError) as exc:
        p.exit(2,f"World review package refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
