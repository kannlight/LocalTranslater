import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def ollama_stream(*chunks: str, thinking: str = "") -> bytes:
    lines = []
    if thinking:
        lines.append({"message": {"role": "assistant", "content": "", "thinking": thinking}, "done": False})
    lines += [{"message": {"role": "assistant", "content": c}, "done": False} for c in chunks]
    lines.append({"message": {"role": "assistant", "content": ""}, "done": True, "eval_count": 3, "total_duration": 2_000_000_000})
    return b"".join(json.dumps(line).encode() + b"\n" for line in lines)


def make_client(handler, password="secret", **kwargs) -> TestClient:
    settings = Settings(password=password, secret_key="k" * 32, **kwargs)
    return TestClient(create_app(settings, transport=httpx.MockTransport(handler)))


def events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line]


def login(client, password="secret"):
    return client.post("/api/login", json={"password": password})


@pytest.fixture
def captured():
    return {}


@pytest.fixture
def ok_handler(captured):
    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=ollama_stream("Hello", ", world"))
    return handler


def test_index_is_public(ok_handler):
    with make_client(ok_handler) as c:
        assert c.get("/").status_code == 200
        assert c.get("/static/app.js").status_code == 200


def test_api_requires_login(ok_handler):
    with make_client(ok_handler) as c:
        assert c.get("/api/session").json() == {"authenticated": False, "auth_required": True}
        assert c.get("/api/config").status_code == 401
        assert c.post("/api/translate", json={"text": "x", "target": "en"}).status_code == 401


def test_wrong_password_and_lockout(ok_handler):
    with make_client(ok_handler) as c:
        for _ in range(5):
            assert login(c, "nope").status_code == 401
        # Locked out now, even with the correct password.
        r = login(c)
        assert r.status_code == 429
        assert r.json()["retry_after"] > 0


def test_login_then_config(ok_handler):
    with make_client(ok_handler) as c:
        assert login(c).status_code == 200
        assert c.get("/api/session").json()["authenticated"] is True
        cfg = c.get("/api/config").json()
        codes = [lang["code"] for lang in cfg["languages"]]
        assert codes[:4] == ["ja", "en", "zh-Hans", "zh-Hant"]
        assert 30 <= len(codes) <= 40
        assert cfg["model"] == "gemma4:26b"


def test_logout(ok_handler):
    with make_client(ok_handler) as c:
        login(c)
        c.post("/api/logout")
        assert c.get("/api/config").status_code == 401


def test_tampered_cookie_rejected(ok_handler):
    with make_client(ok_handler) as c:
        login(c)
        token = c.cookies.get("lt_session")
        expires, sig = token.split(".")
        c.cookies.set("lt_session", f"{int(expires) + 1000}.{sig}")
        assert c.get("/api/config").status_code == 401


def test_no_password_disables_auth(ok_handler):
    with make_client(ok_handler, password="") as c:
        assert c.get("/api/config").status_code == 200
        # And no password logs you in.
        assert login(c, "").status_code == 401


def test_translate_streams(ok_handler, captured):
    with make_client(ok_handler) as c:
        login(c)
        r = c.post("/api/translate", json={"text": "こんにちは", "source": "ja", "target": "en", "instruction": "Be formal"})
        assert r.status_code == 200
        ev = events(r)
        assert ev[0] == {"status": "started"}
        assert "".join(e.get("delta", "") for e in ev) == "Hello, world"
        assert ev[-1]["done"] is True
        assert ev[-1]["total_duration_ms"] == 2000

    body = captured["body"]
    assert captured["path"] == "/api/chat"
    assert body["model"] == "gemma4:26b"
    assert body["stream"] is True
    assert "think" not in body
    assert "from Japanese into English" in body["messages"][0]["content"]
    assert "Be formal" in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": "こんにちは"}


def test_translate_auto_detect_and_think_option(captured, ok_handler):
    with make_client(ok_handler, think=False) as c:
        login(c)
        c.post("/api/translate", json={"text": "hi", "source": "auto", "target": "zh-Hant"})
    assert "Detect the language" in captured["body"]["messages"][0]["content"]
    assert "Traditional Chinese" in captured["body"]["messages"][0]["content"]
    assert captured["body"]["think"] is False


def test_thinking_tokens_not_forwarded():
    def handler(request):
        return httpx.Response(200, content=ollama_stream("Bonjour", thinking="let me think"))

    with make_client(handler) as c:
        login(c)
        ev = events(c.post("/api/translate", json={"text": "Hello", "target": "fr"}))
    assert "".join(e.get("delta", "") for e in ev) == "Bonjour"
    assert "let me think" not in json.dumps(ev)


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"text": "  ", "target": "en"}, 400),
        ({"text": "x", "target": "xx"}, 400),
        ({"text": "x", "source": "xx", "target": "en"}, 400),
        ({"text": "x", "target": "auto"}, 400),
        ({"text": "x" * 101, "target": "en"}, 413),
        ({"text": "x", "target": "en", "instruction": "y" * 11}, 413),
    ],
)
def test_translate_validation(ok_handler, payload, status):
    with make_client(ok_handler, max_input_chars=100, max_instruction_chars=10) as c:
        login(c)
        assert c.post("/api/translate", json=payload).status_code == status


def test_ollama_http_error():
    def handler(request):
        return httpx.Response(404, json={"error": "model 'gemma4:26b' not found"})

    with make_client(handler) as c:
        login(c)
        ev = events(c.post("/api/translate", json={"text": "x", "target": "en"}))
    assert "not found" in ev[-1]["error"]


def test_ollama_unreachable():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with make_client(handler) as c:
        login(c)
        ev = events(c.post("/api/translate", json={"text": "x", "target": "en"}))
    assert "Cannot connect" in ev[-1]["error"]


def test_ollama_error_mid_stream():
    def handler(request):
        content = json.dumps({"message": {"content": "Hal"}, "done": False}) + "\n" + json.dumps({"error": "out of memory"}) + "\n"
        return httpx.Response(200, content=content.encode())

    with make_client(handler) as c:
        login(c)
        ev = events(c.post("/api/translate", json={"text": "x", "target": "en"}))
    assert ev[-1] == {"error": "out of memory"}
