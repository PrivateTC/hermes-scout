#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermès Scout — hlídač "optimálně poškozených" Birkin / Kelly inzerátů.

Zdroje (vrstvy):
  - eBay přes OFICIÁLNÍ Browse API (provider: ebay_api) — robustní, neblokuje.
    Klíče z prostředí: EBAY_APP_ID, EBAY_CERT_ID. Bez klíče se zdroj tiše přeskočí.
  - Kleinanzeigen / eBay HTML (parser: kleinanzeigen | ebay) — scraping, křehčí.
  - JS-heavy weby (Vestiaire, Buyee) — viz README, vyžadují Playwright / nativní alerty.

Pipeline:
  1. Získá inzeráty (API nebo HTML).
  2. Vyfiltruje šum a padělky (exclude_keywords), nechá jen Birkin/Kelly.
  3. Odhadne marži po renovaci (resale - cena - oprava) v CZK.
  4. Deduplikuje proti state/seen.json, nahlásí jen NOVÉ kusy pod cenovým stropem.
  5. Pošle alert (e-mail / soubor / stdout) a zaloguje do logs/listings.jsonl.

Spuštění:
    python3 scout.py              # ostrý běh
    python3 scout.py --selftest   # offline test parseru a logiky (bez sítě)
    python3 scout.py --dry-run    # běh bez zápisu do seen.json

Závislosti: requests, beautifulsoup4, pyyaml   (viz requirements.txt)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    import yaml
    from bs4 import BeautifulSoup
except ImportError as e:  # pragma: no cover
    requests = None  # type: ignore
    if "--selftest" not in sys.argv:
        print(f"Chybí závislost: {e}. Spusť: pip install -r requirements.txt", file=sys.stderr)
        raise

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"
LOG_DIR = BASE_DIR / "logs"
SEEN_FILE = STATE_DIR / "seen.json"
LOG_FILE = LOG_DIR / "listings.jsonl"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# --------------------------------------------------------------------------
# Pomocné: cena a měna
# --------------------------------------------------------------------------
CURRENCY_SYMBOLS = {"€": "EUR", "£": "GBP", "$": "USD", "Kč": "CZK"}
CURRENCY_CODES = ("EUR", "GBP", "USD", "CZK", "JPY")


def parse_price(raw: str) -> tuple[float | None, str | None]:
    """Z textu typu 'EUR 1.234,56' nebo '£1,234.00' vytáhne (částka, měna)."""
    if not raw:
        return None, None
    text = raw.strip()
    currency = None
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in text:
            currency = code
            break
    if currency is None:
        for code in CURRENCY_CODES:
            if code in text.upper():
                currency = code
                break
    # vytáhni číslo
    num = re.sub(r"[^\d.,]", "", text)
    if not num:
        return None, currency
    # normalizace oddělovačů: poslední , nebo . je desetinný
    if "," in num and "." in num:
        if num.rfind(",") > num.rfind("."):      # 1.234,56  -> evropský
            num = num.replace(".", "").replace(",", ".")
        else:                                     # 1,234.56  -> anglický
            num = num.replace(",", "")
    elif "," in num:
        # 1234,56 (desetinná) vs 1,234 (tisíce) – heuristika: 2 číslice za čárkou = desetinná
        if re.search(r",\d{2}$", num):
            num = num.replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "." in num:
        # jen tečka: 1.250 / 9.800 (tisíce) vs 12.50 (desetinná).
        # víc teček = tisíce; jediná tečka s 3 číslicemi na konci = tisíce.
        if num.count(".") > 1:
            num = num.replace(".", "")
        elif re.search(r"\.\d{3}$", num):
            num = num.replace(".", "")
        # jinak ponech tečku jako desetinnou (12.50 -> 12.5)
    try:
        return float(num), currency
    except ValueError:
        return None, currency


def to_czk(amount: float, currency: str | None, fx: dict) -> float | None:
    if amount is None:
        return None
    if currency in (None, "CZK"):
        return amount if currency == "CZK" else None
    rate = fx.get(f"{currency}_CZK")
    return round(amount * rate) if rate else None


