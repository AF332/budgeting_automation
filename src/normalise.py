def normalise_transactions(
    monzo: list[dict],
    hsbc: list[dict],
    bos: list[dict],
    statements: list[dict]
) -> list[dict]:
    """
    Combines, deduplicates, and sorts transaction lists from all sources
    into a single unified list.

    Merges API-fetched transactions from Monzo, HSBC, and Bank of Scotland
    with any manually exported statement files, then sorts by date ascending.
    Deduplication uses a composite key of date, description, amount, and
    source to avoid removing legitimate repeat transactions while still
    catching true duplicates.

    Args:
        monzo (list[dict]): Normalised transactions from fetch_monzo.py.
        hsbc (list[dict]): Normalised transactions from fetch_truelayer.py
            for the HSBC connection.
        bos (list[dict]): Normalised transactions from fetch_truelayer.py
            for the Bank of Scotland connection.
        statements (list[dict]): Normalised transactions parsed from
            manually exported CSV, OFX, or XML statement files.

    Returns:
        list[dict]: A single deduplicated and date-sorted list of transaction
        dictionaries. Each dictionary contains:
            - date (str): Transaction date in YYYY-MM-DD format.
            - description (str): Merchant or transaction description.
            - amount (int): Transaction amount in pence.
            - category (str): Category label assigned by the source bank.
            - source (str): The originating bank or file name.
    """
    all_transactions: list[dict] = monzo + hsbc + bos + statements

    all_transactions.sort(key=lambda t: t["date"])

    seen: set[tuple] = set()
    unique: list[dict] = []
    for t in all_transactions:
        key = (t["date"], t["description"], t["amount"], t["source"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique
