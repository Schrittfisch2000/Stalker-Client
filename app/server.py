from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import current_user, router as auth_router
from .main import app

app.include_router(auth_router)


@app.middleware("http")
async def benutzer_schutz(request: Request, call_next):
    path = request.url.path
    public = (
        path == "/"
        or path == "/health"
        or path.startswith("/static/")
        or path.startswith("/api/auth/")
    )
    if public:
        return await call_next(request)

    if not current_user(request):
        if path.startswith("/api/") or path.startswith("/hls/") or path.startswith("/stream/"):
            return JSONResponse({"detail": "Bitte anmelden"}, status_code=401)
        return JSONResponse({"detail": "Bitte anmelden"}, status_code=401)

    if path in {"/api/config"} and request.method in {"PUT", "POST", "DELETE"}:
        user = current_user(request)
        if not user or user.get("role") != "admin":
            return JSONResponse({"detail": "Nur Administratoren dürfen die Portal-Einstellungen ändern"}, status_code=403)

    return await call_next(request)
