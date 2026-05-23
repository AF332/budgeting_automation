import requests
from dotenv import load_dotenv
import os

load_dotenv()

headers = {"Authorization": f"Bearer {os.getenv('MONZO_ACCESS_TOKEN')}"}

response = requests.get("https://api.monzo.com/accounts", headers=headers)
print(response.json())