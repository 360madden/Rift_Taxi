"""Source-hashed offline kinematics analysis of one physical W-only receipt.

This module NEVER reads the game or sends input. It compares the native
actor-matrix planar angle with the movement bearing observed in the SAME
source-owned physical forward probe. Neither a tiny residual nor an OS key
receipt qualifies actor heading or passive native position freshness.
"""
from __future__ import annotations

import hashlib
import json
import math
import ntpath
from pathlib import Path
import re

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_OWNER = re.compile(r"[1-9][0-9]*\Z")
_MAX_BYTES = 1_000_000


class ForwardBearingError(ValueError):
    """Source cannot support a trustworthy candidate-only motion comparison."""


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForwardBearingError(f"{field} must be numeric")
    try:
        n = float(value)
    except (OverflowError, ValueError) as exc:
        raise ForwardBearingError(f"{field} is not representable") from exc
    if not math.isfinite(n):
        raise ForwardBearingError(f"{field} must be finite")
    return n


def _wrap(degrees: float) -> float:
    return (degrees + 180.0) % 360.0 - 180.0


def _read_pinned(path: str | Path, expected_sha256: str, label: str) -> tuple[bytes, str]:
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ForwardBearingError(f"{label} expected SHA-256 must be 64 hex characters")
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0 or p.stat().st_size > _MAX_BYTES:
        raise ForwardBearingError(f"{label} missing/empty/oversized")
    raw = p.read_bytes()
    if not raw or len(raw) > _MAX_BYTES:
        raise ForwardBearingError(f"{label} missing/oversized")
    sha = hashlib.sha256(raw).hexdigest()
    if sha != expected_sha256.lower():
        raise ForwardBearingError(f"{label} original SHA-256 mismatch")
    return raw, p.name


