import csv
import os
import re
from datetime import datetime
from pathlib import Path

import pdfplumber
from ofxparse import OfxParser


STATEMENTS_DIR = Path(__file__).parent / "statements"


def parse_date(date_str: str) -> str:
    """
    Attempts to parse a date string into YYYY-MM-DD format.

    Tries multiple common date formats used by UK banks in their CSV and
    XML exports, including DD/MM/YYYY, YYYY-MM-DD, DD MMM YYYY, DD-MM-YYYY,
    and two-digit year variants. Returns the date as a string in YYYY-MM-DD
    format.

    Args:
        date_str (str): A raw date string from a bank statement file.

    Returns:
        str: The date formatted as YYYY-MM-DD, or the original string if
        no known format matches.
    """
    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%m/%d/%Y",
        "%d %b %y",
        "%d %B %y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str.strip()


def parse_amount(amount_str: str) -> int:
    """
    Converts a raw amount string from a bank export into pence as an integer.

    Handles common formatting variations found in UK bank exports including
    pound signs, commas, parentheses for negative numbers, and both positive
    and negative signs. Returns the amount in pence to avoid floating point
    rounding issues.

    Args:
        amount_str (str): A raw amount string e.g. '£1,234.56', '-45.00',
            '(12.50)', '1234.56 CR', '1234.56 DR'.

    Returns:
        int: The amount in pence. Negative values indicate outgoing payments,
        positive values indicate incoming payments.
    """
    raw = amount_str.strip()
    negative = False

    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1]

    if raw.upper().endswith("DR"):
        negative = True
        raw = raw[:-2].strip()
    elif raw.upper().endswith("CR"):
        raw = raw[:-2].strip()

    raw = raw.replace("£", "").replace(",", "").replace(" ", "").strip()

    if raw.startswith("-"):
        negative = True
        raw = raw[1:]

    try:
        pence = int(round(float(raw) * 100))
        return -pence if negative else pence
    except ValueError:
        return 0


def _is_valid_amount(text: str) -> bool:
    """
    Checks whether a string looks like a valid monetary amount.

    A valid amount contains only digits, an optional decimal point, optional
    commas as thousand separators, an optional leading pound sign, and an
    optional trailing CR suffix. Strings starting with + or containing
    non-numeric characters like phone numbers are rejected.

    Args:
        text (str): The raw string to validate.

    Returns:
        bool: True if the string is a valid monetary amount, False otherwise.
    """
    clean = text.strip().upper()
    clean = clean.replace("CR", "").replace("£", "").replace(",", "").strip()
    if not clean:
        return False
    if clean.startswith("+") or clean.startswith("-"):
        return False
    try:
        value = float(clean)
        return 0 < value < 100000
    except ValueError:
        return False


def detect_csv_format(headers: list[str]) -> str:
    """
    Detects which bank's CSV format is being parsed based on column headers.

    Different banks use different column names in their CSV exports. This
    function inspects the headers and returns a format identifier string
    that controls how each row is subsequently parsed.

    Args:
        headers (list[str]): The list of column header strings from the
        first row of the CSV file, stripped of whitespace and lowercased.

    Returns:
        str: A format identifier — one of 'monzo', 'hsbc', 'bos',
        'natwest', 'barclays', or 'generic' if no specific bank is
        detected.
    """
    joined = " ".join(headers)

    if "transaction id" in joined and "emoji" in joined:
        return "monzo"
    if "transaction date" in joined and "payment type" in joined:
        return "hsbc"
    if "date" in joined and "reference" in joined and "debit" in joined and "credit" in joined:
        return "bos"
    if "date" in joined and "description" in joined and "debit amount" in joined:
        return "natwest"
    if "date" in joined and "merchant name" in joined:
        return "barclays"
    return "generic"


