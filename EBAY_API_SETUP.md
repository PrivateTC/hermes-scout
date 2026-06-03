# eBay Browse API — setup (5–10 min)

The scout reads eBay via the official **Browse API** (`provider: ebay_api`). Free, robust, no scraping/blocking. You need two values in the environment: `EBAY_APP_ID` and `EBAY_CERT_ID`.

## Steps
1. Go to **https://developer.ebay.com/** → Register / Sign in with your normal eBay account.
2. Open **Application Keys** (https://developer.ebay.com/my/keys).
3. Create a **Production** keyset (not Sandbox). eBay may require accepting terms / brief account approval.
4. Copy from the Production keyset:
   - **App ID (Client ID)** → `EBAY_APP_ID`
   - **Cert ID (Client Secret)** → `EBAY_CERT_ID`

## Use
```bash
export EBAY_APP_ID="..."
export EBAY_CERT_ID="..."
python3 scout.py --dry-run
```
Without keys, eBay sources are skipped silently (the scout won't crash). The OAuth token is fetched and cached automatically (~2h). Browse API has a generous free daily limit. Markets are controlled by `marketplace` in `config.yaml` (EBAY_DE / EBAY_FR / EBAY_IT / EBAY_GB).