# --------------------------------------------------------------------------
# Filtrování a odhad marže
# --------------------------------------------------------------------------
def title_passes(title: str, cfg: dict) -> bool:
    t = title.lower()
    if not ("birkin" in t or "kelly" in t):
        return False
    if "hermes" not in t and "hermès" not in t:
        return False
    for bad in cfg.get("exclude_keywords", []):
        if bad.lower() in t:
            return False
    if cfg.get("require_damage_keyword"):
        if not any(k.lower() in t for k in cfg.get("damage_keywords", [])):
            return False
    return True


def estimate_resale_czk(title: str, cfg: dict) -> int | None:
    t = title.lower()
    table = cfg.get("resale_estimates_czk", {})
    for key in sorted(table, key=len, reverse=True):   # nejkonkrétnější první
        if key.lower() in t:
            return table[key]
    return None


def assess(listing: dict, cfg: dict) -> dict:
    """Doplní CZK cenu, odhad prodeje, marži a flag."""
    fx = cfg.get("fx", {})
    price_czk = to_czk(listing.get("price"), listing.get("currency"), fx)
    resale = estimate_resale_czk(listing.get("title", ""), cfg)
    repair = cfg.get("default_repair_cost_czk", 0)
    margin = None
    if price_czk is not None and resale is not None:
        margin = resale - price_czk - repair
    flag = "PROVĚŘIT"
    if margin is not None and margin >= cfg.get("buy_flag_margin_czk", 1e9):
        flag = "KOUPIT"
    listing.update(
        price_czk=price_czk,
        resale_est_czk=resale,
        margin_est_czk=margin,
        flag=flag,
    )
    return listing


def worth_alert(listing: dict, cfg: dict) -> bool:
    # cenový strop: drahé kusy ven, i když model/marže neznámé
    mx = cfg.get("max_price_czk")
    p = listing.get("price_czk")
    if mx and p is not None and p > mx:
        return False
    m = listing.get("margin_est_czk")
    if m is None:
        return True   # neznámá marže (chybí cena/model) – radši nahlásit k ruční kontrole
    return m >= cfg.get("min_margin_czk", 0)


# --------------------------------------------------------------------------
# Detekce blokace a "0 výsledků" (anti-bot / eBay fallback "míň slov")
# --------------------------------------------------------------------------
BLOCK_MARKERS = (
    "pardon our interruption", "captcha", "unusual traffic", "access denied",
    "are you a human", "robot check", "verify you are a human", "zugriff verweigert",
)
ZERO_RESULT_MARKERS = (
    "0 ergebnisse", "0 results", "no exact matches", "keine exakten treffer",
    "results matching fewer words", "ergebnisse für weniger suchbegriffe",
)


def looks_blocked(html: str) -> str | None:
    """Vrátí důvod, pokud stránka vypadá blokovaná/prázdná, jinak None."""
    if html is None:
        return "prázdná odpověď"
    low = html.lower()
    if len(low) < 1500:
        return "podezřele krátká odpověď"
    for m in BLOCK_MARKERS:
        if m in low:
            return f"anti-bot marker: {m}"
    return None


def looks_zero_results(html: str) -> bool:
    """eBay vrací 0 výsledků a pak podstrčí plnocenné kusy ('míň slov') – past."""
    low = (html or "").lower()
    return any(m in low for m in ZERO_RESULT_MARKERS)


# --------------------------------------------------------------------------
# Parsery HTML webů
# --------------------------------------------------------------------------
def _ebay_item_id(url: str) -> str:
    m = re.search(r"/itm/(?:[^/]+/)?(\d{9,})", url)
    return m.group(1) if m else url.split("?")[0]


