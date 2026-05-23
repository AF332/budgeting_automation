import sys
import os
import requests
import webbrowser
from pathlib import Path
from dotenv import load_dotenv, set_key

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)


def prompt(message: str) -> None:
    """
    Prints a message and waits for the user to press Enter before
    continuing. Used to pace the re-authentication steps so the user
    has time to complete each bank login before moving to the next.

    Args:
        message (str): The instruction message to display to the user.

    Returns:
        None
    """
    print(f"\n{message}")
    input("Press Enter when ready to continue...")


def exchange_monzo_token(code: str) -> None:
    """
    Exchanges a Monzo authorisation code for an access token and refresh
    token and saves both directly to the .env file.

    Calls the Monzo OAuth2 token endpoint with the provided authorisation
    code. On success, writes the new access token and refresh token to the
    .env file using set_key, overwriting the previous values. Prints a
    warning and exits if the exchange fails.

    Args:
        code (str): The authorisation code copied from the redirect URL
            after completing the Monzo OAuth2 login flow.

    Returns:
        None
    """
    response = requests.post("https://api.monzo.com/oauth2/token", data={
        "grant_type": "authorization_code",
        "client_id": os.getenv("MONZO_CLIENT_ID"),
        "client_secret": os.getenv("MONZO_CLIENT_SECRET"),
        "redirect_uri": "http://localhost:3000",
        "code": code.strip(),
    })

    tokens = response.json()

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if access_token and refresh_token:
        set_key(ENV_FILE, "MONZO_ACCESS_TOKEN", access_token)
        set_key(ENV_FILE, "MONZO_REFRESH_TOKEN", refresh_token)
        print("  Monzo tokens saved to .env successfully.")
    else:
        print(f"  ERROR: Monzo token exchange failed — {tokens}")
        sys.exit(1)


def exchange_truelayer_token(
    code: str,
    access_token_key: str,
    refresh_token_key: str,
    bank_name: str
) -> None:
    """
    Exchanges a TrueLayer authorisation code for an access token and refresh
    token and saves both directly to the .env file under the specified keys.

    Calls the TrueLayer token endpoint with the provided authorisation code.
    On success, writes the new access token and refresh token to the .env
    file using set_key, overwriting the previous values. Prints a warning
    and exits if the exchange fails.

    Args:
        code (str): The authorisation code copied from the redirect URL
            after completing the TrueLayer OAuth2 login flow.
        access_token_key (str): The .env key to write the access token to,
            e.g. 'TRUELAYER_HSBC_ACCESS_TOKEN'.
        refresh_token_key (str): The .env key to write the refresh token to,
            e.g. 'TRUELAYER_HSBC_REFRESH_TOKEN'.
        bank_name (str): Human-readable bank name used in log messages.

    Returns:
        None
    """
    response = requests.post("https://auth.truelayer.com/connect/token", data={
        "grant_type": "authorization_code",
        "client_id": os.getenv("TRUELAYER_CLIENT_ID"),
        "client_secret": os.getenv("TRUELAYER_CLIENT_SECRET"),
        "redirect_uri": "http://localhost:3000/callback",
        "code": code.strip(),
    })

    tokens = response.json()

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if access_token and refresh_token:
        set_key(ENV_FILE, access_token_key, access_token)
        set_key(ENV_FILE, refresh_token_key, refresh_token)
        print(f"  {bank_name} tokens saved to .env successfully.")
    else:
        print(f"  ERROR: {bank_name} token exchange failed — {tokens}")
        sys.exit(1)


def build_truelayer_auth_url() -> str:
    """
    Builds the TrueLayer OAuth2 authorisation URL using the client ID
    stored in the .env file.

    Returns:
        str: The full TrueLayer authorisation URL to open in the browser.
    """
    client_id = os.getenv("TRUELAYER_CLIENT_ID")
    redirect_uri = "http://localhost:3000/callback"
    return (
        f"https://auth.truelayer.com/?response_type=code"
        f"&client_id={client_id}"
        f"&scope=accounts%20balance%20transactions%20offline_access"
        f"&redirect_uri={redirect_uri}"
        f"&providers=uk-ob-all%20uk-oauth-all"
        f"&state=budget_automation"
    )


