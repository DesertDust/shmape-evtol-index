import os

from fastapi.testclient import TestClient


def make_client(tmp_path):
    os.environ["EVTOL_INDEX_DATABASE_PATH"] = str(tmp_path / "index.db")
    os.environ["EVTOL_INDEX_BASE_PATH"] = "/Shmape-Homepage/evtol-index"
    os.environ["EVTOL_INDEX_ALERTS_ENABLED"] = "false"
    from app.config import clear_settings_cache
    from app.main import create_app

    clear_settings_cache()
    return TestClient(create_app())


def test_public_dashboard_explains_index_and_standard_deviations(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/Shmape-Homepage/evtol-index")

    assert response.status_code == 200
    html = response.text
    assert "Shmape eVTOL Index" in html
    assert "NASDAQ Composite" in html
    assert "NASDAQ-100" in html
    assert "standard deviation" in html.lower()
    assert "free-float" in html.lower()
    assert "not financial advice" in html.lower()
    assert "1D" in html and "YTD" in html and "MAX" in html


def test_company_universe_api_is_public_read_only_and_canonical(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/Shmape-Homepage/evtol-index/api/v1/companies")
        post = client.post("/Shmape-Homepage/evtol-index/api/v1/companies", json={"name": "Injected"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["canonical_source"] == "shmape-evtol-index"
    assert any(row["ticker"] == "ACHR" for row in payload["companies"])
    assert any(row["ticker"] == "JOBY" for row in payload["companies"])
    assert post.status_code == 405


def test_snapshot_api_has_index_benchmarks_constituents_and_methodology(tmp_path) -> None:
    with make_client(tmp_path) as client:
        payload = client.get("/Shmape-Homepage/evtol-index/api/v1/snapshot").json()

    assert payload["index"]["name"] == "Shmape eVTOL Index"
    assert {row["symbol"] for row in payload["benchmarks"]} == {"^IXIC", "QQQ"}
    assert payload["methodology"]["weight_cap"] == 0.15
    assert payload["alerts"]["enabled"] is False


def test_health_endpoint_reports_data_freshness_without_secrets(tmp_path) -> None:
    with make_client(tmp_path) as client:
        payload = client.get("/Shmape-Homepage/evtol-index/api/v1/health").json()

    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"] == "ok"
    assert "password" not in str(payload).lower()