def parse_ebay(html: str, site: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select("li.s-item, li.s-card"):
        a = li.select_one("a.s-item__link, a.s-card__link, a[href*='/itm/']")
        title_el = li.select_one(".s-item__title, .s-card__title, [role='heading']")
        price_el = li.select_one(".s-item__price, .s-card__price")
        if not a or not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        if title.lower().startswith("shop on ebay"):
            continue
        url = a.get("href", "").split("?")[0]
        if "/itm/" not in url:
            continue
        price, cur = parse_price(price_el.get_text(strip=True) if price_el else "")
        out.append({
            "id": f"ebay:{_ebay_item_id(url)}",
            "site": site,
            "title": title,
            "url": url,
            "price": price,
            "currency": cur,
        })
    return out


def parse_kleinanzeigen(html: str, site: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select("article.aditem, li.ad-listitem article"):
        href = art.get("data-href") or ""
        a = art.select_one("a.ellipsis, h2 a, .text-module-begin a")
        if a and not href:
            href = a.get("href", "")
        title_el = art.select_one("h2 a, a.ellipsis, .text-module-begin")
        price_el = art.select_one(".aditem-main--middle--price-shipping--price, .aditem-main--middle--price")
        if not href or not title_el:
            continue
        url = href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"
        title = title_el.get_text(" ", strip=True)
        price, cur = parse_price(price_el.get_text(strip=True) if price_el else "")
        if cur is None and price is not None:
            cur = "EUR"
        out.append({
            "id": f"klein:{urlparse(url).path}",
            "site": site,
            "title": title,
            "url": url,
            "price": price,
            "currency": cur,
        })
    return out


def parse_todo(html: str, site: str) -> list[dict]:
    raise NotImplementedError(
        f"Parser pro '{site}' není hotový. Web je JS-renderovaný – použij Playwright "
        f"nebo oficiální API (viz README, sekce 'Rozšíření na další weby')."
    )


PARSERS = {
    "ebay": parse_ebay,
    "kleinanzeigen": parse_kleinanzeigen,
    "todo": parse_todo,
}


# --------------------------------------------------------------------------
# eBay Browse API (oficiální, OAuth client-credentials)
# --------------------------------------------------------------------------
EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
MARKET_CURRENCY = {
    "EBAY_DE": "EUR", "EBAY_FR": "EUR", "EBAY_IT": "EUR", "EBAY_ES": "EUR",
    "EBAY_GB": "GBP", "EBAY_US": "USD",
}
_EBAY_TOKEN_CACHE: dict = {}


class EbayAuthMissing(RuntimeError):
    pass


def ebay_token() -> str | None:
    """OAuth token přes client-credentials. None = chybí klíče v prostředí."""
    app_id = os.environ.get("EBAY_APP_ID")
    cert_id = os.environ.get("EBAY_CERT_ID")
    if not app_id or not cert_id:
        return None
    if _EBAY_TOKEN_CACHE.get("exp", 0) > time.time():
        return _EBAY_TOKEN_CACHE.get("tok")
    basic = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
    resp = requests.post(
        EBAY_OAUTH_URL,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": EBAY_SCOPE},
        timeout=25,
    )
    resp.raise_for_status()
    j = resp.json()
    _EBAY_TOKEN_CACHE["tok"] = j["access_token"]
    _EBAY_TOKEN_CACHE["exp"] = time.time() + int(j.get("expires_in", 7200)) - 60
    return _EBAY_TOKEN_CACHE["tok"]


def map_ebay_item(item: dict, site: str) -> dict:
    price = item.get("price") or {}
    val = price.get("value")
    try:
        amount = float(val) if val is not None else None
    except (TypeError, ValueError):
        amount = None
    return {
        "id": f"ebay:{item.get('itemId', '')}",
        "site": site,
        "title": item.get("title", "") or "",
        "url": (item.get("itemWebUrl", "") or "").split("?")[0],
        "price": amount,
        "currency": price.get("currency"),
    }


def ebay_search(token: str, marketplace: str, query: str,
                limit: int = 50, price_max: float | None = None) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace,
        "Content-Type": "application/json",
    }
    params = {"q": query, "limit": str(limit), "sort": "newlyListed"}
    if price_max:
        cur = MARKET_CURRENCY.get(marketplace, "EUR")
        params["filter"] = f"price:[0..{int(price_max)}],priceCurrency:{cur}"
    resp = requests.get(EBAY_BROWSE_URL, headers=headers, params=params, timeout=25)
    resp.raise_for_status()
    return resp.json().get("itemSummaries", []) or []


def collect_ebay_api(site: dict, cfg: dict) -> list[dict]:
    token = ebay_token()
    if token is None:
        raise EbayAuthMissing("chybí EBAY_APP_ID / EBAY_CERT_ID")
    marketplace = site.get("marketplace", "EBAY_DE")
    price_max = site.get("price_max")
    limit = int(site.get("limit", 50))
    out: list[dict] = []
    for q in site.get("queries", []):
        items = ebay_search(token, marketplace, q, limit=limit, price_max=price_max)
        out.extend(map_ebay_item(it, site["name"]) for it in items)
        time.sleep(1)
    return out


# --------------------------------------------------------------------------
# Síť, stav, alerty
# --------------------------------------------------------------------------
def fetch(url: str, timeout: int = 25) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8,fr;q=0.6"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=0), encoding="utf-8")


def log_listings(rows: list[dict]) -> None:
    if not rows:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({**r, "found_at": ts}, ensure_ascii=False) + "\n")


