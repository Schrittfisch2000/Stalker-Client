from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .access import category_allowed, router as access_router
from .auth import current_user, router as auth_router
from .config import PortalConfig, reset_portal_override, set_portal_override
from .diagnostics import install as install_diagnostics
from .downloads import router as downloads_router
from .image_proxy import install as install_image_proxy
from .live_handover import install as install_live_handover
from .live_runtime_fix import install as install_live_runtime_fix
from .live_timeline_v2 import install as install_live_timeline_v2
from .live_timeline_v3 import install as install_live_timeline_v3
from .main import app
from .media_state import router as media_state_router
from .playback_runtime_fix import install as install_playback_runtime_fix
from .portals import router as portals_router, selected_portal
from .safari_hls_fix import install as install_safari_hls_fix
from .storage import ensure_standard_files
from .version import APP_VERSION

ensure_standard_files()
install_safari_hls_fix()
install_live_runtime_fix()
install_live_timeline_v2()
install_live_timeline_v3()
install_playback_runtime_fix()
install_live_handover()
install_diagnostics()
app.version = APP_VERSION
app.include_router(auth_router)
app.include_router(access_router)
app.include_router(media_state_router)
app.include_router(portals_router)
app.include_router(downloads_router)
install_image_proxy(app)

PORTAL_REQUIRED_PATHS = (
    "/api/status",
    "/api/categories/",
    "/api/content/",
    "/api/epg",
    "/api/episodes/",
    "/api/play",
    "/api/download",
    "/api/image",
    "/api/live-refresh/",
    "/api/live-release/",
    "/api/vod-seek/",
    "/download/",
    "/stream/",
    "/hls/",
)


@app.get("/api/version")
async def application_version() -> dict[str, str]:
    return {"name": "Stalker Client", "version": APP_VERSION}


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

    user = current_user(request)
    if not user:
        return JSONResponse({"detail": "Bitte anmelden"}, status_code=401)

    if path == "/api/config":
        if user.get("role") != "admin":
            if request.method in {"PUT", "POST", "DELETE"}:
                return JSONResponse({"detail": "Nur Administratoren dürfen Portal-Zugangsdaten ändern"}, status_code=403)
            return JSONResponse({"configured": True, "portal_url": "", "portal_mac": ""})

    portal = selected_portal(request, user["username"], user["role"])
    requires_portal = any(path == prefix or path.startswith(prefix) for prefix in PORTAL_REQUIRED_PATHS)
    if requires_portal and portal is None:
        return JSONResponse(
            {"detail": "Diesem Benutzer wurde kein Portal zugewiesen. Bitte wende dich an einen Administrator."},
            status_code=403,
        )

    if path.startswith("/api/content/"):
        media_type = path.rsplit("/", 1)[-1]
        category = request.query_params.get("category", "*")
        if media_type in {"itv", "vod", "series"} and not category_allowed(user["username"], user["role"], media_type, category):
            return JSONResponse({"detail": "Diese Kategorie ist für deinen Benutzer nicht freigegeben"}, status_code=403)

    override = None
    if portal:
        override = PortalConfig(
            portal_url=str(portal.get("portal_url", "")),
            portal_mac=str(portal.get("portal_mac", "")),
        )
    token = set_portal_override(override)
    try:
        return await call_next(request)
    finally:
        reset_portal_override(token)
