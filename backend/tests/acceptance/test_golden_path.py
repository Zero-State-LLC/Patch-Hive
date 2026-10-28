import json
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from patches.models import Patch


def _patch_fingerprint(patch: dict) -> str:
    cables_json = json.dumps(patch["connections"], sort_keys=True)
    # Prefer the displayed name: override > suggested > stored name.
    display_name = patch.get("name_override") or patch.get("suggested_name") or patch.get("name")
    payload = f"{cables_json}|{display_name}|{patch['category']}|{patch['difficulty']}"
    return sha256(payload.encode()).hexdigest()


def _run_fingerprint(patches: list[dict]) -> str:
    fingerprint_list = sorted(_patch_fingerprint(patch) for patch in patches)
    return sha256("".join(fingerprint_list).encode()).hexdigest()


def _build_modules_payload(modules, row_hp: int) -> list[dict]:
    payload = []
    row_index = 0
    start_hp = 0
    for module in modules:
        if start_hp + module.hp > row_hp:
            row_index += 1
            start_hp = 0
        payload.append({"module_id": module.id, "row_index": row_index, "start_hp": start_hp})
        start_hp += module.hp
    return payload


def test_create_rig_multi_rig(api_client, login, create_user, seed_minimal_modules):
    create_user("user1", "pass123")
    api_client.headers["Authorization"] = f"Bearer {login('user1', 'pass123')}"
    modules_payload = _build_modules_payload(
        seed_minimal_modules["modules"][:8],
        seed_minimal_modules["case"].hp_per_row[0],
    )

    payload = {
        "case_id": seed_minimal_modules["case"].id,
        "name": None,
        "description": "First rig",
        "tags": ["golden"],
        "is_public": False,
        "generation_seed": 1234,
        "modules": modules_payload,
    }

    resp = api_client.post("/api/racks", json=payload)
    resp.raise_for_status()
    data = resp.json()
    assert data["id"]
    assert data["name"]

    payload["description"] = "Second rig"
    resp2 = api_client.post("/api/racks", json=payload)
    resp2.raise_for_status()

    list_resp = api_client.get("/api/racks")
    list_resp.raise_for_status()
    assert list_resp.json()["total"] == 2


def test_golden_demo_fingerprint(api_client, login, golden_demo_seed):
    # The seeded demo user owns the golden rig.
    api_client.headers["Authorization"] = f"Bearer {login(golden_demo_seed.username, golden_demo_seed.password)}"
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "golden_demo_seed.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    run_resp = api_client.get(f"/api/runs/{golden_demo_seed.run_id}/patches")
    run_resp.raise_for_status()
    patches = run_resp.json()["patches"]

    expected = fixture["expected_hashes"]
    minimums = fixture["expected_minimums"]
    assert len(patches) == expected["patch_count"]
    assert len(patches) >= minimums["min_patches"]
    diagrammed = [p for p in patches if p["diagram_svg_url"]]
    assert len(diagrammed) >= minimums["min_with_diagrams"]
    assert _run_fingerprint(patches) == expected["run_fingerprint"]


def test_generate_patch_library_deterministic(
    api_client, login, db_session: Session, create_user, seed_minimal_modules
):
    create_user("user2", "pass123")
    api_client.headers["Authorization"] = f"Bearer {login('user2', 'pass123')}"

    modules_payload = _build_modules_payload(
        seed_minimal_modules["modules"][:8],
        seed_minimal_modules["case"].hp_per_row[0],
    )

    rack_resp = api_client.post(
        "/api/racks",
        json={
            "case_id": seed_minimal_modules["case"].id,
            "name": None,
            "description": "Rig",
            "tags": [],
            "is_public": False,
            "generation_seed": 4242,
            "modules": modules_payload,
        },
    )
    rack_resp.raise_for_status()
    rack_id = rack_resp.json()["id"]

    gen_resp = api_client.post(
        f"/api/patches/generate/{rack_id}",
        json={"seed": 4242, "max_patches": 12, "allow_feedback": True},
    )
    gen_resp.raise_for_status()
    run_id = gen_resp.json()["run_id"]

    run_resp = api_client.get(f"/api/runs/{run_id}/patches")
    run_resp.raise_for_status()
    patches = run_resp.json()["patches"]
    assert patches
    assert all(patch["diagram_svg_url"] for patch in patches)
    assert all(patch["suggested_name"] for patch in patches)
    assert all(patch["category"] for patch in patches)
    assert all(patch["difficulty"] for patch in patches)

    stored_patch = db_session.query(Patch).filter(Patch.run_id == run_id).first()
    assert stored_patch is not None
    assert stored_patch.generation_ir
    assert stored_patch.generation_ir.get("seed") == 4242
    assert stored_patch.generation_ir.get("engine_version")

    regen_resp = api_client.post(
        f"/api/patches/generate/{rack_id}",
        json={"seed": 4242, "max_patches": 12, "allow_feedback": True},
    )
    regen_resp.raise_for_status()
    run_id_2 = regen_resp.json()["run_id"]

    run_resp_2 = api_client.get(f"/api/runs/{run_id_2}/patches")
    run_resp_2.raise_for_status()
    patches_2 = run_resp_2.json()["patches"]

    hashes_1 = [_patch_fingerprint(p) for p in patches]
    hashes_2 = [_patch_fingerprint(p) for p in patches_2]
    assert len(hashes_1) == len(hashes_2)
    assert sorted(hashes_1) == sorted(hashes_2)
    assert [p["suggested_name"] for p in patches] == [p["suggested_name"] for p in patches_2]

    regen_resp_diff = api_client.post(
        f"/api/patches/generate/{rack_id}",
        json={"seed": 7777, "max_patches": 12, "allow_feedback": True},
    )
    regen_resp_diff.raise_for_status()
    run_id_3 = regen_resp_diff.json()["run_id"]
    run_resp_3 = api_client.get(f"/api/runs/{run_id_3}/patches")
    run_resp_3.raise_for_status()
    patches_3 = run_resp_3.json()["patches"]
    hashes_3 = [_patch_fingerprint(p) for p in patches_3]
    assert any(h not in hashes_1 for h in hashes_3)


