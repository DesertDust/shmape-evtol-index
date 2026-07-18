from app.services.discovery import DiscoveryCandidate, score_candidate


def test_material_public_evtol_candidate_auto_qualifies() -> None:
    candidate = DiscoveryCandidate(
        name="Example Air Mobility",
        ticker="EAM",
        exchange="NASDAQ",
        is_public=True,
        description="Develops and certifies passenger electric vertical takeoff and landing aircraft and operates an air mobility platform.",
        evidence_urls=("https://example.com/investors", "https://www.sec.gov/example"),
    )

    decision = score_candidate(candidate)

    assert decision.auto_include is True
    assert decision.score >= 80
    assert "public listing" in decision.reasons
    assert "material eVTOL activity" in decision.reasons


def test_generic_aerospace_company_does_not_auto_qualify() -> None:
    candidate = DiscoveryCandidate(
        name="Example Conglomerate",
        ticker="BIG",
        exchange="NYSE",
        is_public=True,
        description="A diversified industrial and aerospace manufacturer with one experimental urban air mobility investment.",
        evidence_urls=("https://example.com",),
    )

    decision = score_candidate(candidate)

    assert decision.auto_include is False
    assert decision.score < 80


def test_private_company_never_enters_public_database() -> None:
    candidate = DiscoveryCandidate(
        name="Private eVTOL",
        ticker="",
        exchange="",
        is_public=False,
        description="Pure-play electric vertical takeoff and landing aircraft developer.",
        evidence_urls=("https://example.com",),
    )

    assert score_candidate(candidate).auto_include is False
