"""Spec 003 D8 / T034: jumper-dependent power as one row per setting.

Covers the migration, the loader action (from the T035 receipt), and the rack budget
with and without a chosen setting.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from cases.models import Case
from modules.models import Module, PowerConfig
from racks.schemas import RackModuleSpec
from racks.validation import validate_rack_configuration

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
MIGRATION = BACKEND / "alembic" / "versions" / "20261030_power_configs.py"
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

RECEIPT = json.loads(P.POWER_CONFIG_RECEIPT.read_text(encoding="utf-8"))


# --- migration ---------------------------------------------------------------------


def _migration():
    spec = importlib.util.spec_from_file_location("power_configs_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_bind(self):
        return None

    def create_table(self, name, *items):
        self.calls.append(("create_table", name, {c.name: c.nullable for c in items if hasattr(c, "nullable")}))

    def create_index(self, name, table, columns):
        self.calls.append(("create_index", name, table, tuple(columns)))

    def add_column(self, table, column):
        fks = [fk.target_fullname for fk in column.foreign_keys]
        self.calls.append(("add_column", table, column.name, column.nullable, fks))

    def drop_constraint(self, name, table, type_):
        self.calls.append(("drop_constraint", name, table, type_))

    def drop_column(self, table, column):
        self.calls.append(("drop_column", table, column))

    def drop_index(self, name, table_name):
        self.calls.append(("drop_index", name, table_name))

    def drop_table(self, name):
        self.calls.append(("drop_table", name))


class _FakeInspector:
    def __init__(self, tables: dict[str, list[str]]) -> None:
        self.tables = tables

    def get_table_names(self):
        return list(self.tables)

    def get_columns(self, table):
        return [{"name": name} for name in self.tables[table]]


def _run(direction: str, tables: dict[str, list[str]], monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    module = _migration()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)
    monkeypatch.setattr(module, "inspect", lambda bind: _FakeInspector(tables))
    getattr(module, direction)()
    return fake.calls


def test_the_migration_extends_the_single_head() -> None:
    module = _migration()
    assert module.down_revision == "20261030_catalog_hp_source"
    assert len(module.revision) <= 32  # alembic_version.version_num is VARCHAR(32)
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert heads == [module.revision]


def test_upgrade_adds_the_table_and_the_placement_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _run("upgrade", {"modules": ["id"], "rack_modules": ["id", "module_id"]}, monkeypatch)
    create, index, add = calls
    assert create[:2] == ("create_table", "power_configs")
    columns = create[2]
    # Unstated rails stay NULL: every rail is nullable; identity and source are not.
    assert columns["power_12v_ma"] and columns["power_neg12v_ma"] and columns["power_5v_ma"]
    for required in ("module_id", "label", "source_url", "quote", "unit_stated", "created_at", "updated_at"):
        assert columns[required] is False, required
    assert index == ("create_index", "ix_power_configs_module_id", "power_configs", ("module_id",))
    assert add == ("add_column", "rack_modules", "power_config_id", True, ["power_configs.id"])


def test_upgrade_is_a_no_op_when_already_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    tables = {"modules": ["id"], "power_configs": ["id"], "rack_modules": ["id", "power_config_id"]}
    assert _run("upgrade", tables, monkeypatch) == []


def test_downgrade_drops_the_column_then_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    tables = {"modules": ["id"], "power_configs": ["id"], "rack_modules": ["id", "power_config_id"]}
    assert _run("downgrade", tables, monkeypatch) == [
        ("drop_constraint", "fk_rack_modules_power_config_id", "rack_modules", "foreignkey"),
        ("drop_column", "rack_modules", "power_config_id"),
        ("drop_index", "ix_power_configs_module_id", "power_configs"),
        ("drop_table", "power_configs"),
    ]


# --- loader --------------------------------------------------------------------------


def _modules_from_receipt(**overrides) -> dict[tuple[str, str], dict]:
    """Module state as the loader reads it: one row per receipt page, keyed by brand and name."""
    state = {}
    for page in RECEIPT["pages"]:
        row = {
            "brand": page["brand"],
            "name": page["name"],
            "source_reference": page["url"],
            "power_12v_ma": None,
            "power_neg12v_ma": None,
            "power_5v_ma": None,
            "status": "active",
            "_duplicate": False,
        }
        row.update(overrides.get(page["name"], {}))
        state[(page["brand"], page["name"])] = row
    return state


def _plan(modules=None, stored=None) -> P.Plan:
    plan = P.Plan()
    P._schedule_power_configs(plan, modules or _modules_from_receipt(), RECEIPT, stored if stored is not None else set())
    return plan


def _stats(plan: P.Plan) -> dict:
    return plan.power_configs["t035-jumper-power"]


def _rows(plan: P.Plan) -> dict[tuple[str, str], dict]:
    return {(op.params["name"], op.params["label"]): op.params for op in plan.ops}


def test_the_clean_jumper_settings_are_planned_and_nothing_else() -> None:
    plan = _plan()
    stats = _stats(plan)
    assert plan.inserts == {"power_configs": 17}
    assert stats["jumper_pages"] == 11 and stats["settings_seen"] == 21
    assert stats["settings_loadable"] == stats["planned_inserts"] == 17
    assert plan.conflicts_total == 0 and stats["single_column_conflicts"] == 0
    per_module: dict[str, int] = {}
    for name, _ in _rows(plan):
        per_module[name] = per_module.get(name, 0) + 1
    assert per_module == {
        "Spherical Wavetable Navigator": 2,
        "Dual Looping Delay": 1,
        "Spectral Multiband Resonator": 1,
        "4ms QCD": 2,
        "4ms QPLFO": 2,
        "4ms PEG": 2,
        "4ms VCA Matrix": 1,
        "4ms Rotating Clock Divider": 2,
        "4ms Shuffling Clock Multiplier": 2,
        "A-Envelope": 2,
    }


def test_the_owner_questions_are_skipped_not_guessed() -> None:
    stats = _stats(_plan())
    assert stats["skipped_by_reason"] == {"label_not_on_page": 3, "unit_not_stated": 1}
    assert [(s["name"], s["setting"], s["reason"]) for s in stats["skipped"]] == [
        ("Spectral Multiband Resonator", 0, "label_not_on_page"),
        ("4ms VCA Matrix", 0, "unit_not_stated"),
        ("Otool Scope and Audio Tools", 0, "label_not_on_page"),
        ("Otool Scope and Audio Tools", 1, "label_not_on_page"),
    ]
    # Otool has no clean setting, so the whole module loads nothing.
    assert stats["pages_without_clean_setting"] == 1
    assert not any(name == "Otool Scope and Audio Tools" for name, _ in _rows(_plan()))


def test_single_setting_and_load_condition_pages_are_not_loaded() -> None:
    names = {name for name, _ in _rows(_plan())}
    for page in RECEIPT["pages"]:
        if not page["jumper_dependent"]:
            assert page["name"] not in names


def test_rails_keep_the_page_values_and_unstated_stays_null() -> None:
    rows = _rows(_plan())
    qcd_ext = rows[("4ms QCD", "with jumper selecting external 5V")]
    assert (qcd_ext["power_12v_ma"], qcd_ext["power_neg12v_ma"], qcd_ext["power_5v_ma"]) == (48, 40, 41)
    # "not used (0mA)" states zero.
    qcd_int = rows[("4ms QCD", "with jumper selecting internal 5V")]
    assert (qcd_int["power_12v_ma"], qcd_int["power_neg12v_ma"], qcd_int["power_5v_ma"]) == (88, 40, 0)
    # "+5V: not used" with no number stays NULL, as the single columns store it.
    swn = rows[("Spherical Wavetable Navigator", "with LED PWR jumper set to 12V")]
    assert (swn["power_12v_ma"], swn["power_neg12v_ma"], swn["power_5v_ma"]) == (185, 30, None)
    vca = rows[("4ms VCA Matrix", "with jumper selecting internal 5V")]
    assert vca["power_12v_ma"] == 110
    assert json.loads(qcd_ext["rails"])["+5V"]["quote"].endswith("41mA with jumper selecting external 5V")
    assert qcd_ext["source_url"] == "https://4mscompany.com/p.php?p=620&c=5"
    assert qcd_ext["quote"].startswith("Power consumption:")


def test_only_the_page_that_says_recommended_is_flagged() -> None:
    flagged = [(name, label) for (name, label), row in _rows(_plan()).items() if row["is_recommended"]]
    assert flagged == [("A-Envelope", "The +5V jumper selected (Recommended)")]


def test_a_rerun_plans_nothing() -> None:
    first = _plan()
    stored = {(row["brand"], row["name"], row["setting_key"]) for row in (op.params for op in first.ops)}
    again = _plan(stored=stored)
    assert again.ops == [] and again.inserts == {}
    assert _stats(again)["already_stored"] == 17


def test_a_tombstoned_or_missing_module_gets_nothing() -> None:
    modules = _modules_from_receipt(**{"4ms PEG": {"status": "tombstoned"}})
    del modules[("Velectronic", "A-Envelope")]
    plan = _plan(modules)
    stats = _stats(plan)
    assert stats["pages_tombstoned"] == 1 and stats["pages_unmatched"] == 1
    assert plan.unmatched == {"power_configs": 1}
    assert plan.inserts == {"power_configs": 13}


def test_two_modules_on_one_page_is_a_conflict() -> None:
    modules = _modules_from_receipt()
    modules[("4ms Company", "QCD copy")] = {**modules[("4ms Company", "4ms QCD")], "name": "QCD copy"}
    plan = _plan(modules)
    assert plan.conflicts == [
        {"table": "power_configs", "brand": "4ms Company", "url": "https://4mscompany.com/p.php?p=620&c=5",
         "reason": "source_url_matches_several_modules"}
    ]
    assert plan.inserts == {"power_configs": 15}


def test_a_single_value_that_differs_from_a_setting_is_reported_not_changed() -> None:
    modules = _modules_from_receipt(**{"4ms PEG": {"power_12v_ma": 60, "power_neg12v_ma": 35}})
    plan = _plan(modules)
    # 60 matches the external setting; the internal setting states 105. -12V agrees.
    assert [(c["field"], c["setting"]) for c in plan.conflicts] == [
        ("power_12v_ma", "with jumper selecting internal 5V")
    ]
    assert _stats(plan)["single_column_conflicts"] == 1
    assert not plan.updates  # the single columns are never written


def test_the_rendered_sql_is_insert_only() -> None:
    plan = _plan()
    P.assert_safe_sql(P.render_plan(plan))
    assert all(op.sql.strip().startswith("INSERT INTO power_configs") for op in plan.ops)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"label_on_page": False}, "label_not_on_page"),
        ({"label": None}, "label_not_on_page"),
        ({"unattributed_draw": {"ma": 40, "quote": "about 40mA"}}, "draw_without_rail"),
        ({"rails": {"+12V": {"status": "stated", "ma": 80, "unit_stated": False, "quote": "80 max"}}}, "unit_not_stated"),
        ({"rails": {"+12V": {"status": "stated", "ma": None, "quote": "x"}}}, "stated_rail_without_value"),
        ({"rails": {"+12V": {"status": "guess", "ma": 1, "quote": "x"}}}, "rail_status_unknown"),
    ],
)
def test_unclean_settings_name_their_reason(change: dict, reason: str) -> None:
    base = {
        "label": "jumper A",
        "label_on_page": True,
        "kind": "jumper",
        "unattributed_draw": None,
        "rails": {
            "+12V": {"status": "stated", "ma": 10, "unit_stated": True, "quote": "10mA"},
            "-12V": {"status": "stated", "ma": 5, "unit_stated": True, "quote": "5mA"},
            "+5V": {"status": "not_used", "ma": None, "unit_stated": None, "quote": "not used"},
        },
    }
    assert P.power_setting_problem(base) is None
    rails = {**base["rails"], **change.pop("rails", {})}
    assert P.power_setting_problem({**base, **change, "rails": rails}) == reason


# --- rack budget ---------------------------------------------------------------------


def _case(db: Session, **power) -> Case:
    case = Case(
        brand="Test", name="Case", total_hp=84, rows=1, hp_per_row=[84],
        format_family="Eurorack", capacity_unit="hp", powered=True, source="test", **power,
    )
    db.add(case)
    db.commit()
    return case


def _jumper_module(db: Session, name: str = "QCD") -> tuple[Module, PowerConfig, PowerConfig]:
    # As loaded: the single columns hold only the rail every setting shares.
    module = Module(
        brand="4ms Company", name=name, hp=12, module_type="CLK",
        power_12v_ma=None, power_neg12v_ma=40, power_5v_ma=None, source="test", source_reference="t",
    )
    db.add(module)
    db.flush()
    configs = []
    for key, p12, p5 in (("external", 48, 41), ("internal", 88, 0)):
        config = PowerConfig(
            module_id=module.id, brand=module.brand, name=module.name, setting_key=key,
            label=f"with jumper selecting {key} 5V", kind="jumper", is_recommended=False,
            power_12v_ma=p12, power_neg12v_ma=40, power_5v_ma=p5, unit_stated=True, rails={},
            source_url="https://4mscompany.com/p.php?p=620&c=5", quote="Power consumption:",
            source_batch="t035-jumper-power",
        )
        db.add(config)
        configs.append(config)
    db.commit()
    return module, configs[0], configs[1]


def _codes(items) -> list[tuple[str | None, str | None]]:
    return [((i.details or {}).get("code"), (i.details or {}).get("rail")) for i in items]


def test_without_a_chosen_setting_the_jumper_rails_stay_unknown(db_session: Session) -> None:
    case = _case(db_session, power_12v_ma=1000, power_neg12v_ma=1000, power_5v_ma=1000)
    module, _, _ = _jumper_module(db_session)
    ok, errors, warnings = validate_rack_configuration(
        db_session, case.id, [RackModuleSpec(module_id=module.id, row_index=0, start_hp=0)]
    )
    assert ok and errors == []
    assert _codes(warnings) == [("POWER_RAIL_INCOMPLETE", "+12V"), ("POWER_RAIL_INCOMPLETE", "+5V")]
    assert warnings[0].details["known_draw_ma"] == 0 and warnings[0].details["unknown_modules"] == ["QCD"]


def test_a_chosen_setting_supplies_every_rail(db_session: Session) -> None:
    case = _case(db_session, power_12v_ma=1000, power_neg12v_ma=1000, power_5v_ma=1000)
    module, external, _ = _jumper_module(db_session)
    ok, errors, warnings = validate_rack_configuration(
        db_session, case.id,
        [RackModuleSpec(module_id=module.id, row_index=0, start_hp=0, power_config_id=external.id)],
    )
    assert ok and errors == [] and warnings == []


def test_the_chosen_setting_is_what_the_budget_enforces(db_session: Session) -> None:
    case = _case(db_session, power_12v_ma=60, power_neg12v_ma=1000, power_5v_ma=1000)
    module, external, internal = _jumper_module(db_session)

    def check(config):
        return validate_rack_configuration(
            db_session, case.id,
            [RackModuleSpec(module_id=module.id, row_index=0, start_hp=0, power_config_id=config.id)],
        )

    ok, errors, _ = check(external)  # 48 mA on +12V fits 60
    assert ok and errors == []
    ok, errors, _ = check(internal)  # 88 mA on +12V does not
    assert not ok
    assert _codes(errors) == [("POWER_EXCEEDED_12V", None)]
    assert errors[0].details["total_power_12v"] == 88


def test_a_setting_of_another_module_is_refused(db_session: Session) -> None:
    case = _case(db_session, power_12v_ma=1000, power_neg12v_ma=1000, power_5v_ma=1000)
    module, _, _ = _jumper_module(db_session, name="QCD")
    _, other, _ = _jumper_module(db_session, name="QPLFO")
    for config_id in (other.id, 999_999):
        ok, errors, _ = validate_rack_configuration(
            db_session, case.id,
            [RackModuleSpec(module_id=module.id, row_index=0, start_hp=0, power_config_id=config_id)],
        )
        assert not ok
        assert _codes(errors) == [("POWER_CONFIG_NOT_FOR_MODULE", None)]
        assert errors[0].field == "modules[0].power_config_id"
