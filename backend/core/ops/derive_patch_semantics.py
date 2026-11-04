from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable


def _get_attr(conn: Any, key: str, default: Any = None) -> Any:
    if isinstance(conn, dict):
        return conn.get(key, default)
    return getattr(conn, key, default)


def _infer_output_kind(module: Any, cable_type: str) -> str:
    mtype = getattr(module, "module_type", "") or ""
    mtype = mtype.upper()

    if "ENV" in mtype or "ENVELOPE" in mtype or "ADSR" in mtype:
        return "envelope"
    if "LFO" in mtype:
        return "lfo"
    if "SEQ" in mtype or "CLOCK" in mtype:
        return "clock"
    if "NOISE" in mtype or "RANDOM" in mtype:
        return "random"

    if cable_type == "clock":
        return "clock"
    if cable_type == "gate":
        return "gate"
    if cable_type == "audio":
        return "audio"
    if cable_type == "cv":
        return "cv"

    return "cv"


def _infer_input_kind(cable_type: str) -> str:
    if cable_type in {"audio", "cv", "gate", "clock"}:
        return cable_type
    return "cv"


def derive_patch_semantics(
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
) -> Dict[str, str]:
    """
    Produces a small semantic signature:
      - source_role
      - transform_role
      - control_role
      - clocked (yes/no)
    """
    kinds_out = []
    kinds_in = []

    for conn in connections:
        from_id = _get_attr(conn, "from_module_id")
        cable_type = _get_attr(conn, "cable_type", "audio")

        from_module = modules_by_id.get(from_id)
        kinds_out.append(_infer_output_kind(from_module, cable_type))
        kinds_in.append(_infer_input_kind(cable_type))

    outc = Counter(kinds_out)
    inc = Counter(kinds_in)

    source = "Source"
    if outc.get("audio", 0):
        source = "Voice"
    elif outc.get("random", 0):
        source = "Random"
    elif outc.get("lfo", 0):
        source = "LFO"
    elif outc.get("clock", 0):
        source = "Clock"

    transform = "Path"
    if inc.get("cv", 0) and inc.get("audio", 0):
        transform = "Shaped"
    elif inc.get("audio", 0):
        transform = "Filtered"
    elif inc.get("cv", 0):
        transform = "Modulated"

    control = "Free"
    if outc.get("envelope", 0):
        control = "Enveloped"
    elif outc.get("lfo", 0):
        control = "Cycled"
    elif outc.get("random", 0):
        control = "Drifting"

    clocked = "Clock-Rhythm" if (outc.get("clock", 0) or inc.get("clock", 0)) else "Free"

    return {
        "source": source,
        "transform": transform,
        "control": control,
        "clocked": clocked,
    }
