import requests
from dotenv import load_dotenv, set_key
from datetime import datetime
from pathlib import Path
import os

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)


def refresh_monzo_token() -> str:
    """
    Refreshes the Monzo access token using the stored refresh token and
    saves the new refresh token back to the .env file.

    Monzo uses refresh token rotation — every time a new access token is
    requested, the old refresh token is immediately invalidated and a new
    one is issued. This function saves the new refresh token back to the
    .env file after every call so subsequent runs always have a valid
    refresh token available.

    Returns:
        str: A fresh access token string.
    """
    response = requests.post("https://api.monzo.com/oauth2/token", data={
        "grant_type": "refresh_token",
        "client_id": os.getenv("MONZO_CLIENT_ID"),
        "client_secret": os.getenv("MONZO_CLIENT_SECRET"),
        "refresh_token": os.getenv("MONZO_REFRESH_TOKEN"),
    })

    tokens = response.json()

    new_access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token")

    if new_access_token and new_refresh_token:
        set_key(ENV_FILE, "MONZO_ACCESS_TOKEN", new_access_token)
        set_key(ENV_FILE, "MONZO_REFRESH_TOKEN", new_refresh_token)
        print("  Monzo tokens rotated and saved to .env successfully.")
    else:
        print("  WARNING: Monzo token refresh failed —", tokens)

    return new_access_token


def get_account_id(token: str) -> str | None:
    """
    Retrieves the Monzo UK retail account ID for the authenticated user.

    Fetches all accounts associated with the token and prints all account
    types found for debugging. Returns the account ID of the first account
    with type 'uk_retail', which is the standard current account. Excludes
    joint accounts and prepaid cards.

    Args:
        token (str): A valid Monzo access token.

    Returns:
        str | None: The account ID string if found, or None if no retail
        account exists.
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://api.monzo.com/accounts", headers=headers)
    accounts = response.json().get("accounts", [])
    print("Monzo accounts found:", [(a["type"], a["id"]) for a in accounts])
    for account in accounts:
        if account["type"] == "uk_retail":
            return account["id"]
    return None


def fetch_monzo_transactions(start_date: datetime, end_date: datetime) -> list[dict]:
    """
    Fetches and normalises all Monzo transactions within a given date range.

    Automatically refreshes the access token before making the request.
    Filters out zero-amount transactions such as declined payments or
    internal pot transfers. Amounts are returned in pence as integers.

    Args:
        start_date (datetime): The start of the date range (UTC-aware).
        end_date (datetime): The end of the date range (UTC-aware).

    Returns:
        list[dict]: A list of normalised transaction dictionaries, each
        containing the following keys:
            - date (str): Transaction date in YYYY-MM-DD format.
            - description (str): Merchant or transaction description.
            - amount (int): Transaction amount in pence. Negative values
              indicate outgoing payments, positive values indicate incoming.
            - category (str): Monzo-assigned category label e.g. 'groceries'.
            - source (str): Always 'Monzo' for transactions from this function.
    """
    token = refresh_monzo_token()
    account_id = get_account_id(token)

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "account_id": account_id,
        "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "before": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    response = requests.get(
        "https://api.monzo.com/transactions",
        headers=headers,
        params=params
    )

    print("Monzo raw response:", response.json())

    raw = response.json().get("transactions", [])
    transactions: list[dict] = []

    for t in raw:
        if t["amount"] == 0:
            continue
        transactions.append({
            "date": t["created"][:10],
            "description": t.get("description", "Unknown"),
            "amount": t["amount"],
            "category": t.get("category", "general"),
            "source": "Monzo"
        })

    return transactions
