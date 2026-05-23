# Budget Automation

A small Python project to collect transactions from Monzo and Open Banking providers via TrueLayer, normalise them into a single list, categorise them, and write monthly totals directly into a personal budget Excel workbook.

## What this project does

- Fetches Monzo transactions via the Monzo OAuth2 API.
- Fetches bank transactions from TrueLayer-connected providers (HSBC, Bank of Scotland).
- Parses manually exported HSBC credit card PDF statements from the `statements/` folder.
- Normalises, deduplicates, and sorts transactions from all sources.
- Categorises each transaction using keyword rules and bank-assigned categories.
- Writes monthly totals into the correct cells of `Simple personal budget.xlsx`.

## Key files

All source files live in `src/`:

- `fetch_monzo.py` — refreshes Monzo access tokens and fetches Monzo transactions.
- `fetch_truelayer.py` — refreshes TrueLayer tokens and fetches account transactions for HSBC and Bank of Scotland.
- `fetch_statements.py` — parses manually exported statement files (PDF, CSV, OFX, XML) from the `statements/` folder.
- `normalise.py` — combines and deduplicates transactions from all sources into one unified list.
- `write_to_excel.py` — categorises transactions and writes monthly totals into the correct rows and columns of the budget workbook.
- `reauth_all.py` — interactive browser-based re-authentication flow for all three bank connections.

Entry point:

- `tests/test_fetch.py` — runs the full monthly pipeline: fetch → parse statements → normalise → write to Excel.

## Setup

1. Create a `.env` file in the project root with the required values (see below).
2. Activate the virtual environment: `.\budgeting\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Place `Simple personal budget.xlsx` in the project root.

### Required environment variables

- `MONZO_CLIENT_ID`
- `MONZO_CLIENT_SECRET`
- `MONZO_REFRESH_TOKEN`
- `TRUELAYER_CLIENT_ID`
- `TRUELAYER_CLIENT_SECRET`
- `TRUELAYER_HSBC_REFRESH_TOKEN`
- `TRUELAYER_BOS_REFRESH_TOKEN`

## How to use

1. Run `python src/reauth_all.py` if any bank connections have expired (opens browser).
2. Drop any HSBC credit card PDF statements into the `statements/` folder.
3. Edit the `year` and `month` at the bottom of `tests/test_fetch.py`.
4. Run the pipeline from the project root:
   ```bash
   python tests/test_fetch.py
   ```
5. Open `Simple personal budget.xlsx` — the month column will be populated.

## HSBC credit card

HSBC credit card transactions are not available via Open Banking/TrueLayer. The workaround is to export the monthly PDF statement from HSBC online banking and drop it into the `statements/` folder. The PDF parser handles it automatically. A placeholder file at `statements/example_hsbc_credit_card.pdf` shows the expected naming convention.

## Notes

- All `datetime` objects passed to fetch functions must be UTC-aware (`tzinfo=timezone.utc`).
- The normalisation logic deduplicates transactions using `date`, `description`, `amount`, and `source`.
- Monzo uses refresh token rotation — the new refresh token is written back to `.env` automatically after every run.
- TrueLayer tokens expire after ~90 days of inactivity and require a full re-auth via `reauth_all.py`.
- Known bug: Trainline PDF entries can misparse the phone number as the amount.
