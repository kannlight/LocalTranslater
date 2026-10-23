"""LocalTranslater: a small web front end that translates text with a local Ollama model."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from .config import Settings
from .languages import AUTO, LANGUAGE_NAMES, LANGUAGES
from .prompt import build_messages

STATIC_DIR = Path(__file__).parent / "static"

log = logging.getLogger("localtranslater")


class LoginRequest(BaseModel):
    password: str


class TranslateRequest(BaseModel):
    text: str
    source: str = AUTO
    target: str
    instruction: str = ""


def _line(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode()


def _ollama_error_message(status: int, body: bytes) -> str:
    try:
        detail = json.loads(body).get("error", "")
    except (ValueError, AttributeError):
        detail = body.decode(errors="replace")[:500]
    return f"Ollama returned HTTP {status}: {detail}".strip()


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or Settings()
    throttle = auth.LoginThrottle()
    semaphore = asyncio.Semaphore(max(1, settings.max_concurrent))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not settings.password:
            log.warning("LT_PASSWORD is not set: authentication is DISABLED")
        app.state.ollama = httpx.AsyncClient(
            base_url=settings.ollama_url,
            transport=transport,
            timeout=httpx.Timeout(settings.request_timeout, connect=10),
        )
        yield
        await app.state.ollama.aclose()

    app = FastAPI(title="LocalTranslater", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def is_authenticated(request: Request) -> bool:
        if not settings.password:
            return True
        return auth.verify_token(settings.secret_key, settings.password, request.cookies.get(auth.COOKIE_NAME))

    def require_auth(request: Request) -> None:
        if not is_authenticated(request):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.get("/api/session")
    async def session(request: Request):
        return {"authenticated": is_authenticated(request), "auth_required": bool(settings.password)}

    @app.post("/api/login")
    async def login(body: LoginRequest, request: Request, response: Response):
        ip = request.client.host if request.client else "unknown"
        wait = throttle.locked_for(ip)
        if wait:
            return JSONResponse({"error": "locked", "retry_after": wait}, status_code=429)
        if not settings.password or not auth.check_password(settings.password, body.password):
            throttle.fail(ip)
            log.warning("failed login from %s", ip)
            return JSONResponse({"error": "invalid_password"}, status_code=401)
        throttle.succeed(ip)
        response.set_cookie(
            auth.COOKIE_NAME,
            auth.issue_token(settings.secret_key, settings.password, settings.session_days),
            max_age=settings.session_days * 86400,
            httponly=True,
            samesite="strict",
        )
        return {"ok": True}

    @app.post("/api/logout")
    async def logout(response: Response):
        response.delete_cookie(auth.COOKIE_NAME)
        return {"ok": True}

    @app.get("/api/config", dependencies=[Depends(require_auth)])
    async def config():
        return {
            "model": settings.model,
            "languages": [{"code": code, "name": name} for code, name in LANGUAGES],
            "max_input_chars": settings.max_input_chars,
            "max_instruction_chars": settings.max_instruction_chars,
        }

    @app.post("/api/translate", dependencies=[Depends(require_auth)])
    async def translate(body: TranslateRequest, request: Request):
        if not body.text.strip():
            raise HTTPException(400, "text is empty")
        if len(body.text) > settings.max_input_chars:
            raise HTTPException(413, f"text is longer than {settings.max_input_chars} characters")
        if len(body.instruction) > settings.max_instruction_chars:
            raise HTTPException(413, f"instruction is longer than {settings.max_instruction_chars} characters")
        if body.target not in LANGUAGE_NAMES:
            raise HTTPException(400, "unknown target language")
        if body.source != AUTO and body.source not in LANGUAGE_NAMES:
            raise HTTPException(400, "unknown source language")

        options: dict = {"temperature": settings.temperature, "num_ctx": settings.num_ctx}
        payload: dict = {
            "model": settings.model,
            "messages": build_messages(body.text, body.source, body.target, body.instruction),
            "stream": True,
            "options": options,
            "keep_alive": settings.keep_alive,
        }
        if settings.think is not None:
            payload["think"] = settings.think

        client: httpx.AsyncClient = request.app.state.ollama

        async def stream():
            # Events, one JSON object per line:
            #   {"status": "queued"} / {"status": "started"} / {"delta": "..."} / {"done": true, ...} / {"error": "..."}
            if semaphore.locked():
                yield _line({"status": "queued"})
            async with semaphore:
                yield _line({"status": "started"})
                try:
                    async with client.stream("POST", "/api/chat", json=payload) as r:
                        if r.status_code != 200:
                            yield _line({"error": _ollama_error_message(r.status_code, await r.aread())})
                            return
                        async for raw in r.aiter_lines():
                            if not raw.strip():
                                continue
                            data = json.loads(raw)
                            if data.get("error"):
                                yield _line({"error": str(data["error"])})
                                return
                            # Thinking tokens (message.thinking) are deliberately not forwarded.
                            content = (data.get("message") or {}).get("content")
                            if content:
                                yield _line({"delta": content})
                            if data.get("done"):
                                yield _line({
                                    "done": True,
                                    "eval_count": data.get("eval_count"),
                                    "total_duration_ms": (data.get("total_duration") or 0) // 1_000_000,
                                })
                                return
                    yield _line({"error": "Ollama closed the stream unexpectedly"})
                except httpx.ConnectError:
                    yield _line({"error": f"Cannot connect to Ollama at {settings.ollama_url}"})
                except httpx.TimeoutException:
                    yield _line({"error": "Ollama timed out"})
                except (httpx.HTTPError, ValueError) as e:
                    log.exception("translation failed")
                    yield _line({"error": f"Translation failed: {e}"})

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
