import requests
from dotenv import load_dotenv
import os

load_dotenv()

def test_bank(name, token):
    headers = {"Authorization": f"Bearer {token}"}

    accounts = requests.get(
        "https://api.truelayer.com/data/v1/accounts",
        headers=headers
    ).json()

    print(f"\n--- {name} ---")
    print(accounts)

test_bank("HSBC", os.getenv("TRUELAYER_HSBC_ACCESS_TOKEN"))
test_bank("Bank of Scotland", os.getenv("TRUELAYER_BOS_ACCESS_TOKEN"))
