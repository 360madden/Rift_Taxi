"""Compare two complete, source-hashed, native one-shot candidate reports offline.

No live process access or game input. Same Windows process/build/HWND/player
continuity is mandatory. A pair of changed caches is NOT proof of passive
freshness, body yaw, input consumption, or physical movement.
"""
from __future__ import annotations

import math
import ntpath
from pathlib import Path
import re

from .facing_signature import _read_json, FacingSignatureError
from .native_burst import (
    _validate_sample, _validate_matrix_evidence, _validate_refresh_guard,
    _number,
)
from .native_capture import CandidateCaptureRefused
from .native_memory import ProcessPin

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


class NativePairError(ValueError):
    """The selected native receipts cannot support a same-session comparison."""


def _wrap(degrees: float) -> float:
    return ((degrees + 180.) % 360.) - 180.


def _validate_actor_translation(doc: dict) -> dict | None:
    evidence = doc.get("evidence")
    payload = doc.get("actorTranslationEvidence")
    if not isinstance(evidence, dict):
        raise NativePairError("capture evidence object missing")
    flag = evidence.get("actorTranslationEvidenceRequested", False)
    if type(flag) is not bool:
        raise NativePairError("actor translation request flag invalid")
    if not flag:
        if payload is not None:
            raise NativePairError("unsolicited actor translation data")
        return None
    if not isinstance(payload, dict):
        raise NativePairError("requested actor translation evidence missing")
    if (payload.get("independentlyFresh") is not False
            or payload.get("authoritativePlayerPosition") is not False):
        raise NativePairError("actor translation cannot be promoted to live pose")

    def xyz(field: str, optional: bool = False) -> tuple[float, float, float] | None:
        vals = payload.get(field)
        if vals is None and optional:
            return None
        if not isinstance(vals, list) or len(vals) != 3:
            raise NativePairError(f"{field} must contain 3 float values")
        try:
            out = tuple(_number(value, field) for value in vals)
        except (CandidateCaptureRefused, OverflowError, ValueError) as error:
            raise NativePairError(f"{field} has invalid data") from error
        return out

    secondary = xyz("positionSecondaryXyz")
    actor = xyz("actorStoredWorldTranslationCandidate")
    first = xyz("offsetAt04F8")
    second = xyz("offsetAt0770")
    reconstructed = xyz("reconstructedActorWorldTranslationCandidate")
    render = xyz("normalRenderWorldTranslationCandidate", optional=True)
    status = payload.get("renderBranchStatus")
    if status not in (
        "alternate-render-reference-not-followed", "normal-render-pointer-absent",
        "normal-render-translation-candidate"
    ):
        raise NativePairError("unknown actor render branch status")
    if (render is None) != (status != "normal-render-translation-candidate"):
        raise NativePairError("actor renderer status and translation contradict")
    if type(payload.get("actorFlagsRaw")) is not int \
            or not 0 <= payload["actorFlagsRaw"] <= 0xFFFFFFFF:
        raise NativePairError("actor component flags invalid")
    if status == "alternate-render-reference-not-followed" \
            and payload["actorFlagsRaw"] & 1 != 1:
        raise NativePairError("alternate render flag absent")
    if status != "alternate-render-reference-not-followed" \
            and payload["actorFlagsRaw"] & 1:
        raise NativePairError("normal render branch flag mismatch")
    calculated = tuple(a + b + c for a, b, c in zip(secondary, first, second))
    primary = doc.get("candidate", {}).get("xyz")
    if not isinstance(primary, list) or len(primary) != 3:
        raise NativePairError("actor comparison lacks primary XYZ")
    try:
        primary = tuple(_number(value, "primary XYZ") for value in primary)
    except (CandidateCaptureRefused, ValueError, OverflowError) as error:
        raise NativePairError("invalid primary XYZ for actor comparison") from error
    actual_primary_delta = max(abs(a - b) for a, b in zip(primary, secondary))
    residual = max(abs(a - b) for a, b in zip(actor, calculated))
    actual_reconstructed_residual = max(abs(a - b) for a, b in zip(calculated, reconstructed))
    # Float32 store/JSON variation allowed at the scale of the source XYZ.
    epsilon = max(0.00001, max(abs(x) for x in calculated) * 1e-7)
    try:
        receipt_delta = _number(payload.get("reconstructionMaxAbsDelta"),
                                "actor reconstruction residual")
        primary_delta = _number(payload.get("primarySecondaryMaxAbsDelta"),
                                "primary/secondary delta")
    except (CandidateCaptureRefused, OverflowError, ValueError) as error:
        raise NativePairError("actor translation difference fields malformed") from error
    if (receipt_delta < 0 or primary_delta < 0 or
            abs(receipt_delta - residual) > epsilon or
            abs(primary_delta - actual_primary_delta) > epsilon or
            actual_reconstructed_residual > epsilon):
        raise NativePairError("actor translation reconstruction contradicts source values")
    if render is not None:
        try:
            render_delta = _number(payload.get("actorRenderMaxAbsDelta"),
                                   "actor-render delta")
        except (CandidateCaptureRefused, OverflowError, ValueError) as error:
            raise NativePairError("actor render residual malformed") from error
        if abs(render_delta - max(abs(a - b) for a, b in zip(actor, render))) > epsilon:
            raise NativePairError("actor/render translation contradicts receipt")
    elif payload.get("actorRenderMaxAbsDelta") is not None:
        raise NativePairError("render delta present without render translation")
    return {
        "actorStoredWorldTranslationCandidate": list(actor),
        "positionSecondaryXyz": list(secondary),
        "reconstructedActorWorldTranslationCandidate": list(reconstructed),
        "reconstructionMaxAbsDelta": receipt_delta,
        "renderBranchStatus": status,
        "normalRenderWorldTranslationCandidate": list(render) if render is not None else None,
        "authoritativePlayerPosition": False,
        "independentlyFresh": False,
    }


