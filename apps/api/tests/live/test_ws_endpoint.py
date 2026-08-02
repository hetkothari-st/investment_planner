"""The browser-facing websocket: snapshot → ticks/heartbeats, and the
docs/02 rule that no credential material ever reaches the browser."""

import json

from starlette.testclient import TestClient

from corpus.api.main import create_app

CREDENTIAL_MARKERS = ("api_key", "apikey", "access_token", "secret", "authorization")


def scan_for_credentials(payload) -> list[str]:
    hits: list[str] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower()
                if any(m in lk for m in CREDENTIAL_MARKERS):
                    hits.append(f"{path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            if any(m in node.lower() for m in CREDENTIAL_MARKERS):
                hits.append(f"{path}={node[:40]}")

    walk(payload, "$")
    return hits


def test_ws_streams_and_carries_no_credentials(monkeypatch):
    monkeypatch.setenv("CORPUS_FEED", "replay")
    monkeypatch.setenv("CORPUS_REPLAY_INTERVAL_S", "0.01")
    monkeypatch.setenv("KITE_API_KEY", "supersecret-key-should-never-appear")
    with TestClient(create_app()) as client:
        status = client.get("/live/status").json()
        assert status["feed"] == "replay"
        assert scan_for_credentials(status) == []

        with client.websocket_connect("/live/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "snapshot"
            messages = [first] + [ws.receive_json() for _ in range(25)]

    kinds = {m["type"] for m in messages}
    assert "tick" in kinds
    ticks = [m for m in messages if m["type"] == "tick"]
    assert all(
        set(t) == {"type", "instrument_token", "last_price", "change_pct", "received_at"}
        for t in ticks
    )
    offenders = scan_for_credentials(json.loads(json.dumps(messages)))
    assert offenders == []


def test_ws_when_feed_off_states_the_fact(monkeypatch):
    monkeypatch.setenv("CORPUS_FEED", "off")
    with TestClient(create_app()) as client:
        assert client.get("/live/status").json()["status"] == "OFF"
        with client.websocket_connect("/live/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "state" and first["status"] == "OFF"
            assert "CORPUS_FEED" in first["detail"]


def test_overview_without_feed_is_an_explained_empty(monkeypatch):
    monkeypatch.setenv("CORPUS_FEED", "off")
    with TestClient(create_app()) as client:
        body = client.get("/live/overview").json()
        assert body["indices"] == [] and body["gainers"] == []
        assert body["message"]
