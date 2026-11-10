"""
Port resolution and validation for generated patches (spec 001 FR-016, FR-017, FR-019).

The engine wires generic roles ("Audio Out", "V/Oct", "Gate In"). Each cable end is
resolved against the module's declared jacks (``Module.io_ports``):

- The module declares jacks: the role maps to a declared jack of the right type when
  its name settles which one: the exact name, then a keyword, then a channel mark
  (1, A, Left), then the only jack of its kind. The cable end becomes ``declared``.
- Several jacks could take the cable and no name settles it: the generic name stays
  and the cable end is ``generic``. A wrong jack with no warning is worse than a role.
- The module declares no jacks (most catalog rows): the generic name stays and the
  cable end is ``generic``, an unresolved fact the UI can label as approximate.

Findings have three severities:

- ``block``: a contradiction with what is on file. Any one fails the run
  (``validation_failed``) and nothing is saved: a module outside the confirmed
  inventory, or a declared jack used against its direction.
- ``unresolved``: a jack that is not settled (spec 001 OQ-04): the module declares no
  jacks, no free jack of the needed type, or several that could fit. Lists on file come
  from documents and not panels, so a missing jack is not proof that it does not exist.
- ``flag``: everything else worth noting, such as a feedback loop or an empty run.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core.ir import ConnectionIR, PatchGraphIR

# Generic role -> (direction, accepted declared jack types, name keywords to prefer).
OUTPUT_ROLES: Dict[str, Tuple[str, ...]] = {
    "Audio Out": ("audio_out",),
    "Noise Out": ("audio_out",),
    "Mix Out": ("audio_out",),
    "LFO Out": ("cv_out",),
    "Envelope Out": ("cv_out",),
    "CV Out": ("cv_out",),
    "Gate Out": ("gate_out", "trigger_out", "clock_out"),
}
INPUT_ROLES: Dict[str, Tuple[str, ...]] = {
    "Audio In": ("audio_in",),
    "FX In": ("audio_in",),
    "In 1": ("audio_in",),
    "In 2": ("audio_in",),
    "CV In": ("cv_in",),
    "FM In": ("cv_in",),
    "Cutoff CV": ("cv_in",),
    "V/Oct": ("cv_in",),
    "Gate In": ("gate_in", "trigger_in", "clock_in"),
}
# Each keyword must start a word, so "amp" is not found in "Damp".
KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "V/Oct": ("oct", "voct", "v/o", "pitch"),
    "FM In": ("fm", "tzfm", "frequency mod", "linear freq"),
    "Cutoff CV": ("cut", "freq", "cf", "cvf", "filter", "mod"),
    "CV In": ("vca", "level", "amp", "gain", "am ", "control"),
    "Audio Out": (
        "lowpass", "low-pass", "low pass", "lp", "main", "mix",
        "saw", "ramp", "square", "pulse", "tri", "sin",
    ),
    "Audio In": ("audio", "signal", "main"),
    "FX In": ("audio", "signal", "main"),
    "Noise Out": ("noise", "white"),
    "Mix Out": ("mix", "sum", "main"),
    "LFO Out": ("lfo", "primary", "smooth", "tri", "sin"),
    "Envelope Out": ("env", "contour", "adsr", "eg"),
    "CV Out": ("pitch", "note", "freq", "tuned", "cv"),
    "Gate Out": ("gate", "trig"),
    "Gate In": ("gate", "trig"),
}
# Jacks that serve a side purpose, passed over when a main jack of the same kind exists.
SECONDARY = re.compile(
    r"(?<!non-)(?<!non )(?<![a-z])inv|mirror|(?<![a-z0-9])(?:neg|eoc|eor|end|send|return|thru(?![- ]?zero)|through"
    r"|headphone|feedback|aux|sub)"
)
# Channels are interchangeable, so a plain channel mark decides. These roles each have a
# specific job, and a channel mark says nothing about which input does it.
FIRST_CHANNEL = re.compile(r"(?<![a-z0-9])(?:left|l|mono|a)(?![a-z0-9])|(?<![\d.])1(?![\d.])")
SECOND_CHANNEL = re.compile(r"(?<![a-z0-9])(?:right|r|b)(?![a-z0-9])|(?<![\d.])2(?![\d.])")
NO_CHANNEL_ROLES = frozenset({"V/Oct", "FM In", "Cutoff CV"})


@dataclass(frozen=True)
class Finding:
    severity: str  # "block" | "unresolved" | "flag"
    code: str
    message: str
    patch_index: Optional[int] = None


@dataclass
class ValidationReport:
    findings: List[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        # One finding per fact: a module with no jacks on file is reported once per patch.
        if finding not in self.findings:
            self.findings.append(finding)

    @property
    def blocking(self) -> bool:
        return any(f.severity == "block" for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return {
            "blocking": self.blocking,
            "counts": counts,
            "findings": [asdict(f) for f in self.findings],
        }


def _declared(module: Any) -> List[Dict[str, str]]:
    ports = getattr(module, "io_ports", None) or []
    return [p for p in ports if isinstance(p, dict) and p.get("name") and p.get("type")]


def _by_channel(role: str, ports: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """The lowest channel still free: a second cable of a role moves on to the next channel."""
    if role in NO_CHANNEL_ROLES:
        return None
    marks = (SECOND_CHANNEL, FIRST_CHANNEL) if role == "In 2" else (FIRST_CHANNEL, SECOND_CHANNEL)
    for mark in marks:
        for port in ports:
            if mark.search(port["name"].lower()):
                return port
    return None


def _pick(
    role: str, accepted: Tuple[str, ...], ports: List[Dict[str, str]], taken: set[str]
) -> Optional[Dict[str, str]]:
    """The jack this role means, or None when no name settles it (spec 001 FR-016)."""
    of_kind = [p for p in ports if p["type"] in accepted]
    main = [p for p in of_kind if not SECONDARY.search(p["name"].lower())] or of_kind
    free = [p for p in main if p["name"] not in taken]
    for port in free:
        if port["name"] == role:
            return port
    for keyword in KEYWORDS.get(role, ()):
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}")
        matches = [p for p in free if pattern.search(p["name"].lower())]
        if matches:
            return _by_channel(role, matches) or matches[0]
    return _by_channel(role, free) or (free[0] if len(main) == 1 and free else None)


def resolve_and_validate(
    patch_graphs: Iterable[PatchGraphIR],
    modules_by_id: Dict[int, Any],
    allowed_module_ids: Optional[set[int]] = None,
) -> Tuple[List[PatchGraphIR], ValidationReport]:
    """Resolve each cable end to a declared jack where one exists, and report what
    cannot be resolved. Returns the resolved patches and the report."""
    report = ValidationReport()
    resolved: List[PatchGraphIR] = []
    graphs = list(patch_graphs)
    if not graphs:
        report.add(Finding("flag", "NO_PATCHES", "No rule fits this rack."))

    for index, graph in enumerate(graphs):
        taken_inputs: Dict[int, set[str]] = {}
        connections: List[ConnectionIR] = []
        for cable in graph.connections:
            ends = []
            for module_id, port, roles, direction in (
                (cable.from_module_id, cable.from_port, OUTPUT_ROLES, "out"),
                (cable.to_module_id, cable.to_port, INPUT_ROLES, "in"),
            ):
                module = modules_by_id.get(module_id)
                if module is None or (allowed_module_ids is not None and module_id not in allowed_module_ids):
                    report.add(
                        Finding("block", "MODULE_NOT_IN_INVENTORY", f"Module {module_id} is not in the confirmed inventory.", index)
                    )
                    ends.append((port, "generic"))
                    continue
                ports = _declared(module)
                if not ports:
                    report.add(
                        Finding("unresolved", "PORT_NOT_ON_FILE", f"{module.name}: jack names are not on file, so its jacks are generic.", index)
                    )
                    ends.append((port, "generic"))
                    continue
                accepted = roles.get(port)
                if accepted is None:
                    # Already a declared name: check it exists and points the right way.
                    match = next((p for p in ports if p["name"] == port), None)
                    if match is None or not match["type"].endswith(f"_{direction}"):
                        report.add(
                            Finding("block", "PORT_DIRECTION_MISMATCH", f"{module.name}: '{port}' is not a declared {direction}put.", index)
                        )
                    ends.append((port, "declared"))
                    continue
                taken = taken_inputs.setdefault(module_id, set()) if direction == "in" else set()
                choice = _pick(port, accepted, ports, taken)
                if choice is None:
                    # Lists on file come from documents, so a missing jack is not proof
                    # it does not exist: unresolved, not blocked.
                    of_kind = [p for p in ports if p["type"] in accepted]
                    if any(p["name"] not in taken for p in of_kind):
                        code, reason = "SEVERAL_JACKS_FIT", f"several jacks could take '{port}' and no name settles which"
                    else:
                        code = "INPUT_ALREADY_USED" if of_kind else "PORT_TYPE_NOT_ON_FILE"
                        reason = f"no free {'/'.join(accepted)} jack on file for '{port}'"
                    report.add(Finding("unresolved", code, f"{module.name}: {reason}.", index))
                    ends.append((port, "generic"))
                    continue
                if direction == "in":
                    taken.add(choice["name"])
                ends.append((choice["name"], "declared"))
            (from_port, from_status), (to_port, to_status) = ends
            connections.append(
                ConnectionIR(
                    from_module_id=cable.from_module_id,
                    from_port=from_port,
                    to_module_id=cable.to_module_id,
                    to_port=to_port,
                    cable_type=cable.cable_type,
                    port_status="declared" if from_status == to_status == "declared" else "generic",
                )
            )
            if cable.from_module_id == cable.to_module_id:
                report.add(
                    Finding("flag", "FEEDBACK_LOOP", "A module patched into itself.", index)
                )
        if _route_loops_through_other_modules(connections):
            report.add(
                Finding("flag", "FEEDBACK_LOOP", "A route through other modules comes back to where it began.", index)
            )
        resolved.append(
            PatchGraphIR(
                patch_name=graph.patch_name,
                category=graph.category,
                connections=connections,
                description=graph.description,
                generation_ir_hash=graph.generation_ir_hash,
                generation_seed=graph.generation_seed,
            )
        )
    return resolved, report


def _route_loops_through_other_modules(connections: List[ConnectionIR]) -> bool:
    """A cycle of two or more modules, which the canonical compiler calls an undeclared feedback
    cycle (spec 001 D9). A module patched directly into itself is flagged where it's found."""
    next_modules: Dict[int, Set[int]] = {}
    for cable in connections:
        if cable.from_module_id != cable.to_module_id:
            next_modules.setdefault(cable.from_module_id, set()).add(cable.to_module_id)

    def reaches(start: int) -> bool:
        seen: Set[int] = set()
        stack = list(next_modules.get(start, ()))
        while stack:
            module_id = stack.pop()
            if module_id == start:
                return True
            if module_id not in seen:
                seen.add(module_id)
                stack.extend(next_modules.get(module_id, ()))
        return False

    return any(reaches(module_id) for module_id in next_modules)


def drop_feedback_patches(
    patch_graphs: List[PatchGraphIR], report: ValidationReport
) -> Tuple[List[PatchGraphIR], int]:
    """Remove patches that carry a ``FEEDBACK_LOOP`` finding (``allow_feedback=false``).
    Their findings go with them and the rest are re-indexed. Returns the kept patches
    and how many were dropped."""
    looped = {f.patch_index for f in report.findings if f.code == "FEEDBACK_LOOP"}
    if not looped:
        return list(patch_graphs), 0
    new_index: Dict[int, int] = {}
    kept: List[PatchGraphIR] = []
    for index, graph in enumerate(patch_graphs):
        if index not in looped:
            new_index[index] = len(kept)
            kept.append(graph)
    report.findings = [
        replace(f, patch_index=new_index[f.patch_index])
        if f.patch_index is not None
        else f
        for f in report.findings
        if f.patch_index is None or f.patch_index in new_index
    ]
    return kept, len(patch_graphs) - len(kept)