def _parse(doc: dict) -> dict:
    if not isinstance(doc, dict):
        raise NativePairError("candidate JSON root must be an object")
    process = doc.get("process")
    if not isinstance(process, dict):
        raise NativePairError("candidate process record missing")
    host, path, sha = (
        process.get("host"), process.get("executablePath"),
        process.get("onDiskExecutableSha256"),
    )
    pid, ticks, hwnd = (
        process.get("pid"), process.get("startUtcTicks"),
        process.get("windowHandle"),
    )
    if not isinstance(host, str) or not host.strip() or host != host.strip() \
            or not isinstance(path, str) or not ntpath.isabs(path) \
            or not isinstance(sha, str) or not _SHA.fullmatch(sha) \
            or any(type(n) is not int or n <= 0 for n in (pid, ticks, hwnd)):
        raise NativePairError("candidate source lacks qualified OS pin fields")
    try:
        ProcessPin(pid, ticks, path, sha)
        owner, xyz, yaw, timestamp, bracket = _validate_sample(
            doc, pid=pid, start_utc_ticks=ticks, executable_path=path,
            executable_sha256=sha, window_handle=hwnd, host=host
        )
        matrix = _validate_matrix_evidence(
            doc, requested=doc["evidence"].get("matrixEvidenceRequested", False))
        guard = _validate_refresh_guard(
            doc, requested=doc["evidence"].get("refreshGuardEvidenceRequested", False))
        actor = _validate_actor_translation(doc)
    except (CandidateCaptureRefused, ValueError, OverflowError) as error:
        raise NativePairError(f"candidate source validation refused: {error}") from error
    if not -180. <= yaw <= 180.:
        raise NativePairError("player system yaw outside wrapped candidate range")
    return {
        "identity": (
            host.casefold(), pid, ticks, ntpath.normcase(ntpath.normpath(path)),
            sha.casefold(), hwnd, owner
        ),
        "timestamp": timestamp,
        "bracket": bracket,
        "xyz": xyz,
        "yaw": yaw,
        "matrix": matrix,
        "guard": guard,
        "actor": actor,
    }


