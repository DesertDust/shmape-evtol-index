from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.repository import Repository
from app.services.discovery import DiscoveryCandidate, score_candidate
from app.services.market_data import MarketDataClient


SEC_USER_AGENT = "Shmape eVTOL Index tom1giro@gmail.com"
SEARCH_TERMS = (
    "electric vertical takeoff",
    "electric vertical take-off",
    "advanced air mobility",
    "eVTOL",
)


class SecDiscoveryService:
    def __init__(self, repository: Repository, market_client: MarketDataClient, timeout: int = 30) -> None:
        self.repository = repository
        self.market_client = market_client
        self.timeout = timeout

    def run(self) -> dict:
        listed = self._listed_companies()
        hits: dict[str, dict] = defaultdict(lambda: {"terms": set(), "evidence": set(), "dates": [], "sics": set()})
        for term in SEARCH_TERMS:
            for filing in self._search_filings(term):
                cik = filing["cik"]
                if cik not in listed:
                    continue
                hits[cik]["terms"].add(term)
                hits[cik]["evidence"].add(filing["url"])
                hits[cik]["dates"].append(filing["date"])
                hits[cik]["sics"].update(filing["sics"])
            time.sleep(0.12)

        existing = {row["ticker"] for row in self.repository.list_companies()}
        included = 0
        audited = 0
        for cik, evidence in hits.items():
            company = listed[cik]
            description = "Public filings repeatedly reference " + ", ".join(sorted(evidence["terms"])) + "."
            candidate = DiscoveryCandidate(
                name=company["title"],
                ticker=company["ticker"],
                exchange=company["exchange"],
                is_public=True,
                description=description,
                evidence_urls=tuple(sorted(evidence["evidence"])),
            )
            decision = score_candidate(candidate)
            fingerprint = hashlib.sha256(f"sec:{cik}".encode()).hexdigest()
            candidate_row = {
                "name": candidate.name,
                "ticker": candidate.ticker,
                "exchange": candidate.exchange,
                "evidence_urls": candidate.evidence_urls,
            }
            material_name = bool(re.search(r"\b(aviation|aircraft|aerospace|air mobility)\b", candidate.name, re.I))
            qualifies = (
                decision.score >= 90
                and "3721" in evidence["sics"]
                and len(evidence["terms"]) >= 2
                and material_name
            )
            state = "already-tracked" if candidate.ticker in existing else ("auto-included" if qualifies else "observed")
            self.repository.record_discovery(fingerprint, candidate_row, decision.score, state, decision.reasons)
            audited += 1
            if qualifies and candidate.ticker not in existing:
                try:
                    self.repository.upsert_discovered_company(self._company_row(candidate, evidence["dates"]))
                    existing.add(candidate.ticker)
                    included += 1
                except Exception:
                    self.repository.record_discovery(fingerprint, candidate_row, decision.score, "provider-validation-failed", decision.reasons)
        return {"audited": audited, "auto_included": included, "terms": list(SEARCH_TERMS)}

    def _company_row(self, candidate: DiscoveryCandidate, filing_dates: list[str]) -> dict:
        metadata = self.market_client.fetch_metadata(candidate.ticker)
        first_trade = metadata.get("firstTradeDate")
        listing_date = datetime.fromtimestamp(first_trade, tz=timezone.utc).date().isoformat() if first_trade else min(filing_dates)
        evidence = candidate.evidence_urls[0]
        slug = re.sub(r"[^a-z0-9]+", "-", candidate.name.lower()).strip("-")
        return {
            "slug": slug,
            "legal_name": candidate.name,
            "display_name": re.sub(r"\s+(inc\.?|ltd\.?|plc|corp\.?)$", "", candidate.name, flags=re.I),
            "ticker": candidate.ticker,
            "yahoo_symbol": candidate.ticker,
            "exchange": metadata.get("fullExchangeName") or candidate.exchange,
            "country": "Unverified",
            "currency": metadata.get("currency", "USD"),
            "category": "automatically-discovered",
            "listing_date": listing_date,
            "delisting_date": None,
            "listing_status": "active",
            "website_url": evidence,
            "investor_relations_url": evidence,
            "career_url": "",
            "materiality_summary": candidate.description,
            "evidence_url": evidence,
            "free_float_factor": 1.0,
            "float_factor_status": "automatic-placeholder",
        }

    def _listed_companies(self) -> dict[str, dict]:
        payload = self._json("https://www.sec.gov/files/company_tickers_exchange.json")
        fields = payload["fields"]
        candidates: dict[str, list[dict]] = defaultdict(list)
        for row in payload["data"]:
            item = dict(zip(fields, row))
            ticker = str(item.get("ticker") or "")
            exchange = str(item.get("exchange") or "")
            if not ticker or not exchange or re.search(r"[-./](W|WS|WT|U|R)$", ticker):
                continue
            candidates[str(item["cik"]).zfill(10)].append({
                "title": item["name"], "ticker": ticker, "exchange": exchange,
            })
        return {
            cik: min(rows, key=lambda row: (bool(re.search(r"(?:-WT|-WS|W|WS)$", row["ticker"])), len(row["ticker"])))
            for cik, rows in candidates.items()
        }

    def _search_filings(self, term: str) -> list[dict]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=730)
        params = urlencode({
            "q": f'"{term}"', "dateRange": "custom", "startdt": start.isoformat(),
            "enddt": end.isoformat(), "from": 0, "size": 200,
        })
        payload = self._json(f"https://efts.sec.gov/LATEST/search-index?{params}")
        rows = []
        for hit in payload.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            ciks = source.get("ciks") or []
            accession = str(source.get("adsh") or "")
            if not ciks or not accession:
                continue
            cik = str(ciks[0]).zfill(10)
            accession_path = accession.replace("-", "")
            rows.append({
                "cik": cik,
                "date": source.get("file_date"),
                "sics": tuple(source.get("sics") or ()),
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/",
            })
        return rows

    def _json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"})
        with urlopen(request, timeout=self.timeout) as response:
            data = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return json.loads(data)
