"""Exercise an installed Taxi wheel with invented world-review packages.

Invoke from a fresh wheel environment with Python -I. All geometry is
literal, fictional test data; this script cannot discover local captures
or connect to a game. Build the catalog through the installed command,
exercise the actual Tk launcher/viewer workflow, and retain a bounded
synthetic-only receipt. No screenshot or physical qualification is implied.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import sysconfig

from rift_taxi.world_candidate_review import IDENTITY_FIELDS, content_id
from rift_taxi.world_review_package import create_package
from rift_taxi.world_catalog_build import PLAN_SCHEMA


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(data,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.write("\n")


def generate_plan(root):
    """Generate two fictional routes; no source data is read from disk.

    The main route includes uniquely projected interior vertices for mouse
    selection, varied heights, and a separate destination for search tests.
    Each package is independently pinned by the existing production builder.
    """
    inventory=[]
    for route,points in (
        ("invented-main",[[0,0,0],[4,1,0],[8,2,3],[12,1,3],[16,0,0]]),
        ("invented-side",[[16,0,0],[20,1,4],[24,0,4]]),
    ):
        ends={"requestedStartXYZ":points[0],"requestedGoalXYZ":points[-1],
              "snappedStartXYZ":points[0],"snappedGoalXYZ":points[-1]}
        flags=[1]+[0]*(len(points)-2)+[2]
        doc={"schema":"riftworld.candidate-path/1","patchId":"a"*64,
             "status":"complete","world":{"sourceWorld":"synthetic-ci","authority":"source-map-name"},
             "coordinates":{"axisOrder":["x","y","z"],"upAxis":"y","frameId":"invented-ci",
                            "units":"test","transformToRr2Native":{"kind":"unknown"}},
             "query":ends.copy(),"points":[{"id":str(i),"xyz":p,"flags":f}
                 for i,(p,f) in enumerate(zip(points,flags,strict=True))],
             "planner":{"buildId":"b"*64},
             "evidence":{"geometry":"unknown","walkability":"estimated","traversal":"unverified"},
             "sourceRefs":{"patchDescriptor":"not-accessed.json"},
             "plannerResult":{"status":"complete","cacheKey":"b"*64,**ends,
                              "waypoints":[{"pos":p,"flags":f} for p,f in zip(points,flags,strict=True)]}}
        identity={key:doc[key] for key in IDENTITY_FIELDS}
        identity["plannerResult"]=doc["plannerResult"]
        doc["candidateId"]=content_id(identity)
        candidate=root/(route+"-candidate.json")
        write_json(candidate,doc)
        package=create_package(candidate,expected_sha256=digest(candidate),source_commit="c"*40)
        package_path=root/(route+".json")
        write_json(package_path,package)
        inventory.append({"routeId":route,"destinationId":route+"-goal",
                          "packageFile":package_path.name,"packageId":package["packageId"]})
    plan=root/"plan.json"
    write_json(plan,{"schema":PLAN_SCHEMA,"entries":inventory})
    return plan


def installed_modules():
    """Fail if a source checkout or user-site module substitutes for the wheel."""
    require_isolated = bool(sys.flags.isolated)
    if not require_isolated:
        raise RuntimeError("invoke installed smoke with Python -I")
    root=Path(sysconfig.get_paths()["purelib"]).resolve()
    names=("app","local_taxi","local_taxi_gui","local_journey_viewer",
           "world_catalog_build","world_route_graph","world_route_viewer")
    for name in names:
        module=importlib.import_module("rift_taxi."+name)
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise RuntimeError("not an installed module: "+name)
    return list(names)


def run(output, *, wheel, source_commit):
    """Run actual installed catalog CLI and GUI smoke under bounded subprocesses."""
    names=installed_modules()
    if not re.fullmatch(r"[0-9a-f]{40}",source_commit):
        raise ValueError("expected exact checkout Git SHA")
    wheel=Path(wheel).resolve(strict=True)
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    fixtures=output/"invented-fixtures"
    fixtures.mkdir()
    plan=generate_plan(fixtures)
    catalog=fixtures/"catalog.json"
    subprocess.run([sys.executable,"-I","-B","-m","rift_taxi.world_catalog_build",str(plan),
                    "--expected-plan-sha256",digest(plan),"--out",str(catalog)],
                   cwd=output,check=True,timeout=30)
    pin=digest(catalog)
    report=output/"widget-smoke.json"
    smoke=Path(__file__).resolve().with_name("desktop_viewer_smoke.py")
    subprocess.run([sys.executable,"-I","-B",str(smoke),"--catalog",str(catalog),
                    "--catalog-sha256",pin,"--anchor-route","invented-main","--out",str(report)],
                   cwd=output,check=True,timeout=60)
    result=json.loads(report.read_text(encoding="utf-8"))
    # Require positive evidence; a skipped GUI or incomplete receipt is
    # a failing gate, not a pass. Keep the hosted context explicit.
    if not (result["launcherDemo"]["mapped"] and result["launcherWorld"]["mapped"]
            and result["launcherWorld"]["wrongPinRefusalChecked"]
            and result["launcherWorld"]["staleInputRefusalChecked"]
            and result["launcherWorld"]["explicitAnchorChecked"]
            and result["synthetic"]["modelJourneyReplayChecked"]
            and result["importedWorld"]["searchAndAutomaticReplanChecked"]
            and result["importedWorld"]["mapSourceSelectionChecked"]
            and result["importedWorld"]["positionReviewChecked"]
            and not any(result[key]["callbackErrors"] for key in
                        ("launcherDemo","launcherWorld","synthetic","importedWorld"))
            and result["physicalQualification"] is False and result["gameInputSent"] is False):
        raise RuntimeError("installed desktop receipt incomplete")
    receipt={"schema":"taxi.installed-desktop-ci/1","classification":"SYNTHETIC_CI_ONLY",
             "sourceCommit":source_commit,"wheel":wheel.name,"wheelSHA256":digest(wheel),
             "installedModules":names,"catalogSHA256":pin,"widgetReceiptSHA256":digest(report),
             "desktopSmokePassed":True,"physicalQualification":False,"gameInputSent":False}
    write_json(output/"summary.json",receipt)
    print(json.dumps(receipt,indent=2))
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--wheel",type=Path,required=True)
    parser.add_argument("--source-commit",required=True)
    a=parser.parse_args(argv)
    run(a.out_dir,wheel=a.wheel,source_commit=a.source_commit)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