def compare_native_candidates(before: str | Path, after: str | Path) -> dict:
    """Offline, original-byte-hashed candidate comparison; all live flags false."""
    earlier = Path(before).resolve(strict=True)
    later = Path(after).resolve(strict=True)
    if earlier == later:
        raise NativePairError("two distinct source files required")
    earlier_doc, earlier_sha = _read_json(earlier)
    later_doc, later_sha = _read_json(later)
    a = _parse(earlier_doc)
    b = _parse(later_doc)
    if a["identity"] != b["identity"]:
        raise NativePairError("process/build/window/player owner identity changed")
    gap = b["timestamp"] - a["timestamp"]
    if not math.isfinite(gap) or gap <= 0:
        raise NativePairError("candidate samples are nonadvancing or reversed")
    delta = tuple(y - x for x, y in zip(a["xyz"], b["xyz"]))
    distance = math.hypot(*delta)
    xz = math.hypot(delta[0], delta[2])
    if not all(math.isfinite(x) for x in (distance, xz, *delta)):
        raise NativePairError("candidate displacement arithmetic overflowed")

    matrix_pair = None
    if a["matrix"] is not None and b["matrix"] is not None:
        m_a, m_b = a["matrix"], b["matrix"]
        angle_a, angle_b = (
            m_a["actorPlanarAngleDegreesCandidate"],
            m_b["actorPlanarAngleDegreesCandidate"],
        )
        matrix_pair = {
            "actorRawBitsChanged": m_a["actorRawBits"] != m_b["actorRawBits"],
            "positionSecondaryRawBitsChanged": (
                m_a["positionSecondaryRawBits"] != m_b["positionSecondaryRawBits"]
            ),
            "beforeActorPositionBitwiseMatch": m_a["exactRawBitsMatch"],
            "afterActorPositionBitwiseMatch": m_b["exactRawBitsMatch"],
            "actorMatrixAngleDeltaDegreesCandidate": (
                _wrap(angle_b - angle_a) if angle_a is not None and angle_b is not None
                else None
            ),
            "beforeActorPlusPlayerSystemAngleDegreesCandidate": (
                _wrap(angle_a + a["yaw"]) if angle_a is not None else None
            ),
            "afterActorPlusPlayerSystemAngleDegreesCandidate": (
                _wrap(angle_b + b["yaw"]) if angle_b is not None else None
            ),
            "bodyHeadingVerified": False,
        }

    guard_pair = None
    if a["guard"] is not None and b["guard"] is not None:
        ga, gb = a["guard"], b["guard"]
        guard_pair = {
            "beforeTopLevelRoute": ga["topLevelBranchCandidate"],
            "afterTopLevelRoute": gb["topLevelBranchCandidate"],
            "bothKnownRoutesIneligibleAtBothEndpoints": all(
                entry["topLevelBranchCandidate"]
                == "both-known-top-level-routes-ineligible-candidate"
                for entry in (ga, gb)
            ),
            "rawGuardInputsChanged": (
                ga["refreshHandleDecimal"] != gb["refreshHandleDecimal"]
                or ga["refreshFlagRaw"] != gb["refreshFlagRaw"]
            ),
            "otherWriterPathsRuledOut": False,
            "writerExecutionVerified": False,
        }

    actor_delta = None
    if a["actor"] is not None and b["actor"] is not None:
        old_actor = a["actor"]["actorStoredWorldTranslationCandidate"]
        new_actor = b["actor"]["actorStoredWorldTranslationCandidate"]
        actor_vector = tuple(n - o for o, n in zip(old_actor, new_actor))
        if not all(math.isfinite(v) for v in actor_vector):
            raise NativePairError("actor translation difference overflowed")
        actor_delta = {
            "deltaActorStoredWorldTranslationCandidate": list(actor_vector),
            "horizontalXZDistanceSourceUnits": math.hypot(actor_vector[0], actor_vector[2]),
            "independentlyFresh": False,
            "gameMovementVerified": False,
        }
    identity = a["identity"]
    return {
        "schema": "taxi.native-candidate-pair/1",
        "status": "offline-same-session-candidate-comparison",
        "source": {
            "host": identity[0], "pid": identity[1],
            "startUtcTicks": identity[2], "executablePath": identity[3],
            "onDiskExecutableSha256": identity[4], "windowHandle": identity[5],
            "ownerKeyDecimalCandidate": identity[6],
        },
        "sourceFiles": [
            {"role": "before", "basename": earlier.name, "sha256": earlier_sha},
            {"role": "after", "basename": later.name, "sha256": later_sha},
        ],
        "timeGapSeconds": gap,
        "candidateChanges": {
            "beforeXYZ": list(a["xyz"]), "afterXYZ": list(b["xyz"]),
            "deltaXYZ": list(delta),
            "horizontalXZDistanceSourceUnits": xz,
            "distance3dSourceUnits": distance,
            "beforePlayerSystemYawDegreesCandidate": a["yaw"],
            "afterPlayerSystemYawDegreesCandidate": b["yaw"],
            "playerSystemYawDeltaDegreesCandidate": _wrap(b["yaw"] - a["yaw"]),
            "xyzValuesChanged": a["xyz"] != b["xyz"],
            "yawValueChanged": a["yaw"] != b["yaw"],
            "matrixPair": matrix_pair,
            "refreshGuardPair": guard_pair,
            "beforeActorTranslationEvidence": a["actor"],
            "afterActorTranslationEvidence": b["actor"],
            "actorStoredTranslationPair": actor_delta,
        },
        "qualifications": {
            "sameWindowsProcessAndPlayerKey": True,
            "independentInputActionReceiptsPresent": False,
            "synchronizedGameApiOrVisualReferencePresent": False,
            "independentPassivePositionFreshnessVerified": False,
            "actorBodyHeadingVerified": False,
            "gameMovementVerified": False,
            "gameKeyInputOrReleaseVerified": False,
            "destinationArrivalVerified": False,
        },
        "limitations": [
            "Changes over a gap do not prove continuous sampling or causal game input.",
            "Native caches, actor transform and render references may share upstream values.",
            "Inspect.Unit.Detail can refresh the XYZ cache; an API-first agreement may be circular.",
            "Zero refresh guards rule out only the two known conditional top-level routes at capture time.",
            "Scalar/matrix angle correlation does not prove body heading or camera independence.",
        ],
    }