def format_listing(r: dict) -> str:
    price = f"{r['price_czk']:,} Kč".replace(",", " ") if r.get("price_czk") else "cena ?"
    margin = f"{r['margin_est_czk']:,} Kč".replace(",", " ") if r.get("margin_est_czk") is not None else "marže ?"
    return (
        f"[{r['flag']}] {r['site'].upper()} — {r['title'][:90]}\n"
        f"    cena: {price} | odhad marže: {margin} | OVĚŘIT PRAVOST\n"
        f"    {r['url']}"
    )


def build_report(new_rows: list[dict]) -> str:
    if not new_rows:
        return "Žádné nové nálezy."
    eu = [r for r in new_rows if not r["site"].endswith("_jp")]
    jp = [r for r in new_rows if r["site"].endswith("_jp")]
    key = lambda r: (r.get("margin_est_czk") is not None, r.get("margin_est_czk") or 0)
    eu.sort(key=key, reverse=True)
    jp.sort(key=key, reverse=True)
    parts = [f"Hermès Scout — {len(new_rows)} nových nálezů ({datetime.now():%Y-%m-%d %H:%M})", ""]
    if eu:
        parts.append("=== EU (primární) ===")
        parts += [format_listing(r) for r in eu]
    if jp:
        parts.append("")
        parts.append("=== Japonsko (sekundární) ===")
        parts += [format_listing(r) for r in jp]
    return "\n".join(parts)


def send_alert(report: str, cfg: dict) -> None:
    method = cfg.get("alert", {}).get("method", "stdout")
    if method == "stdout":
        print(report)
    elif method == "file":
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        out = LOG_DIR / f"alert_{datetime.now():%Y%m%d_%H%M}.txt"
        out.write_text(report, encoding="utf-8")
        print(f"Alert zapsán do {out}")
    elif method == "email":
        ec = cfg["alert"]["email"]
        user = os.environ.get("SCOUT_SMTP_USER")
        pw = os.environ.get("SCOUT_SMTP_PASS")
        if not user or not pw:
            print("CHYBA: chybí SCOUT_SMTP_USER / SCOUT_SMTP_PASS v prostředí.", file=sys.stderr)
            print(report)
            return
        msg = EmailMessage()
        msg["Subject"] = f"Hermès Scout — nové nálezy ({datetime.now():%H:%M})"
        msg["From"] = ec["from_addr"]
        msg["To"] = ec["to_addr"]
        msg.set_content(report)
        with smtplib.SMTP(ec["smtp_host"], ec["smtp_port"]) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        print("Alert odeslán e-mailem.")


# --------------------------------------------------------------------------
# Hlavní běh
# --------------------------------------------------------------------------
def _process(listings: list[dict], seen: set[str], new_rows: list[dict], cfg: dict) -> None:
    for r in listings:
        if r["id"] in seen:
            continue
        if not title_passes(r["title"], cfg):
            continue
        assess(r, cfg)
        seen.add(r["id"])
        if worth_alert(r, cfg):
            new_rows.append(r)


