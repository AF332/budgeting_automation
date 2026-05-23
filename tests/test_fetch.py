from src.fetch_monzo import fetch_monzo_transactions
from src.fetch_truelayer import fetch_truelayer_transactions
from src.fetch_statements import fetch_statement_transactions
from src.normalise import normalise_transactions
from src.write_to_excel import write_transactions_to_budget
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()


def run_test(year: int, month: int) -> None:
    """
    Runs a full end-to-end test of the transaction fetching pipeline for a
    given month, including both API sources and manually exported statement
    files.

    Fetches transactions from Monzo, HSBC, and Bank of Scotland via their
    respective APIs, parses any CSV, OFX, or XML files found in the
    statements/ folder, normalises everything into a single list, and prints
    a summary along with the first five transactions for manual inspection.

    Args:
        year (int): The calendar year to fetch transactions for, e.g. 2026.
        month (int): The calendar month to fetch transactions for, as an
            integer from 1 (January) to 12 (December).

    Returns:
        None
    """
    start = datetime(year, month, 1, tzinfo=timezone.utc)

    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    print(f"Fetching transactions for {year}-{month:02d}...\n")

    print("Fetching Monzo transactions...")
    monzo = fetch_monzo_transactions(start, end)
    print(f"  Found {len(monzo)} transactions\n")

    print("Fetching HSBC transactions...")
    hsbc = fetch_truelayer_transactions(
        "HSBC",
        os.getenv("TRUELAYER_HSBC_REFRESH_TOKEN"),
        start,
        end
    )
    print(f"  Found {len(hsbc)} transactions\n")

    print("Fetching Bank of Scotland transactions...")
    bos = fetch_truelayer_transactions(
        "Bank of Scotland",
        os.getenv("TRUELAYER_BOS_REFRESH_TOKEN"),
        start,
        end
    )
    print(f"  Found {len(bos)} transactions\n")

    print("Parsing statement files from statements/ folder...")
    statements = fetch_statement_transactions(start, end)
    print(f"  Found {len(statements)} transactions from statement files\n")

    print("Normalising...")
    all_transactions = normalise_transactions(monzo, hsbc, bos, statements)
    print(f"  Total unique transactions: {len(all_transactions)}\n")

    print("All transactions:")
    for t in all_transactions:
        pounds = t["amount"] / 100
        print(
            f"  {t['date']} | {t['source']:<30} | "
            f"£{pounds:>8.2f} | {t['category']:<15} | {t['description']}"
        )

    print("\nWriting to Excel...")
    output_path = write_transactions_to_budget(all_transactions, year, month)
    print(f" Done. Open: {output_path}")


if __name__ == "__main__":
    run_test(year=2026, month=4)