def parse_csv_row(
    row: dict,
    fmt: str,
    source: str
) -> dict | None:
    """
    Parses a single CSV row into a normalised transaction dictionary.

    Uses the detected format identifier to extract the correct fields from
    each bank's specific column structure. Returns None if the row cannot
    be parsed or represents a zero-amount transaction.

    Args:
        row (dict): A single row from the CSV file as a dictionary keyed
            by column header strings.
        fmt (str): The format identifier returned by detect_csv_format().
        source (str): The bank name label to assign to this transaction.

    Returns:
        dict | None: A normalised transaction dictionary with keys date,
        description, amount, category, and source — or None if the row
        should be skipped.
    """
    try:
        if fmt == "monzo":
            date = parse_date(row.get("Date", ""))
            description = row.get("Name", "Unknown")
            amount = parse_amount(row.get("Amount", "0"))
            category = row.get("Category", "general").lower()

        elif fmt == "hsbc":
            date = parse_date(row.get("Transaction Date", ""))
            description = row.get("Transaction Description", "Unknown")
            debit = row.get("Debit Amount", "").strip()
            credit = row.get("Credit Amount", "").strip()
            if debit:
                amount = -parse_amount(debit)
            elif credit:
                amount = parse_amount(credit)
            else:
                return None
            category = row.get("Payment Type", "general").lower()

        elif fmt == "bos":
            date = parse_date(row.get("Date", ""))
            description = row.get("Description", row.get("Reference", "Unknown"))
            debit = row.get("Debit Amount", "").strip()
            credit = row.get("Credit Amount", "").strip()
            if debit:
                amount = -parse_amount(debit)
            elif credit:
                amount = parse_amount(credit)
            else:
                return None
            category = "general"

        elif fmt == "natwest":
            date = parse_date(row.get("Date", ""))
            description = row.get("Description", "Unknown")
            debit = row.get("Debit Amount", "").strip()
            credit = row.get("Credit Amount", "").strip()
            if debit:
                amount = -parse_amount(debit)
            elif credit:
                amount = parse_amount(credit)
            else:
                return None
            category = "general"

        elif fmt == "barclays":
            date = parse_date(row.get("Date", ""))
            description = row.get("Merchant Name", row.get("Memo", "Unknown"))
            amount = parse_amount(row.get("Amount", "0"))
            category = row.get("Category", "general").lower()

        else:
            date = parse_date(row.get("Date", row.get("date", "")))
            description = row.get(
                "Description",
                row.get("Memo", row.get("description", "Unknown"))
            )
            raw_amount = row.get(
                "Amount",
                row.get("amount", row.get("Value", "0"))
            )
            amount = parse_amount(raw_amount)
            category = row.get("Category", row.get("category", "general")).lower()

        if amount == 0:
            return None

        return {
            "date": date,
            "description": description,
            "amount": amount,
            "category": category,
            "source": source,
        }

    except Exception as e:
        print(f"  Skipping row due to error: {e} — row: {row}")
        return None


def parse_csv_file(filepath: Path, source: str) -> list[dict]:
    """
    Parses an entire CSV bank statement file into a list of normalised
    transaction dictionaries.

    Reads the CSV file, detects its bank format from the headers, and
    parses each row using the appropriate field mapping. Skips rows that
    cannot be parsed or that represent zero-amount transactions.

    Args:
        filepath (Path): The full path to the CSV file to parse.
        source (str): The bank name label to assign to all transactions
            parsed from this file.

    Returns:
        list[dict]: A list of normalised transaction dictionaries each
        containing keys: date, description, amount (pence), category,
        source.
    """
    transactions: list[dict] = []

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        fmt = detect_csv_format(headers)
        print(f"  Detected format: {fmt}")

        for row in reader:
            cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
            transaction = parse_csv_row(cleaned, fmt, source)
            if transaction:
                transactions.append(transaction)

    return transactions


def parse_ofx_file(filepath: Path, source: str) -> list[dict]:
    """
    Parses an OFX or QFX bank statement file into a list of normalised
    transaction dictionaries.

    OFX (Open Financial Exchange) is an XML-based format used by many UK
    banks as an alternative to CSV. Uses the ofxparse library to extract
    transactions from all accounts contained in the file.

    Args:
        filepath (Path): The full path to the OFX or QFX file to parse.
        source (str): The bank name label to assign to all transactions
            parsed from this file.

    Returns:
        list[dict]: A list of normalised transaction dictionaries each
        containing keys: date, description, amount (pence), category,
        source.
    """
    transactions: list[dict] = []

    with open(filepath, "rb") as f:
        ofx = OfxParser.parse(f)

    for account in ofx.accounts:
        for t in account.statement.transactions:
            amount_pence = int(round(float(t.amount) * 100))
            if amount_pence == 0:
                continue
            transactions.append({
                "date": t.date.strftime("%Y-%m-%d"),
                "description": t.memo or t.payee or "Unknown",
                "amount": amount_pence,
                "category": "general",
                "source": source,
            })

    return transactions