def test_patch_naming_humor_gating(api_client, login, seed_minimal_modules, create_user):
    create_user("user3", "pass123")
    api_client.headers["Authorization"] = f"Bearer {login('user3', 'pass123')}"

    rack_resp = api_client.post(
        "/api/racks",
        json={
            "case_id": seed_minimal_modules["case"].id,
            "name": "Humor Rig",
            "description": "Humor",
            "tags": [],
            "is_public": False,
            "generation_seed": 100,
            "modules": [
                {"module_id": seed_minimal_modules["modules"][0].id, "row_index": 0, "start_hp": 0},
            ],
        },
    )
    rack_resp.raise_for_status()
    rack_id = rack_resp.json()["id"]

    patch_payload = {
        "rack_id": rack_id,
        "name": "Looped",
        "category": "Experimental-Feedback",
        "description": "Self feedback",
        "connections": [
            {
                "from_module_id": seed_minimal_modules["modules"][0].id,
                "from_port": "Out",
                "to_module_id": seed_minimal_modules["modules"][0].id,
                "to_port": "In",
                "cable_type": "audio",
            }
        ],
        "generation_seed": 101,
        "generation_version": "1.0.0",
        "engine_config": {},
        "is_public": False,
        "tags": [],
    }
    resp = api_client.post("/api/patches", json=patch_payload)
    resp.raise_for_status()
    patch = resp.json()
    assert "humor" in patch["tags"]

    patch_payload["connections"] = [
        {
            "from_module_id": seed_minimal_modules["modules"][0].id,
            "from_port": "Out",
            "to_module_id": seed_minimal_modules["modules"][0].id + 1,
            "to_port": "In",
            "cable_type": "audio",
        }
    ]
    resp2 = api_client.post("/api/patches", json=patch_payload)
    resp2.raise_for_status()
    patch2 = resp2.json()
    assert "humor" not in patch2["tags"]


def test_run_history(api_client, login, create_user, seed_minimal_modules):
    create_user("user4", "pass123")
    api_client.headers["Authorization"] = f"Bearer {login('user4', 'pass123')}"

    modules_payload = _build_modules_payload(
        seed_minimal_modules["modules"][:6],
        seed_minimal_modules["case"].hp_per_row[0],
    )

    rack_resp = api_client.post(
        "/api/racks",
        json={
            "case_id": seed_minimal_modules["case"].id,
            "name": "History Rig",
            "description": "History",
            "tags": [],
            "is_public": False,
            "generation_seed": 300,
            "modules": modules_payload,
        },
    )
    rack_resp.raise_for_status()
    rack_id = rack_resp.json()["id"]

    gen_resp_1 = api_client.post(
        f"/api/patches/generate/{rack_id}",
        json={"seed": 1111, "max_patches": 8},
    )
    gen_resp_1.raise_for_status()
    run_id_1 = gen_resp_1.json()["run_id"]

    gen_resp_2 = api_client.post(
        f"/api/patches/generate/{rack_id}",
        json={"seed": 2222, "max_patches": 8},
    )
    gen_resp_2.raise_for_status()
    run_id_2 = gen_resp_2.json()["run_id"]

    runs_resp = api_client.get(f"/api/runs?rack_id={rack_id}")
    runs_resp.raise_for_status()
    runs = runs_resp.json()["runs"]
    run_ids = {run["id"] for run in runs}
    assert {run_id_1, run_id_2}.issubset(run_ids)

    patches_resp = api_client.get(f"/api/runs/{run_id_1}/patches")
    patches_resp.raise_for_status()
    older_patches = patches_resp.json()["patches"]

    patches_resp_2 = api_client.get(f"/api/runs/{run_id_2}/patches")
    patches_resp_2.raise_for_status()
    newer_patches = patches_resp_2.json()["patches"]

    assert older_patches != newer_patches
