"""
Port resolution and validation for generated patches (spec 001 FR-016, FR-017, FR-019).

The engine wires generic roles ("Audio Out", "V/Oct", "Gate In"). Each cable end is
resolved against the module's declared jacks (``Module.io_ports``):

- The module declares jacks: the role maps to a declared jack of the right type, by
  name first, then by keyword, then the first free one. The cable end becomes
  ``declared``.
- The module declares no jacks (most catalog rows): the generic name stays and the
  cable end is ``generic``, an unresolved fact the UI can label as approximate.

Findings have three severities:

- ``block``: a contradiction with what is on file. Any one fails the run
  (``validation_failed``) and nothing is saved: a module outside the confirmed
  inventory, or a declared jack used against its direction.
- ``unresolved``: a jack that is not on file (spec 001 OQ-04): the module declares no
  jacks, or no free jack of the needed type. Jack lists on file are often partial,
  so a missing jack is not proof that it does not exist.
- ``flag``: everything else worth noting, such as a feedback loop or an empty run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "V/Oct": ("oct", "pitch"),
    "FM In": ("fm",),
    "Cutoff CV": ("cut", "freq"),
    "Noise Out": ("noise",),
    "Mix Out": ("mix", "sum"),
    "LFO Out": ("lfo",),
}


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


def _pick(
    role: str, accepted: Tuple[str, ...], ports: List[Dict[str, str]], taken: set[str]
) -> Optional[Dict[str, str]]:
    candidates = [p for p in ports if p["type"] in accepted and p["name"] not in taken]
    for port in candidates:
        if port["name"] == role:
            return port
    for keyword in KEYWORDS.get(role, ()):
        for port in candidates:
            if keyword in port["name"].lower():
                return port
    return candidates[0] if candidates else None


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
                    # Jack lists on file are often partial, so a missing jack is not
                    # proof it does not exist: unresolved, not blocked.
                    code = "INPUT_ALREADY_USED" if any(p["type"] in accepted for p in ports) else "PORT_TYPE_NOT_ON_FILE"
                    report.add(
                        Finding("unresolved", code, f"{module.name}: no free {'/'.join(accepted)} jack on file for '{port}'.", index)
                    )
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
