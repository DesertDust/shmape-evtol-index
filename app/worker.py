from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.index_service import IndexService
from app.repository import Repository
from app.services.discovery_scan import SecDiscoveryService
from app.services.market_data import MarketDataClient


ROOT = Path(__file__).resolve().parent


def bootstrap() -> tuple[Repository, IndexService, MarketDataClient]:
    settings = get_settings()
    repository = Repository(settings.database_path)
    repository.initialize()
    repository.seed_companies(ROOT / "data" / "companies.json")
    return repository, IndexService(repository, settings), MarketDataClient(settings.market_data_user_agent)


def main() -> None:
    parser = argparse.ArgumentParser(description="Operate the Shmape eVTOL Index data pipeline")
    parser.add_argument("command", choices=("refresh", "rebuild", "discover", "bootstrap"))
    args = parser.parse_args()
    repository, service, market_client = bootstrap()
    if args.command == "refresh":
        result = service.refresh_market_data(market_client)
    elif args.command == "rebuild":
        rows = service.rebuild_index()
        result = {"status": "ok", "index_levels": len(rows)}
    elif args.command == "discover":
        result = SecDiscoveryService(repository, market_client).run()
    else:
        result = {"status": "ok", "companies": len(repository.list_companies())}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