def parse_xml_file(filepath: Path, source: str) -> list[dict]:
    """
    Parses a generic XML bank statement file into a list of normalised
    transaction dictionaries.

    Handles basic XML formats by searching for common transaction element
    tags used by UK banks. Tries multiple tag name variations to maximise
    compatibility across different providers.

    Args:
        filepath (Path): The full path to the XML file to parse.
        source (str): The bank name label to assign to all transactions
            parsed from this file.

    Returns:
        list[dict]: A list of normalised transaction dictionaries each
        containing keys: date, description, amount (pence), category,
        source.
    """
    import xml.etree.ElementTree as ET

    transactions: list[dict] = []
    tree = ET.parse(filepath)
    root = tree.getroot()

    transaction_tags = ["Transaction", "transaction", "STMTTRN", "Entry"]

    entries = []
    for tag in transaction_tags:
        entries = root.findall(f".//{tag}")
        if entries:
            break

    for entry in entries:
        def get(tag_names: list[str]) -> str:
            for tag in tag_names:
                el = entry.find(tag)
                if el is not None and el.text:
                    return el.text.strip()
            return ""

        date_str = get(["Date", "date", "DTPOSTED", "BookingDate", "ValueDate"])
        description = get(["Description", "description", "MEMO", "NAME", "Narrative"])
        amount_str = get(["Amount", "amount", "TRNAMT", "TransactionAmount"])

        if not date_str or not amount_str:
            continue

        amount_pence = parse_amount(amount_str)
        if amount_pence == 0:
            continue

        transactions.append({
            "date": parse_date(date_str),
            "description": description or "Unknown",
            "amount": amount_pence,
            "category": "general",
            "source": source,
        })

    return transactions


def _expand_short_year(date_str: str) -> str:
    """
    Expands a two-digit year in a date string to a four-digit year.

    HSBC credit card PDFs use two-digit years e.g. '28 Dec 25' rather than
    '28 Dec 2025'. This function converts them to the full four-digit format
    so they can be parsed correctly by parse_date(). Assumes all two-digit
    years are in the 2000s.

    Args:
        date_str (str): A date string potentially containing a two-digit
            year e.g. '28 Dec 25' or '02 Jan 26'.

    Returns:
        str: The date string with a four-digit year e.g. '28 Dec 2025'.
    """
    parts = date_str.strip().split()
    if len(parts) == 3 and len(parts[2]) == 2:
        parts[2] = "20" + parts[2]
    return " ".join(parts)


def _group_words_into_rows(words: list[dict]) -> dict[int, list[dict]]:
    """
    Groups extracted PDF words into visual rows based on their vertical
    position.

    Uses a tolerance of 3 pixels when grouping words by their top coordinate
    to account for slight vertical misalignment between words that are
    visually on the same line.

    Args:
        words (list[dict]): A list of word dictionaries from pdfplumber's
            extract_words() method, each with 'text', 'top', 'x0', and
            'x1' fields.

    Returns:
        dict[int, list[dict]]: A dictionary mapping rounded y-coordinates
        to lists of word dictionaries on that visual row, with each list
        sorted by x-coordinate left to right.
    """
    rows: dict[int, list[dict]] = {}
    for word in words:
        top = int(round(word["top"] / 3) * 3)
        rows.setdefault(top, []).append(word)
    for top in rows:
        rows[top] = sorted(rows[top], key=lambda w: w["x0"])
    return rows