def build_monzo_auth_url() -> str:
    """
    Builds the Monzo OAuth2 authorisation URL using the client ID stored
    in the .env file.

    Returns:
        str: The full Monzo authorisation URL to open in the browser.
    """
    client_id = os.getenv("MONZO_CLIENT_ID")
    redirect_uri = "http://localhost:3000"
    return (
        f"https://auth.monzo.com/?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&state=budget_automation"
    )


def reauth_bank_of_scotland() -> None:
    """
    Runs the full re-authentication flow for Bank of Scotland via TrueLayer.

    Opens the TrueLayer auth URL in the browser, prompts the user to log in
    and select Bank of Scotland, then collects the authorisation code from
    the redirect URL and exchanges it for new tokens. Saves the new tokens
    directly to the .env file. Must be completed within 5 minutes of login
    due to Bank of Scotland's SCA window.

    Returns:
        None
    """
    print("\n" + "=" * 50)
    print("STEP 1 — Bank of Scotland")
    print("=" * 50)
    print("Opening TrueLayer in your browser...")
    print("Select 'Bank of Scotland' from the bank list and log in.")
    print("You have 5 minutes from approval to paste the code.")

    url = build_truelayer_auth_url()
    webbrowser.open(url)

    print(f"\nIf the browser did not open, copy this URL manually:\n{url}")

    prompt("After logging in and being redirected to localhost:3000, press Enter.")

    code = input("Paste the code= value from the redirect URL: ").strip()

    if "code=" in code:
        code = code.split("code=")[1].split("&")[0]

    exchange_truelayer_token(
        code,
        "TRUELAYER_BOS_ACCESS_TOKEN",
        "TRUELAYER_BOS_REFRESH_TOKEN",
        "Bank of Scotland"
    )


def reauth_hsbc() -> None:
    """
    Runs the full re-authentication flow for HSBC via TrueLayer.

    Opens the TrueLayer auth URL in the browser, prompts the user to log in
    and select HSBC, then collects the authorisation code from the redirect
    URL and exchanges it for new tokens. Saves the new tokens directly to
    the .env file.

    Returns:
        None
    """
    print("\n" + "=" * 50)
    print("STEP 2 — HSBC")
    print("=" * 50)
    print("Opening TrueLayer in your browser...")
    print("Select 'HSBC' from the bank list and log in.")

    url = build_truelayer_auth_url()
    webbrowser.open(url)

    print(f"\nIf the browser did not open, copy this URL manually:\n{url}")

    prompt("After logging in and being redirected to localhost:3000, press Enter.")

    code = input("Paste the code= value from the redirect URL: ").strip()

    if "code=" in code:
        code = code.split("code=")[1].split("&")[0]

    exchange_truelayer_token(
        code,
        "TRUELAYER_HSBC_ACCESS_TOKEN",
        "TRUELAYER_HSBC_REFRESH_TOKEN",
        "HSBC"
    )


def reauth_monzo() -> None:
    """
    Runs the full re-authentication flow for Monzo.

    Opens the Monzo auth URL in the browser, prompts the user to approve
    the request in the Monzo app, then collects the authorisation code from
    the redirect URL and exchanges it for new tokens. Saves the new access
    token and refresh token directly to the .env file.

    Returns:
        None
    """
    print("\n" + "=" * 50)
    print("STEP 3 — Monzo")
    print("=" * 50)
    print("Opening Monzo auth in your browser...")
    print("Approve the request in your Monzo app immediately.")

    url = build_monzo_auth_url()
    webbrowser.open(url)

    print(f"\nIf the browser did not open, copy this URL manually:\n{url}")

    prompt("After approving in the Monzo app and being redirected, press Enter.")

    code = input("Paste the code= value from the redirect URL: ").strip()

    if "code=" in code:
        code = code.split("code=")[1].split("&")[0]

    exchange_monzo_token(code)

    print("\nNow open your Monzo app and approve the data access request.")
    input("Press Enter once you have approved it in the app...")


if __name__ == "__main__":
    print("=" * 50)
    print("Re-authentication helper")
    print("This will refresh all three bank connections")
    print("and save the new tokens directly to your .env file.")
    print("=" * 50)

    reauth_bank_of_scotland()
    reauth_hsbc()
    reauth_monzo()

    print("\n" + "=" * 50)
    print("All connections refreshed successfully.")
    print("Run python test_fetch.py to verify everything works.")
    print("=" * 50)
