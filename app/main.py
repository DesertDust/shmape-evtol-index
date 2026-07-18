from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import clear_settings_cache, get_settings
from app.index_service import IndexService
from app.repository import Repository


ROOT = Path(__file__).resolve().parent
RANGES = {"1D", "1W", "1M", "3M", "YTD", "1Y", "MAX"}


def create_app() -> FastAPI:
    clear_settings_cache()
    settings = get_settings()
    repository = Repository(settings.database_path)
    service = IndexService(repository, settings)
    templates = Jinja2Templates(directory=str(ROOT / "templates"))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        repository.seed_companies(ROOT / "data" / "companies.json")
        yield

    app = FastAPI(
        title="Shmape eVTOL Index",
        description="Transparent public-equity index and canonical eVTOL company universe",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.repository = repository
    app.state.index_service = service
    app.mount("/assets", StaticFiles(directory=str(ROOT / "static")), name="assets")
    if settings.base_path:
        app.mount(f"{settings.base_path}/assets", StaticFiles(directory=str(ROOT / "static")), name="prefixed-assets")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.url.path.endswith("/api/v1/health"):
            response.headers["Cache-Control"] = "no-store"
        elif "/api/" in request.url.path:
            response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
        return response

    prefixes = ("", settings.base_path) if settings.base_path else ("",)
    for prefix in dict.fromkeys(prefixes):
        register_routes(app, prefix, templates, repository, service, settings.base_path)
    return app


def register_routes(
    app: FastAPI,
    prefix: str,
    templates: Jinja2Templates,
    repository: Repository,
    service: IndexService,
    public_base_path: str,
) -> None:
    route_key = (prefix or "root").replace("/", "-")

    @app.get(prefix or "/", response_class=HTMLResponse, name=f"dashboard-{route_key}")
    def dashboard(request: Request):
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"base_path": public_base_path, "launch_date": "18 July 2026"},
        )

    @app.get(f"{prefix}/api/v1/health", name=f"health-{route_key}")
    def health():
        try:
            company_count = len(repository.list_companies())
            latest_sync = repository.latest_sync("market-data")
            status = "ok" if latest_sync and latest_sync["status"] == "ok" else "degraded"
            return {
                "status": status,
                "database": "ok",
                "app": "shmape-evtol-index",
                "company_count": company_count,
                "market_data": latest_sync["status"] if latest_sync else "awaiting-first-refresh",
                "last_refresh": latest_sync["finished_at"] if latest_sync else None,
            }
        except Exception:
            return JSONResponse({"status": "failed", "database": "error", "app": "shmape-evtol-index"}, status_code=503)

    @app.get(f"{prefix}/api/v1/companies", name=f"companies-{route_key}")
    def companies(include_historical: bool = True):
        fields = (
            "slug", "legal_name", "display_name", "ticker", "yahoo_symbol", "exchange", "country", "currency",
            "category", "listing_date", "delisting_date", "listing_status", "website_url", "investor_relations_url",
            "career_url", "materiality_summary", "evidence_url", "float_factor_status", "last_verified_at",
        )
        rows = [{key: row[key] for key in fields} for row in repository.list_companies(include_historical)]
        return {
            "schema_version": "1.0",
            "canonical_source": "shmape-evtol-index",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "inclusion_scope": "Public passenger, cargo, and enabling-platform companies where eVTOL is a material business",
            "companies": rows,
        }

    @app.get(f"{prefix}/api/v1/snapshot", name=f"snapshot-{route_key}")
    def snapshot(range_name: str = Query("1M", alias="range")):
        normalized = range_name.upper()
        if normalized not in RANGES:
            return JSONResponse({"error": "unsupported range", "allowed": sorted(RANGES)}, status_code=400)
        return service.snapshot(normalized)

    @app.get(f"{prefix}/api/v1/series", name=f"series-{route_key}")
    def series(range_name: str = Query("1M", alias="range")):
        normalized = range_name.upper()
        if normalized not in RANGES:
            return JSONResponse({"error": "unsupported range", "allowed": sorted(RANGES)}, status_code=400)
        return service.comparison_series(normalized)

    @app.get(f"{prefix}/api/v1/methodology", name=f"methodology-{route_key}")
    def methodology():
        return service.methodology()


app = create_app()
