# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

`src/` is a package (`__init__.py` present). All imports in `tests/` use the `src.` prefix. Run everything from the project root.

```bash
# Activate the virtual environment
.\budgeting\Scripts\Activate.ps1

# Run the full monthly pipeline (edit year/month at the bottom of the file)
python tests/test_fetch.py

# Re-authenticate all three bank connections (interactive, opens browser)
python src/reauth_all.py

# Run the ad-hoc API connectivity tests
python tests/test_monzo.py
python tests/test_truelayer.py

# Install / sync dependencies
pip install -r requirements.txt
```

`~/.bashrc` has `export PYTHONPATH=/f/Projects/budget_automation` so `python tests/test_fetch.py` works from the project root without any prefix.

There is no test runner or lint config in this project.

## Architecture

The pipeline has four layers:

**1. Fetch layer (`src/fetch_monzo.py`, `src/fetch_truelayer.py`)**
Each module exposes one public function (`fetch_monzo_transactions`, `fetch_truelayer_transactions`) that handles token refresh, account discovery, and raw API calls. Both return the same normalised dict shape: `{date, description, amount, category, source}` with `amount` always in **pence as an integer** (negative = outgoing).

- Monzo uses refresh token rotation — every refresh invalidates the old token and issues a new one. `fetch_monzo.py` writes the new refresh token back to `.env` via `set_key` after every call. The `.env` path is resolved as an absolute path anchored to the source file location to avoid writing to the wrong directory.
- TrueLayer tokens do not auto-rotate but expire after ~90 days of inactivity, requiring a full browser re-auth via `reauth_all.py`.

**2. Statement parser (`src/fetch_statements.py`)**
Scans `statements/` (project root) for `.csv`, `.ofx`/`.qfx`, `.xml`, and `.pdf` files. The source label is inferred from the filename stem (underscores replaced with spaces, title-cased). PDF parsing is HSBC credit card-specific (`parse_hsbc_credit_card_pdf`) — it uses x-coordinate thresholds to distinguish the amount column from phone numbers/references in the description column, handles multi-line descriptions, and stops at the interest summary section footer.

**3. Normalise (`src/normalise.py`)**
Merges all four lists (monzo, hsbc, bos, statements), sorts by date ascending, and deduplicates using `(date, description, amount, source)` as the composite key. Legitimate repeat transactions on the same day survive deduplication because source is part of the key.

**4. Excel writer (`src/write_to_excel.py`)**
Categorises each transaction using `DESCRIPTION_RULES` (keyword regex patterns, checked first) then falls back to `CATEGORY_API_MAP` (bank-assigned category → budget key). Writes monthly totals in pounds to the correct row/column in `Simple personal budget.xlsx`. Month → column is controlled by `MONTH_TO_COL`, category → row by `INCOME_ROWS` and `EXPENSE_ROWS`. Uncategorised spending goes to `UNCATEGORISED_ROW`. Also creates a per-month `Transactions YYYY-MM` audit tab with each transaction highlighted by status.

**Re-auth (`src/reauth_all.py`)**
Interactive browser-based OAuth2 flow for all three connections (Bank of Scotland → HSBC → Monzo). Writes new access and refresh tokens straight to `.env`. Run this when TrueLayer tokens expire or when Monzo requires fresh user approval.

## Key constraints

- **HSBC credit card** is not available via Open Banking/TrueLayer. Drop the monthly PDF export into `statements/` — the PDF parser picks it up automatically.
- All `datetime` objects passed to fetch functions must be **UTC-aware** (`tzinfo=timezone.utc`).
- The `statements/` folder is not deleted after parsing — files persist between runs.
- `Simple personal budget.xlsx` must be in the project root. The path is resolved in `write_to_excel.py` as `Path(__file__).parent.parent / "Simple personal budget.xlsx"`.
- Known bug: Trainline PDF entries can misparse the phone number as the amount. Root cause is in `_is_valid_amount` / x-coordinate threshold logic in `parse_hsbc_credit_card_pdf`.