def run(cfg: dict, dry_run: bool = False) -> list[dict]:
    seen = load_seen()
    new_rows: list[dict] = []
    for site in cfg.get("sites", []):
        if not site.get("enabled"):
            continue
        provider = site.get("provider")

        # --- eBay oficiální API ---
        if provider == "ebay_api":
            try:
                listings = collect_ebay_api(site, cfg)
            except EbayAuthMissing as e:
                print(f"[{site['name']}] přeskočeno ({e}) — zatím bez API klíče.", file=sys.stderr)
                continue
            except Exception as e:
                print(f"[{site['name']}] eBay API selhal: {e}", file=sys.stderr)
                continue
            _process(listings, seen, new_rows, cfg)
            time.sleep(1)
            continue

        # --- HTML scraping ---
        parser = PARSERS.get(site.get("parser", ""), parse_todo)
        for url in site.get("urls", []):
            try:
                html = fetch(url)
            except Exception as e:
                print(f"[{site['name']}] fetch selhal: {e}", file=sys.stderr)
                continue
            blocked = looks_blocked(html)
            if blocked:
                print(f"[{site['name']}] VAROVÁNÍ: stránka vypadá blokovaná ({blocked}) — přeskakuji.", file=sys.stderr)
                continue
            if looks_zero_results(html):
                print(f"[{site['name']}] 0 výsledků (ignoruji eBay fallback 'míň slov').", file=sys.stderr)
                continue
            try:
                listings = parser(html, site["name"])
            except NotImplementedError as e:
                print(f"[{site['name']}] {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"[{site['name']}] parser selhal: {e}", file=sys.stderr)
                continue
            _process(listings, seen, new_rows, cfg)
            time.sleep(2)  # ohleduplné tempo

    log_listings(new_rows)
    if not dry_run:
        save_seen(seen)
    report = build_report(new_rows)
    send_alert(report, cfg)
    return new_rows


def load_config() -> dict:
    return yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Selftest (offline, bez sítě)
# --------------------------------------------------------------------------
EBAY_FIXTURE = """
<ul>
  <li class="s-item"><a class="s-item__link" href="https://www.ebay.de/itm/123456789012?hash=x">
    <div class="s-item__title">Hermès Kelly 28 Togo schwarz, beschädigt, Ecken abgenutzt</div></a>
    <span class="s-item__price">EUR 12.500,00</span></li>
  <li class="s-item"><a class="s-item__link" href="https://www.ebay.de/itm/223456789013">
    <div class="s-item__title">Hermes Birkin 30 - REPLICA inspired style</div></a>
    <span class="s-item__price">199,00 €</span></li>
  <li class="s-item"><a class="s-item__link" href="https://www.ebay.de/itm/323456789014">
    <div class="s-item__title">Hermès Twilly silk scarf</div></a>
    <span class="s-item__price">85,00 €</span></li>
  <li class="s-item"><a class="s-item__link" href="https://www.ebay.co.uk/itm/423456789015">
    <div class="s-item__title">Hermes Birkin 25 as is, needs restoration, corner wear</div></a>
    <span class="s-item__price">£9,800.00</span></li>
</ul>
"""

EBAY_API_FIXTURE = {
    "itemSummaries": [
        {"itemId": "v1|123456789012|0",
         "title": "Hermès Kelly 28 Togo schwarz, beschädigt, Ecken abgenutzt",
         "itemWebUrl": "https://www.ebay.de/itm/123456789012?hash=abc",
         "price": {"value": "12500.00", "currency": "EUR"}},
        {"itemId": "v1|223456789013|0",
         "title": "Hermes Birkin 30 - REPLICA inspired style",
         "itemWebUrl": "https://www.ebay.de/itm/223456789013",
         "price": {"value": "199.00", "currency": "EUR"}},
    ]
}


def selftest() -> int:
    print("== SELFTEST ==")
    cfg = load_config()
    ok = True

    # 1) HTML parser
    items = parse_ebay(EBAY_FIXTURE, "ebay_de")
    assert len(items) == 4, f"čekány 4 položky, je {len(items)}"
    # 2) filtr (Kelly28 ano, replica ne, twilly ne, Birkin25 ano)
    passed = [i for i in items if title_passes(i["title"], cfg)]
    assert len(passed) == 2, f"čekány 2 po filtru, je {len(passed)}"
    # 3) cena/měna
    kelly = next(i for i in items if "Kelly 28" in i["title"])
    assert kelly["price"] == 12500.0 and kelly["currency"] == "EUR", kelly
    birkin = next(i for i in items if "Birkin 25" in i["title"])
    assert birkin["price"] == 9800.0 and birkin["currency"] == "GBP", birkin
    # 4) odhad marže
    for p in passed:
        assess(p, cfg)
    k = next(p for p in passed if "Kelly 28" in p["title"])
    assert k["price_czk"] == 312500, k
    assert k["margin_est_czk"] == 327500, k
    assert k["flag"] == "KOUPIT", k
    # 5) report
    rep = build_report(passed)
    assert "EU (primární)" in rep and "OVĚŘIT PRAVOST" in rep
    # 6) parse_price edge cases (vč. opravy "jen tečka jako tisíce")
    assert parse_price("1,234.56 USD") == (1234.56, "USD")
    assert parse_price("1.234,56 €") == (1234.56, "EUR")
    assert parse_price("Kč 45 000") == (45000.0, "CZK")
    assert parse_price("1.250 €") == (1250.0, "EUR"), parse_price("1.250 €")
    assert parse_price("9.800 €") == (9800.0, "EUR"), parse_price("9.800 €")
    assert parse_price("12.50 €") == (12.5, "EUR"), parse_price("12.50 €")
    assert parse_price("1.250.000 €") == (1250000.0, "EUR")
    # 7) JPY přepočet (po doplnění fx.JPY_CZK)
    if cfg.get("fx", {}).get("JPY_CZK"):
        assert to_czk(1000000, "JPY", cfg["fx"]) is not None
    # 8) eBay API mapování
    mapped = [map_ebay_item(it, "ebay_de_api") for it in EBAY_API_FIXTURE["itemSummaries"]]
    assert mapped[0]["id"] == "ebay:v1|123456789012|0", mapped[0]
    assert mapped[0]["price"] == 12500.0 and mapped[0]["currency"] == "EUR", mapped[0]
    assert mapped[0]["url"] == "https://www.ebay.de/itm/123456789012", mapped[0]
    apass = [m for m in mapped if title_passes(m["title"], cfg)]
    assert len(apass) == 1, apass   # replica vyhozena
    # 9) detekce 0 výsledků (eBay fallback past)
    assert looks_zero_results("... 0 Ergebnisse für hermes birkin beschädigt ...")
    assert looks_zero_results("No exact matches found")
    assert not looks_zero_results("Hermès Kelly 28 Togo beschädigt")
    # 10) detekce blokace
    assert looks_blocked("x") is not None
    assert looks_blocked("<html>" + "Pardon Our Interruption" + " " * 2000 + "</html>") is not None
    # 11) cenový strop
    cheap = {"price_czk": 200000, "margin_est_czk": None}
    pricey = {"price_czk": 900000, "margin_est_czk": None}
    cfg_cap = {**cfg, "max_price_czk": 380000}
    assert worth_alert(cheap, cfg_cap) is True
    assert worth_alert(pricey, cfg_cap) is False

    print(f"  HTML parser: {len(items)} položek, po filtru {len(passed)}")
    print(f"  API mapování: {len(mapped)} položek, po filtru {len(apass)}")
    print(f"  Kelly 28: {k['price_czk']:,} Kč, marže {k['margin_est_czk']:,} Kč → {k['flag']}")
    print("  ---- ukázka reportu ----")
    print(rep)
    print("== SELFTEST OK ==" if ok else "== SELFTEST FAIL ==")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Hermès Scout")
    ap.add_argument("--selftest", action="store_true", help="offline test bez sítě")
    ap.add_argument("--dry-run", action="store_true", help="nezapisovat seen.json")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    cfg = load_config()
    new_rows = run(cfg, dry_run=args.dry_run)
    print(f"\nHotovo: {len(new_rows)} nových nálezů.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
