import json
from urllib.parse import urlsplit

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def _send_json(send, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"connection", b"close"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Limita o corpo da requisicao pelo Content-Length e tambem contando os bytes
    recebidos, o que cobre uploads com Transfer-Encoding: chunked."""

    def __init__(self, app, max_bytes: int, max_mb: int):
        self.app = app
        self.max_bytes = max_bytes
        self.message = {"error": f"Arquivo excede o limite de {max_mb} MB"}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        return await _send_json(send, 413, self.message)
                except ValueError:
                    return await _send_json(send, 400, {"error": "Content-Length invalido"})

        received = 0
        rejected = False
        response_started = False

        async def limited_receive():
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    if not response_started:
                        await _send_json(send, 413, self.message)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal response_started
            if rejected:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not rejected:
                raise


def _host_of(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


class CSRFMiddleware:
    """Recusa requisicoes que alteram estado vindas de outra origem.
    Aceita a origem do proprio host (Host ou X-Forwarded-Host) e as listadas em CORS_ORIGINS."""

    def __init__(self, app, trusted_origins: list[str]):
        self.app = app
        self.trusted_hosts = {_host_of(o) for o in trusted_origins if _host_of(o)}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        source = headers.get("origin") or headers.get("referer")
        if source:
            allowed = set(self.trusted_hosts)
            if headers.get("host"):
                allowed.add(headers["host"].lower())
            forwarded = headers.get("x-forwarded-host", "").split(",")[0].strip().lower()
            if forwarded:
                allowed.add(forwarded)
            if source == "null" or _host_of(source) not in allowed:
                return await _send_json(send, 403, {"error": "Origem da requisicao invalida"})

        return await self.app(scope, receive, send)
