# Hermès Scout

Watcher for "optimally damaged" Hermès **Birkin / Kelly** listings across EU marketplaces. Estimates post-restoration margin (CZK), deduplicates, and alerts only on new pieces under a price ceiling. Ships with a daily multi-market HTML report generator.

> CZ: Hlídač „optimálně poškozených" Hermès Birkin/Kelly inzerátů na EU marketech. Odhad marže po renovaci, deduplikace, alerty + denní multi-market report.

## Components
- `scout.py` — core watcher: eBay via official **Browse API**, Kleinanzeigen (HTML), pluggable parsers; margin estimation; dedup; email/file/stdout alerts; offline self-test.
- `report/hermes_report_builder.py` — deterministic builder that turns scraped data (`hermes_scan_data.json`) into a light HTML report: TOP-10 Birkin/Kelly, EU/Japan toggles, market-coverage panel, and "new since last run" diffing.
- `config.yaml` — FX rates, resale estimates, price ceiling, filters, sources.
- `EBAY_API_SETUP.md` — how to get free eBay Browse API keys.
- `native_alerts.md` — ready-made saved-search alerts (eBay, Vestiaire, Leboncoin, Buyee).

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scout.py --selftest   # offline test (no network)
python3 scout.py --dry-run    # live scan, no state write
```
Set eBay API keys (see `EBAY_API_SETUP.md`) and copy `.env.example` → `.env`.

## Approach
- Prefer official APIs (eBay Browse) and clean parsers (e.g. `__NEXT_DATA__` for JS sites) over fragile scraping.
- Filter by a **price ceiling**, not damage keywords — sellers don't title damaged bags "as is".
- Respect site terms and use polite pacing. No bot-detection evasion.

## License
MIT — see `LICENSE`.
