# Budget Automation

A small Python project to collect transactions from Monzo and Open Banking providers via TrueLayer, normalise them into a single list, and support a mixed manual/automatic workflow for budget tracking.

## What this project does

- Fetches Monzo transactions via the Monzo OAuth2 API.
- Fetches bank transactions from TrueLayer-connected providers.
- Normalises, deduplicates, and sorts transactions from multiple sources.
- Includes helper scripts to obtain authorization URLs and exchange auth codes for refresh tokens.

## Key files

- `fetch_monzo.py` - refreshes Monzo access tokens and fetches Monzo transactions.
- `fetch_truelayer.py` - refreshes TrueLayer tokens and fetches account transactions for provided TrueLayer refresh tokens.
- `normalise.py` - combines and deduplicates transactions from Monzo, HSBC, HSBC credit card, and Bank of Scotland into one unified transaction list.
- `monzo_auth.py` - builds and prints a Monzo authorization URL for initial OAuth authorization.
- `monzo_token.py` - exchanges a Monzo authorization code for tokens.
- `truelayer_auth.py` - builds and prints a TrueLayer authorization URL for initial OAuth authorization.
- `truelayer_token.py` - exchanges a TrueLayer authorization code for tokens.
- `test_fetch.py` - example entry point to run a monthly fetch and print a summary of results.
- `.env` - local environment variables loaded by `python-dotenv`.
- `budgeting/` - local Python virtual environment for the project.

## Setup

1. Create a `.env` file in the project root with the required values.
2. Install dependencies into the `budgeting` virtual environment, or use the environment already present.

### Required environment variables

- `MONZO_CLIENT_ID`
- `MONZO_CLIENT_SECRET`
- `MONZO_REFRESH_TOKEN`
- `TRUELAYER_CLIENT_ID`
- `TRUELAYER_CLIENT_SECRET`
- `TRUELAYER_HSBC_REFRESH_TOKEN`
- `TRUELAYER_BOS_REFRESH_TOKEN`


## How to use

1. Use `monzo_auth.py` and `monzo_token.py` to obtain Monzo OAuth tokens if you do not already have them.
2. Use `truelayer_auth.py` and `truelayer_token.py` to obtain TrueLayer authorization and refresh tokens for your banks.
3. Place the tokens into `.env`.
4. Run `python test_fetch.py` to fetch transactions for a month, normalise them, and print a summary.

## Current project behaviour

- Monzo is fetched directly using its token refresh endpoint.
- TrueLayer is used to fetch current account transactions for HSBC and Bank of Scotland.
- HSBC credit card transactions are not available automatically through the current Open Banking setup.
- `normalise.py` merges all transaction sources, sorts by date, and removes exact duplicates.

## Known limitation: HSBC credit card via Open Banking

HSBC is not reliably exposing its credit card transactions through Open Banking / TrueLayer for this project. That means the project cannot automatically fetch the granular credit card transactions you use every month.

This is a significant limitation because most of your monthly spending happens on that credit card, and the credit card feed is the source that would normally provide category-level detail for food, travel, flights, and other spending.

## Options for handling HSBC credit card data

### Option 1: Manual CSV export for HSBC credit card

- Download the HSBC credit card statement as a CSV at the end of each month.
- Add a small CSV parser alongside the existing automated feeds.
- Everything else remains fully automatic.
- The monthly statement only covers up to the 28th of each month, so it does not capture the whole month's usage.
- To keep the workflow fully automatic you would need to stop using the credit card before the 28th, or manually add the last entries after the 28th.
- This is the best way to preserve granular transaction detail for credit card spending while keeping the rest of the system automatic.

### Option 2: Use HSBC current account payments as a proxy

- Do not import credit card transactions directly.
- Use the HSBC current account feed as a proxy by capturing the monthly repayment amount to your credit card.
- This keeps the workflow automatic, but you lose per-transaction detail for the credit card.
- This would be fine if you decide to treat all credit card spending as food shopping only, but it becomes inaccurate if your card is also used for travel, flights, or other categories.
- It is a weaker solution if you need to know whether spending was food, travel, flights, or other categories.

### Option 3: Switch to a card or provider that supports Open Banking credit card feeds

- If possible, use a different credit card provider or bank account that exposes card transactions through Open Banking.
- This is the cleanest automatic approach if you can move spending to a compatible provider.
- Otherwise, maintain the mixed mode with the bank account current feed and manual credit card handling.

## Recommended path for this project

Given the current limitation, the most useful path is:

1. Keep the existing automatic Monzo and TrueLayer bank feeds.
2. Add a dedicated CSV parser for HSBC credit card statements.
3. Use the current account repayment flow only as a fallback if the CSV cannot be obtained.

That keeps the core automation intact while preserving the detailed credit card transaction data you need for true monthly budgeting.

## Notes

- The project currently assumes date ranges are provided in UTC-aware `datetime` objects.
- The normalisation logic deduplicates transactions using `date`, `description`, `amount`, and `source`.
- If HSBC credit cards become available via Open Banking in the future, the credit card refresh token path can be enabled again.

## Stop at
- pdf parsed not fully functioning. trainline amount parsed the phone number instead of the amount.
- it showed 6 unique transaction even though there are more than that
- Bank APIs seems to need manual login after not using it for a while. Why is this?
