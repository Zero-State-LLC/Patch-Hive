"""Unit tests for case format + power validation (C1/C2)."""

from sqlalchemy.orm import Session

from cases.models import Case
from modules.models import Module
from racks.schemas import RackModuleSpec
from racks.validation import validate_rack_configuration


def _case(db: Session, **kwargs) -> Case:
    defaults = dict(
        brand="Test",
        name="Case",
        total_hp=84,
        rows=1,
        hp_per_row=[84],
        format_family="Eurorack",
        capacity_unit="hp",
        powered=True,
        source="test",
    )
    defaults.update(kwargs)
    row = Case(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mod(db: Session, hp: int = 12, p12: int = 50) -> Module:
    m = Module(
        brand="T",
        name=f"M{hp}",
        hp=hp,
        module_type="VCO",
        power_12v_ma=p12,
        power_neg12v_ma=10,
        source="test",
        source_reference="t",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_power_exceeded_hard_error(db_session: Session):
    case = _case(db_session, power_12v_ma=40, power_neg12v_ma=100)
    mod = _mod(db_session, p12=50)
    ok, errors, warnings = validate_rack_configuration(
        db_session, case.id, [RackModuleSpec(module_id=mod.id, row_index=0, start_hp=0)]
    )
    assert not ok
    assert any((e.details or {}).get("code") == "POWER_EXCEEDED_12V" for e in errors)
    assert warnings == []


def test_power_unspecified_warning(db_session: Session):
    case = _case(db_session, power_12v_ma=None, power_neg12v_ma=None, power_5v_ma=None)
    mod = _mod(db_session, p12=50)
    ok, errors, warnings = validate_rack_configuration(
        db_session, case.id, [RackModuleSpec(module_id=mod.id, row_index=0, start_hp=0)]
    )
    assert ok
    assert errors == []
    assert any((w.details or {}).get("code") == "POWER_UNSPECIFIED" for w in warnings)


def test_unpowered_case_hard_error(db_session: Session):
    case = _case(db_session, powered=False, power_12v_ma=None)
    mod = _mod(db_session, p12=50)
    ok, errors, _ = validate_rack_configuration(
        db_session, case.id, [RackModuleSpec(module_id=mod.id, row_index=0, start_hp=0)]
    )
    assert not ok
    assert any((e.details or {}).get("code") == "POWER_ON_UNPOWERED_CASE" for e in errors)


def test_non_eurorack_placement_hard_error(db_session: Session):
    case = _case(
        db_session,
        format_family="Buchla",
        capacity_unit="buchla_panels",
        total_hp=4,
        hp_per_row=[4],
    )
    mod = _mod(db_session)
    ok, errors, _ = validate_rack_configuration(
        db_session, case.id, [RackModuleSpec(module_id=mod.id, row_index=0, start_hp=0)]
    )
    assert not ok
    assert any(
        (e.details or {}).get("code") == "FORMAT_NOT_SUPPORTED_FOR_PLACEMENT" for e in errors
    )


def test_empty_modules_ok(db_session: Session):
    case = _case(db_session)
    ok, errors, warnings = validate_rack_configuration(db_session, case.id, [])
    assert ok
    assert errors == []
    assert warnings == []


# --- unknown draws per rail (spec 003 FR-022: unknown is never 0) -----------------


def _partial(db: Session, *, name: str, p12=None, n12=None, p5=None) -> Module:
    m = Module(
        brand="T", name=name, hp=4, module_type="UTIL",
        power_12v_ma=p12, power_neg12v_ma=n12, power_5v_ma=p5,
        source="test", source_reference="t",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _place(*mods: Module) -> list[RackModuleSpec]:
    return [RackModuleSpec(module_id=m.id, row_index=0, start_hp=i * 4) for i, m in enumerate(mods)]


def _codes(items) -> list[tuple[str, str | None]]:
    return [((i.details or {}).get("code"), (i.details or {}).get("rail")) for i in items]


def test_a_known_rail_with_unknown_draws_is_incomplete(db_session: Session):
    case = _case(db_session, power_12v_ma=500, power_neg12v_ma=500, power_5v_ma=100)
    known = _partial(db_session, name="Known", p12=60, n12=20, p5=0)
    no_neg = _partial(db_session, name="No -12", p12=40)
    ok, errors, warnings = validate_rack_configuration(db_session, case.id, _place(known, no_neg))
    assert ok and errors == []
    assert _codes(warnings) == [("POWER_RAIL_INCOMPLETE", "-12V"), ("POWER_RAIL_INCOMPLETE", "+5V")]
    neg = warnings[0].details
    assert neg["known_draw_ma"] == 20 and neg["unknown_draw_count"] == 1
    assert neg["unknown_modules"] == ["No -12"]
    assert "at least 20mA of 500mA, plus 1 module with unknown draw" in warnings[0].message


def test_known_draws_over_capacity_stay_an_error_whatever_is_unknown(db_session: Session):
    case = _case(db_session, power_12v_ma=50, power_neg12v_ma=500, power_5v_ma=0)
    big = _partial(db_session, name="Big", p12=80, n12=10, p5=0)
    unknown = _partial(db_session, name="Unknown")
    ok, errors, warnings = validate_rack_configuration(db_session, case.id, _place(big, unknown))
    assert not ok
    assert _codes(errors) == [("POWER_EXCEEDED_12V", None)]
    # +12V already fails; the other rails are lower bounds.
    assert _codes(warnings) == [("POWER_RAIL_INCOMPLETE", "-12V"), ("POWER_RAIL_INCOMPLETE", "+5V")]


def test_fully_specified_modules_raise_no_power_warning(db_session: Session):
    case = _case(db_session, power_12v_ma=500, power_neg12v_ma=500, power_5v_ma=100)
    mod = _partial(db_session, name="Full", p12=60, n12=20, p5=0)
    ok, errors, warnings = validate_rack_configuration(db_session, case.id, _place(mod))
    assert ok and errors == [] and warnings == []


def test_modules_with_no_known_draw_still_warn_on_an_unspecified_case(db_session: Session):
    case = _case(db_session, power_12v_ma=None, power_neg12v_ma=None, power_5v_ma=None)
    mod = _partial(db_session, name="Blank")
    ok, errors, warnings = validate_rack_configuration(db_session, case.id, _place(mod))
    assert ok
    assert _codes(warnings) == [("POWER_UNSPECIFIED", None)]
    assert warnings[0].details["unknown_draw_count"] == {"+12V": 1, "-12V": 1, "+5V": 1}
