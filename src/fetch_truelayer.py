import requests
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()


def refresh_truelayer_token(refresh_token: str) -> str:
    """
    Refreshes a TrueLayer access token using the provided refresh token.

    Calls the TrueLayer token endpoint with the refresh_token grant type.
    Client credentials are read from the TRUELAYER_CLIENT_ID and
    TRUELAYER_CLIENT_SECRET environment variables.

    Args:
        refresh_token (str): A valid TrueLayer refresh token for the bank
        connection being refreshed. Each bank (HSBC, Bank of Scotland) has
        its own refresh token.

    Returns:
        str: A fresh TrueLayer access token string.
    """
    response = requests.post("https://auth.truelayer.com/connect/token", data={
        "grant_type": "refresh_token",
        "client_id": os.getenv("TRUELAYER_CLIENT_ID"),
        "client_secret": os.getenv("TRUELAYER_CLIENT_SECRET"),
        "refresh_token": refresh_token,
    })
    tokens = response.json()
    return tokens.get("access_token")


def get_account_ids(token: str) -> list[str]:
    """
    Retrieves all bank account IDs accessible under a TrueLayer access token.

    A single TrueLayer token may grant access to multiple accounts at the
    same bank, for example a current account and a savings account. This
    function returns all of them so transactions can be fetched from each.
    Prints the display names of all found accounts for debugging purposes.

    Args:
        token (str): A valid TrueLayer access token.

    Returns:
        list[str]: A list of account ID strings. Returns an empty list if
        no accounts are found or if the token is invalid.
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "https://api.truelayer.com/data/v1/accounts",
        headers=headers
    )
    accounts = response.json().get("results", [])
    print("Bank accounts found:", [a.get("display_name", a["account_id"]) for a in accounts])
    return [a["account_id"] for a in accounts]


def fetch_truelayer_transactions(
    bank_name: str,
    refresh_token: str,
    start_date: datetime,
    end_date: datetime
) -> list[dict]:
    """
    Fetches and normalises all transactions from a TrueLayer-connected bank
    within a given date range.

    Automatically refreshes the access token before making requests.
    Iterates over all accounts found under the token. Skips any account that
    returns an error response, such as accounts blocked by Article 10A
    restrictions. TrueLayer returns amounts as floats in pounds, which are
    converted to pence as integers to avoid floating point rounding issues.
    Safely handles transactions where transaction_classification is an empty
    list by falling back to 'general'.

    Args:
        bank_name (str): A human-readable label for the bank, e.g. 'HSBC'
            or 'Bank of Scotland'. Used to populate the 'source' field on
            each transaction.
        refresh_token (str): A valid TrueLayer refresh token for this bank
            connection.
        start_date (datetime): The start of the date range (UTC-aware).
        end_date (datetime): The end of the date range (UTC-aware).

    Returns:
        list[dict]: A list of normalised transaction dictionaries across all
        accessible accounts for this bank, each containing the following keys:
            - date (str): Transaction date in YYYY-MM-DD format.
            - description (str): Merchant or transaction description.
            - amount (int): Transaction amount in pence. Negative values
              indicate outgoing payments, positive values indicate incoming.
            - category (str): TrueLayer classification label, lowercased.
              Falls back to 'general' if no classification is provided or
              if the classification list is empty.
            - source (str): The bank_name argument passed to this function.
    """
    token = refresh_truelayer_token(refresh_token)
    account_ids = get_account_ids(token)
    headers = {"Authorization": f"Bearer {token}"}
    transactions: list[dict] = []

    for account_id in account_ids:
        params = {
            "from": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        response = requests.get(
            f"https://api.truelayer.com/data/v1/accounts/{account_id}/transactions",
            headers=headers,
            params=params
        )

        response_json = response.json()
        print(f"{bank_name} account raw response:", response_json)

        if "error" in response_json:
            print(
                f"  Skipping account {account_id} — error: "
                f"{response_json.get('error_description', response_json['error'])}"
            )
            continue

        raw = response_json.get("results", [])

        for t in raw:
            amount_pence = int(t["amount"] * 100)
            classification = t.get("transaction_classification", [])
            category = classification[0].lower() if classification else "general"

            transactions.append({
                "date": t["timestamp"][:10],
                "description": t.get("description", "Unknown"),
                "amount": amount_pence,
                "category": category,
                "source": bank_name
            })

    return transactions