def _parse_json(raw: bytes, label: str) -> dict:
    try:
        doc = json.loads(raw.decode("utf8"),
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ForwardBearingError(f"{label}: nonfinite JSON refused")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ForwardBearingError(f"{label}: invalid UTF-8 JSON") from exc
    if not isinstance(doc, dict):
        raise ForwardBearingError(f"{label} root must be an object")
    return doc


def _source(doc: dict) -> dict:
    if (doc.get("schema") != "taxi.m1-bounded-forward-probe/1"
            or doc.get("status") != "calibration-candidate-only"
            or doc.get("probeKind") != "forward"
            or doc.get("dryRun") is not False):
        raise ForwardBearingError("real physical W-only candidate receipt required")
    source = doc.get("source")
    if not isinstance(source, dict):
        raise ForwardBearingError("physical report source absent")
    if (not isinstance(source.get("host"), str)
            or not source["host"].strip()
            or type(source.get("pid")) is not int or source["pid"] <= 0
            or type(source.get("startUtcTicks")) is not int
            or source["startUtcTicks"] <= 0
            or type(source.get("windowHandle")) is not int
            or source["windowHandle"] <= 0
            or not isinstance(source.get("executablePath"), str)
            or not ntpath.isabs(source["executablePath"])
            or not isinstance(source.get("onDiskExecutableSha256"), str)
            or not _SHA.fullmatch(source["onDiskExecutableSha256"])
            or not isinstance(source.get("ownerKeyDecimalCandidate"), str)
            or not _OWNER.fullmatch(source["ownerKeyDecimalCandidate"])
            or not isinstance(source.get("reviewedSceneImageSha256"), str)
            or not _SHA.fullmatch(source["reviewedSceneImageSha256"])):
        raise ForwardBearingError("incomplete build/process/actor/screenshot identity")
    return source


def _candidate(value: object, source: dict, label: str) -> dict:
    if not isinstance(value, dict):
        raise ForwardBearingError(f"{label} candidate missing")
    if (value.get("ownerKeyDecimal") != source["ownerKeyDecimalCandidate"]
            or value.get("actorHeadingVerified") is not False
            or value.get("passivePositionFreshnessVerified") is not False):
        raise ForwardBearingError(f"{label}: candidate owner or qualification mismatch")
    xyz = value.get("xyzCandidate")
    if not isinstance(xyz, list) or len(xyz) != 3:
        raise ForwardBearingError(f"{label} XYZ must contain three values")
    xyz = tuple(_number(v, f"{label} XYZ") for v in xyz)
    system = _number(value.get("playerSystemBearingDegreesCandidate"),
                     f"{label} player-system scalar")
    matrix = _number(value.get("actorMatrixPlanarAngleDegreesCandidate"),
                     f"{label} actor-matrix angle")
    t = _number(value.get("observedMonotonicSeconds"), f"{label} sample clock")
    if t < 0 or not all(-180 <= a <= 180 for a in (system, matrix)):
        raise ForwardBearingError(f"{label}: wrapped yaw/time invalid")
    return {"xyz": xyz, "scalar": system, "matrix": matrix, "clock": t}


def _check_action(doc: dict, before: dict, after: dict, settled: dict) -> tuple[float, float]:
    action = doc.get("action")
    if not isinstance(action, dict):
        raise ForwardBearingError("forward action receipt missing")
    held = action.get("sampledDuringHeldKey")
    released = action.get("sampledAfterKeyUp")
    if (action.get("requestedKey") != "W"
            or type(action.get("requestedHoldMilliseconds")) is not int
            or not 60 <= action["requestedHoldMilliseconds"] <= 160
            or action.get("downAcceptedBySender") is not True
            or action.get("upAcceptedBySender") is not True
            or action.get("osKeyDownAccepted") is not True
            or action.get("osKeyUpAccepted") is not True
            or action.get("inputInjectedByTaxi") is not True
            or action.get("externalLeaseClearObserved") is not True
            or action.get("gameInputConsumptionVerified") is not False
            or action.get("physicalKeyReleaseConsumedByGameVerified") is not False
            or held != {"W": True, "A": False, "D": False}
            or released != {"W": False, "A": False, "D": False}):
        raise ForwardBearingError("forward physical input/release fields unqualified")
    down = _number(action.get("keyDownAtMonotonicSeconds"), "W DOWN clock")
    up = _number(action.get("keyUpAtMonotonicSeconds"), "W UP clock")
    if (not 0 <= before["clock"] < down < up < after["clock"] < settled["clock"]
            or not .04 <= up - down <= .35):
        raise ForwardBearingError("native/action timeline invalid or duration unbounded")
    return down, up


def _validate_delta(doc: dict, before: dict, after: dict, settled: dict) -> tuple[float, float, float]:
    changes = doc.get("candidateChanges")
    if not isinstance(changes, dict):
        raise ForwardBearingError("candidate change fields missing")
    if (changes.get("bodyHeadingQualified") is not False
            or changes.get("passiveXYZFreshnessQualified") is not False
            or changes.get("gameMotionIndependentlyVerified") is not False
            or changes.get("nativeXYZChanged") is not True):
        raise ForwardBearingError("motion change accidentally promotes unverified source")
    delta = tuple(a-b for a,b in zip(after["xyz"], before["xyz"]))
    settle_delta = tuple(a-b for a,b in zip(settled["xyz"], before["xyz"]))
    for label, actual, claimed in (
        ("deltaXYZ", delta, changes.get("deltaXYZ")),
        ("settledDeltaXYZCandidate", settle_delta, changes.get("settledDeltaXYZCandidate")),
    ):
        if (not isinstance(claimed, list) or len(claimed) != 3
                or any(abs(v - _number(c, label)) > 0.000001
                       for v,c in zip(actual, claimed))):
            raise ForwardBearingError(f"{label} contradicts original XYZ")
    distance = math.hypot(delta[0], delta[2])
    if (not math.isfinite(distance) or distance < 0.10
            or abs(_number(changes.get("planarDistanceXZCandidate"),
                           "reported distance") - distance) > 0.000001):
        raise ForwardBearingError("measured XZ displacement missing/noisy/inconsistent")
    scalar_change = _wrap(after["scalar"] - before["scalar"])
    matrix_change = _wrap(after["matrix"] - before["matrix"])
    if (abs(_wrap(_number(changes.get("playerSystemYawDeltaDegrees"), "scalar delta")
                  - scalar_change)) > 0.00001
            or abs(_wrap(_number(changes.get("actorMatrixAngleDeltaDegrees"), "matrix delta")
                         - matrix_change)) > 0.00001
            or changes.get("nativeYawChanged") != (before["scalar"] != after["scalar"])):
        raise ForwardBearingError("candidate heading delta contradicts samples")
    return delta


def _audit(raw: bytes, source: dict, down: float, up: float) -> dict:
    try:
        lines = raw.decode("utf8").splitlines()
        if not 6 <= len(lines) <= 32:
            raise ForwardBearingError("release audit incomplete or unbounded")
        events = [_parse_json(line.encode("utf8"), "release audit event") for line in lines]
    except UnicodeError as exc:
        raise ForwardBearingError("release audit not UTF-8") from exc
    if (events[0].get("event") != "ready"
            or events[0].get("dryRun") is not False
            or events[0].get("pid") != source["pid"]):
        raise ForwardBearingError("release audit wrong physical target or dry-run")
    timeline = []
    prior = None
    for event in events:
        t = _number(event.get("monotonicSeconds"), "release event clock")
        if t < 0 or prior is not None and t <= prior:
            raise ForwardBearingError("release audit clock not monotonic")
        prior = t
        timeline.append(t)
        if event.get("event") in ("worker-init-or-runtime-failed",
                                   "release-not-sent-identity-unavailable",
                                   "native-key-up-attempt",
                                   "bounded-final-release-retry"):
            raise ForwardBearingError("nonordinary release must be analyzed separately")
    commands = [row for row in events if row.get("event") == "command"]
    if [(x.get("action"), x.get("key")) for x in commands] != [
        ("reserve", "W"), ("renew", None), ("clear", "W"), ("stop", None)
    ]:
        raise ForwardBearingError("unexpected release lease command sequence")
    reserve, renew, clear, stop = commands
    for row, expected_held, expected_stopped in (
        (reserve, ["W"], False), (renew, ["W"], False),
        (clear, [], False), (stop, [], True),
    ):
        state = row.get("status")
        if (not isinstance(state, dict) or state.get("possibleHeld") != expected_held
                or state.get("stopped") is not expected_stopped
                or state.get("gameResponseVerified") is not False):
            raise ForwardBearingError("release child state not safe/consistent")
    if (not events[0]["monotonicSeconds"] < reserve["monotonicSeconds"]
            < renew["monotonicSeconds"] <= down < up
            <= clear["monotonicSeconds"] < stop["monotonicSeconds"]
            <= events[-1]["monotonicSeconds"]
            or events[-1].get("event") != "stop"
            or events[-1].get("possibleHeld") != []
            or events[-1].get("stopped") is not True):
        raise ForwardBearingError("release child did not cover the OS W edge interval")
    return {
        "childReadyBeforeReservation": True,
        "childReservedBeforeDown": True,
        "childRenewedBeforeDown": True,
        "childClearedAfterUp": True,
        "childStoppedWithNoReservedKeys": True,
        "childEmergencyReleaseWasNeeded": False,
        "gameConsumedReleaseVerified": False,
    }


def analyze_forward_bearing(*, report: str | Path, report_sha256: str,
                            release_audit: str | Path,
                            release_audit_sha256: str) -> dict:
    """Validate physical receipts and compute *candidate-only* XZ heading.

    RIFT uses XYZ with Y up. The matrix descriptor reports +atan2(m[6],m[0]);
    a candidate aligned forward vector is (-sin(theta), 0, cos(theta)).
    Travel angle is thus atan2(-deltaX, deltaZ), *not* atan2(deltaX,deltaZ).
    """
    raw, report_name = _read_pinned(report, report_sha256, "physical forward report")
    audit_bytes, audit_name = _read_pinned(release_audit, release_audit_sha256,
                                           "release audit")
    if Path(report).resolve() == Path(release_audit).resolve():
        raise ForwardBearingError("distinct original input files required")
    doc = _parse_json(raw, "physical forward report")
    source = _source(doc)
    before = _candidate(doc.get("candidateBefore"), source, "before")
    after = _candidate(doc.get("candidateAfter"), source, "after")
    settled = _candidate(doc.get("candidateSettledAfterRelease"), source, "settled")
    down, up = _check_action(doc, before, after, settled)
    dx, dy, dz = _validate_delta(doc, before, after, settled)
    release = _audit(audit_bytes, source, down, up)
    distance = math.hypot(dx, dz)
    heading = _wrap(math.degrees(math.atan2(-dx, dz)))
    by_matrix = [ _wrap(heading - candidate["matrix"])
                  for candidate in (before, after, settled)]
    by_scalar = [ _wrap(heading - (-candidate["scalar"]))
                  for candidate in (before, after, settled)]
    matrix_scalar = [ _wrap(candidate["matrix"] + candidate["scalar"])
                      for candidate in (before, after, settled)]
    if not all(math.isfinite(x) for x in [heading, *by_matrix, *by_scalar]):
        raise ForwardBearingError("forward angle arithmetic overflow")
    return {
        "schema": "taxi.m1-forward-bearing-comparison/1",
        "status": "offline-candidate-heading-alignment-only",
        "sources": {
            "physicalForward": {"name": report_name, "sha256": report_sha256.lower()},
            "externalReleaseAudit": {"name": audit_name, "sha256": release_audit_sha256.lower()},
            "host": source["host"], "pid": source["pid"],
            "startUtcTicks": source["startUtcTicks"],
            "onDiskExecutableSha256": source["onDiskExecutableSha256"].lower(),
            "windowHandle": source["windowHandle"],
            "ownerKeyDecimalCandidate": source["ownerKeyDecimalCandidate"],
            "reviewedSceneImageSha256": source["reviewedSceneImageSha256"].lower(),
        },
        "observed": {
            "nativeDeltaXYZCandidate": [dx,dy,dz],
            "nativeHorizontalDistanceCandidate": distance,
            "nativeTravelAngleDegreesPositiveTowardNegativeX": heading,
            "requestedHoldMilliseconds": doc["action"]["requestedHoldMilliseconds"],
            "osDownToUpMilliseconds": (up-down)*1000,
            "candidateBeforeToDownMilliseconds": (down-before["clock"])*1000,
            "upToCandidateAfterMilliseconds": (after["clock"]-up)*1000,
            "afterToSettledMilliseconds": (settled["clock"]-after["clock"])*1000,
            "settledXZEqualsAfter": settled["xyz"][::2] == after["xyz"][::2],
        },
        "headingCandidates": {
            "actorMatrixBeforeDegrees": before["matrix"],
            "actorMatrixAfterDegrees": after["matrix"],
            "playerSystemScalarBeforeDegrees": before["scalar"],
            "playerSystemScalarAfterDegrees": after["scalar"],
            "travelMinusActorMatrixDegreesByPhase": by_matrix,
            "travelMinusNegatedScalarDegreesByPhase": by_scalar,
            "actorMatrixPlusScalarDegreesByPhase": matrix_scalar,
        },
        "releaseLedger": release,
        "qualification": {
            "sameActorProcessAndEpoch": True,
            "originalEvidenceSHA256Verified": True,
            "physicalOSKeyEdgesVerified": True,
            "actorHeadingVerified": False,
            "passiveNativeXYZFreshnessVerified": False,
            "gameConsumedWReleaseVerified": False,
            "calibratedSteadySpeedVerified": False,
            "continuousNavigationAuthorized": False,
        },
        "limitations": [
            "Native XYZ and matrix/scalar readings are candidate data from the same game process.",
            "Only one real short forward pulse at one heading has been compared.",
            "Small angular residual cannot by itself authenticate actor body orientation.",
            "Native before/after samples do not align exactly to W DOWN/UP; speed is not calibrated.",
            "The installed addon may refresh native cached XYZ via Inspect.Unit.Detail.",
            "External child lease and OS UP are not independent game-consumed release proof.",
            "No RIFT process, game memory, input, or sibling repository is accessed by this analyzer.",
        ],
    }


def compare_two_forward_bearings(
    *, first_report: str | Path, first_report_sha256: str,
    first_release_audit: str | Path, first_release_audit_sha256: str,
    second_report: str | Path, second_report_sha256: str,
    second_release_audit: str | Path, second_release_audit_sha256: str,
) -> dict:
    """Compare TWO independently source-hashed physical W pulses at distinct angles.

    This is an offline candidate-consistency check. Neither a pair of aligned
    native vectors nor two child lease ledgers establish trusted live yaw,
    a passive position writer, or crash-safe/game-consumed STOP.
    """
    first = analyze_forward_bearing(
        report=first_report, report_sha256=first_report_sha256,
        release_audit=first_release_audit,
        release_audit_sha256=first_release_audit_sha256,
    )
    second = analyze_forward_bearing(
        report=second_report, report_sha256=second_report_sha256,
        release_audit=second_release_audit,
        release_audit_sha256=second_release_audit_sha256,
    )
    if (Path(first_report).resolve() == Path(second_report).resolve()
            or first_report_sha256.lower() == second_report_sha256.lower()
            or Path(first_release_audit).resolve() == Path(second_release_audit).resolve()):
        raise ForwardBearingError("two distinct original physical pulse receipts required")
    a_source, b_source = first["sources"], second["sources"]
    identity_fields = (
        "host", "pid", "startUtcTicks", "onDiskExecutableSha256",
        "windowHandle", "ownerKeyDecimalCandidate",
    )
    if any(
        (str(a_source[key]).casefold() != str(b_source[key]).casefold())
        for key in identity_fields
    ):
        raise ForwardBearingError("physical W pulses belong to different process/actor epochs")
    a_doc = _parse_json(_read_pinned(first_report, first_report_sha256,
                                     "first original physical report")[0], "first")
    b_doc = _parse_json(_read_pinned(second_report, second_report_sha256,
                                     "second original physical report")[0], "second")
    if (ntpath.normcase(a_doc["source"]["executablePath"])
            != ntpath.normcase(b_doc["source"]["executablePath"])):
        raise ForwardBearingError("physical executable path changed between W pulses")
    first_settled = _number(
        a_doc["candidateSettledAfterRelease"]["observedMonotonicSeconds"],
        "first settled timestamp",
    )
    second_before = _number(
        b_doc["candidateBefore"]["observedMonotonicSeconds"],
        "second before timestamp",
    )
    if not first_settled < second_before:
        raise ForwardBearingError("physical W pulses overlap or reverse sample order")

    fa, fb = first["headingCandidates"], second["headingCandidates"]
    oa, ob = first["observed"], second["observed"]
    first_angle = oa["nativeTravelAngleDegreesPositiveTowardNegativeX"]
    second_angle = ob["nativeTravelAngleDegreesPositiveTowardNegativeX"]
    angle_separation = abs(_wrap(second_angle - first_angle))
    matrix_separation = abs(_wrap(
        fb["actorMatrixBeforeDegrees"] - fa["actorMatrixBeforeDegrees"]
    ))
    residuals = [
        abs(fa["travelMinusActorMatrixDegreesByPhase"][0]),
        abs(fb["travelMinusActorMatrixDegreesByPhase"][0]),
    ]
    # One degree is an exploratory *consistency threshold*, never permission
    # to feed the native matrix as a verified actor body yaw.
    diverse = angle_separation >= 15.0
    aligned = max(residuals) <= 1.0
    return {
        "schema": "taxi.m1-two-heading-forward-comparison/1",
        "status": (
            "two-distinct-heading-native-alignment-candidate"
            if diverse and aligned else "insufficient-or-inconsistent-heading-evidence"
        ),
        "source": {
            "host": a_source["host"],
            "pid": a_source["pid"],
            "startUtcTicks": a_source["startUtcTicks"],
            "windowHandle": a_source["windowHandle"],
            "onDiskExecutableSha256": a_source["onDiskExecutableSha256"],
            "ownerKeyDecimalCandidate": a_source["ownerKeyDecimalCandidate"],
            "firstPhysicalReport": a_source["physicalForward"],
            "firstReleaseAudit": a_source["externalReleaseAudit"],
            "secondPhysicalReport": b_source["physicalForward"],
            "secondReleaseAudit": b_source["externalReleaseAudit"],
        },
        "observed": {
            "firstNativeTravelAngleDegrees": first_angle,
            "secondNativeTravelAngleDegrees": second_angle,
            "firstActorMatrixAngleDegrees": fa["actorMatrixBeforeDegrees"],
            "secondActorMatrixAngleDegrees": fb["actorMatrixBeforeDegrees"],
            "travelHeadingSeparationDegrees": angle_separation,
            "matrixHeadingSeparationDegrees": matrix_separation,
            "firstMatrixResidualDegrees": fa["travelMinusActorMatrixDegreesByPhase"][0],
            "secondMatrixResidualDegrees": fb["travelMinusActorMatrixDegreesByPhase"][0],
            "maxAbsoluteMatrixResidualDegrees": max(residuals),
            "firstPreWScalarResidualDegrees":
                fa["travelMinusNegatedScalarDegreesByPhase"][0],
            "secondPreWScalarResidualDegrees":
                fb["travelMinusNegatedScalarDegreesByPhase"][0],
            "firstPostWScalarResidualDegrees":
                fa["travelMinusNegatedScalarDegreesByPhase"][1],
            "secondPostWScalarResidualDegrees":
                fb["travelMinusNegatedScalarDegreesByPhase"][1],
            "firstXZDistanceCandidate": oa["nativeHorizontalDistanceCandidate"],
            "secondXZDistanceCandidate": ob["nativeHorizontalDistanceCandidate"],
            "sameEpochMonotonicOrderingVerified": True,
        },
        "evidence": {
            "twoDistinctSourceHashedPhysicalWReportsVerified": True,
            "twoExternalNormalReleaseLedgersVerified": True,
            "sameWindowsProcessActorAndBuild": True,
            "atLeast15DegreesObservedTravelVariation": diverse,
            "bothActorMatrixResidualsUnder1Degree": aligned,
        },
        "qualification": {
            "actorBodyYawVerified": False,
            "passiveNativeXYZFreshnessVerified": False,
            "gameConsumedInputReleaseAfterFaultVerified": False,
            "steadySpeedCalibrated": False,
            "productionNavigationArmed": False,
            "M1Complete": False,
        },
        "limitations": [
            "Same-process native XYZ and actor-matrix fields share producer/caching uncertainty.",
            "Observed XZ displacement is between two unsynchronized native samples.",
            "Two headings support kinematic consistency, not independent body yaw authority.",
            "An intervening turn is not itself established by the two W receipts alone.",
            "The 1-degree/15-degree cutoffs are exploratory heuristics, not safety gates.",
            "Normal Windows key-up/child CLEAR does not establish game-consumed release after crash.",
            "This tool is entirely offline and never reads or controls RIFT.",
        ],
    }