def parse_hsbc_credit_card_pdf(filepath: Path, source: str) -> list[dict]:
    """
    Parses an HSBC credit card statement PDF into a list of normalised
    transaction dictionaries.

    Tailored specifically to HSBC's credit card PDF layout which has four
    columns: 'Received By Us' (posting date), 'Transaction Date', 'Details'
    (description), and 'Amount'. Amounts are identified by their x-coordinate
    position in the rightmost portion of the page to avoid confusing phone
    numbers or reference numbers in the description column with monetary
    amounts.

    Handles multi-line descriptions by appending continuation rows to the
    previous transaction when a row does not begin with a recognisable date.
    Stops parsing when it encounters the 'Summary Of Interest On This
    Statement' section to avoid capturing footer and legal text. Credits are
    identified by a 'CR' suffix and represent payments made to the card. All
    other transactions are treated as spending and stored as negative amounts.

    Args:
        filepath (Path): The full path to the HSBC credit card PDF file.
        source (str): The bank name label to assign to all transactions
            parsed from this file.

    Returns:
        list[dict]: A list of normalised transaction dictionaries each
        containing keys: date, description, amount (pence), category,
        source.
    """
    transactions: list[dict] = []
    date_pattern = re.compile(r"^\d{2}\s+\w{3}\s+\d{2}$")

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_width = page.width
            amount_x_threshold = page_width * 0.65

            words = page.extract_words()
            if not words:
                continue

            rows = _group_words_into_rows(words)
            pending_transaction: dict | None = None
            stop_parsing = False

            for top in sorted(rows.keys()):
                if stop_parsing:
                    break

                row_words = rows[top]
                row_text = " ".join(w["text"] for w in row_words).lower()

                if (
                    "summary of interest" in row_text
                    or "estimated interest" in row_text
                ):
                    stop_parsing = True
                    break

                first_three = " ".join(w["text"] for w in row_words[:3])
                row_starts_with_date = bool(date_pattern.match(first_three))

                if row_starts_with_date:
                    if pending_transaction:
                        transactions.append(pending_transaction)
                        pending_transaction = None

                    posting_date = first_three
                    remaining = row_words[3:]

                    txn_date = None
                    if len(remaining) >= 3:
                        candidate = " ".join(w["text"] for w in remaining[:3])
                        if date_pattern.match(candidate):
                            txn_date = candidate
                            remaining = remaining[3:]

                    use_date = txn_date or posting_date

                    amount_str = None
                    amount_word_idx = None
                    for i in range(len(remaining) - 1, -1, -1):
                        word = remaining[i]
                        if (
                            word["x0"] >= amount_x_threshold
                            and _is_valid_amount(word["text"])
                        ):
                            amount_str = word["text"]
                            amount_word_idx = i
                            break

                    if amount_word_idx is not None:
                        desc_words = remaining[:amount_word_idx]
                    else:
                        desc_words = remaining

                    description = (
                        " ".join(w["text"] for w in desc_words).strip()
                        or "Unknown"
                    )

                    if not amount_str:
                        continue

                    is_credit = amount_str.upper().endswith("CR")
                    clean_amount = (
                        amount_str.upper()
                        .replace("CR", "")
                        .replace(",", "")
                        .strip()
                    )

                    try:
                        pence = int(round(float(clean_amount) * 100))
                    except ValueError:
                        continue

                    if pence == 0:
                        continue

                    amount = pence if is_credit else -pence
                    full_date = _expand_short_year(use_date)
                    parsed_date = parse_date(full_date)

                    pending_transaction = {
                        "date": parsed_date,
                        "description": description,
                        "amount": amount,
                        "category": "general",
                        "source": source,
                    }

                else:
                    if pending_transaction:
                        continuation_words = [
                            w["text"] for w in row_words
                            if w["x0"] < amount_x_threshold
                        ]
                        if continuation_words:
                            pending_transaction["description"] += (
                                " " + " ".join(continuation_words)
                            )

            if pending_transaction:
                transactions.append(pending_transaction)

    return transactions


def fetch_statement_transactions(
    start_date: datetime,
    end_date: datetime
) -> list[dict]:
    """
    Scans the statements/ folder for CSV, OFX, QFX, XML, and PDF files and
    parses all of them into a single combined list of normalised transactions
    filtered to the given date range.

    The bank name (source label) is inferred from the filename. Name your
    files descriptively, e.g. 'hsbc_credit_card_jan2026.pdf' or
    'barclaycard_jan2026.ofx'. PDF files are parsed using the HSBC credit
    card specific parser. CSV, OFX, QFX, and XML files are parsed using
    their respective generic parsers.

    Files in the statements/ folder are not deleted after parsing so you
    can re-run the script safely without losing the source files.

    Args:
        start_date (datetime): The start of the date range to include.
            Transactions before this date are filtered out.
        end_date (datetime): The end of the date range to include.
            Transactions on or after this date are filtered out.

    Returns:
        list[dict]: A combined list of normalised transaction dictionaries
        from all statement files, filtered to the given date range, each
        containing keys: date, description, amount (pence), category,
        source.
    """
    if not STATEMENTS_DIR.exists():
        print("  No statements/ folder found — skipping file imports.")
        return []

    all_transactions: list[dict] = []
    files = list(STATEMENTS_DIR.iterdir())
    supported = {".csv", ".ofx", ".qfx", ".xml", ".pdf"}
    statement_files = [f for f in files if f.suffix.lower() in supported]

    if not statement_files:
        print("  No statement files found in statements/ folder.")
        return []

    for filepath in statement_files:
        source = filepath.stem.replace("_", " ").title()
        print(f"  Parsing {filepath.name} as '{source}'...")

        ext = filepath.suffix.lower()

        try:
            if ext == ".csv":
                transactions = parse_csv_file(filepath, source)
            elif ext in {".ofx", ".qfx"}:
                transactions = parse_ofx_file(filepath, source)
            elif ext == ".xml":
                transactions = parse_xml_file(filepath, source)
            elif ext == ".pdf":
                transactions = parse_hsbc_credit_card_pdf(filepath, source)
            else:
                continue
        except Exception as e:
            print(f"  ERROR parsing {filepath.name}: {e}")
            continue

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        filtered = [
            t for t in transactions
            if start_str <= t["date"] < end_str
        ]

        print(f"  Found {len(filtered)} transactions in date range.")
        all_transactions.extend(filtered)

    return all_transactions
