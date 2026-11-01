import threading
import types

import pytest
from fastapi.testclient import TestClient

from app import app
from config import MAX_CANDIDATES, MAX_IMAGE_BYTES, MAX_NEW_NODES, MAX_TREE_COUNT
from routers import scenes as scenes_router

from conftest import solid_image, to_data_url

client = TestClient(app)


@pytest.fixture(scope="module")
def black():
    return to_data_url(solid_image(100, 30, 0))


def body(black, **overrides):
    req = {
        "count": 1,
        "params": {"treeCount": 1, "maxThickness": 0.5, "branchingProb": 0.5, "maxAngle": 0.5},
        "targetShadows": [
            {"imageData": black, "lightVector": {"x": 0, "y": 0, "z": -1}},
            {"imageData": black, "lightVector": {"x": -1, "y": 0, "z": 0}},
        ],
        "max_new_nodes": 30,
    }
    req.update(overrides)
    return req


def test_generate_returns_schema_and_openapi_documents_it(black):
    r = client.post("/scenes/generate", json=body(black))
    assert r.status_code == 200
    data = r.json()
    assert len(data["scenes"]) == 1
    assert data["stats"]["total_attractors"] > 0
    schema = client.get("/openapi.json").json()
    ok = schema["paths"]["/scenes/generate"]["post"]["responses"]["200"]
    assert ok["content"]["application/json"]["schema"]["$ref"].endswith("GenerateResponse")


@pytest.mark.parametrize(
    "overrides",
    [
        {"count": 0},
        {"count": MAX_CANDIDATES + 1},
        {"max_new_nodes": 0},
        {"max_new_nodes": MAX_NEW_NODES + 1},
        {"targetShadows": []},
        {"parent_generation": -1},
    ],
)
def test_out_of_range_inputs_are_rejected_with_422(black, overrides):
    assert client.post("/scenes/generate", json=body(black, **overrides)).status_code == 422


def test_tree_count_limit(black):
    b = body(black)
    b["params"]["treeCount"] = MAX_TREE_COUNT + 1
    assert client.post("/scenes/generate", json=b).status_code == 422


def test_dangling_parent_id_rejected(black):
    nodes = [{"id": "a", "x": 0, "y": 0, "z": 0, "radius": 0.1, "parentId": "missing"}]
    assert client.post("/scenes/generate", json=body(black, parent_nodes=nodes)).status_code == 422


@pytest.mark.parametrize(
    "image_data, status",
    [
        ("data:image/png;base64", 422),  # no comma
        ("data:image/png;base64,!!!notbase64!!!", 422),
        ("data:image/png;base64,aGVsbG8=", 422),  # valid base64, not an image
        ("data:image/png;base64," + "A" * (MAX_IMAGE_BYTES * 2), 413),
    ],
)
def test_bad_images_give_4xx_not_500(black, image_data, status):
    b = body(black)
    b["targetShadows"][0]["imageData"] = image_data
    assert client.post("/scenes/generate", json=b).status_code == status


def test_run_until_complete_stops_and_reports(black, monkeypatch):
    # All-black target = huge volume; the wall-clock budget must end the run.
    monkeypatch.setattr(scenes_router, "MAX_RUN_SECONDS", 1)
    r = client.post("/scenes/generate", json=body(black, run_until_complete=True, max_new_nodes=100))
    assert r.status_code == 200
    stats = r.json()["stats"]
    assert stats["growth_stopped_reason"] in {
        "attractors_exhausted",
        "unreachable_attractors",
        "node_limit",
        "influence_radius",
        "max_nodes",
        "no_valid_growth",
        "time_limit",
    }


def test_abort_targets_only_the_named_request(monkeypatch):
    a, b = threading.Event(), threading.Event()
    monkeypatch.setitem(scenes_router._active_requests, "a", a)
    monkeypatch.setitem(scenes_router._active_requests, "b", b)
    r = client.post("/scenes/abort", params={"request_id": "a"})
    assert r.json() == {"aborted": True, "requests_aborted": 1}
    assert a.is_set() and not b.is_set()


def test_abort_without_id_aborts_all_inflight(monkeypatch):
    a, b = threading.Event(), threading.Event()
    monkeypatch.setitem(scenes_router._active_requests, "a", a)
    monkeypatch.setitem(scenes_router._active_requests, "b", b)
    assert client.post("/scenes/abort").json()["requests_aborted"] == 2
    assert a.is_set() and b.is_set()


def test_new_request_does_not_clear_another_requests_abort(black):
    # Regression for the old module-level flag that every new request reset.
    flagged = threading.Event()
    flagged.set()
    scenes_router._active_requests["other"] = flagged
    try:
        assert client.post("/scenes/generate", json=body(black)).status_code == 200
        assert flagged.is_set()
    finally:
        scenes_router._active_requests.pop("other", None)


def test_aborted_request_returns_early_without_scenes(black, monkeypatch):
    real = threading.Event

    def pre_set():
        e = real()
        e.set()
        return e

    stub = types.SimpleNamespace(Event=pre_set, Lock=threading.Lock)
    monkeypatch.setattr(scenes_router, "threading", stub)
    r = client.post("/scenes/generate", json=body(black, count=3))
    assert r.status_code == 200
    assert r.json()["scenes"] == []
    assert r.json()["stats"]["growth_stopped_reason"] == "aborted"


def test_duplicate_inflight_request_id_conflicts(black, monkeypatch):
    monkeypatch.setitem(scenes_router._active_requests, "dup", threading.Event())
    assert client.post("/scenes/generate", json=body(black, request_id="dup")).status_code == 409


def test_active_registry_is_cleaned_up(black):
    client.post("/scenes/generate", json=body(black, request_id="cleanup"))
    assert "cleanup" not in scenes_router._active_requests
