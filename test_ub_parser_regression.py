import os

from utils.pdf_parser import extract_transactions


def test_unionbank_password_protected_statement_filters_non_transactions():
    pdf_path = os.path.join(
        "data",
        "uploads",
        "UB_VP201-REWARDS VISA PLATINUM_eStatement_02022026_201060006548177.pdf",
    )

    if not os.path.exists(pdf_path):
        return

    password = os.environ.get("UB_PDF_PASSWORD")
    if not password:
        return

    ok, txns, err = extract_transactions(pdf_path, password=password, bank_type="unionbank")

    assert ok, err
    assert len(txns) > 0

    # Guard against false positives: non-transaction sections that might be mistakenly parsed.
    banned_phrases = [
        "CREDIT LIMIT",
        "MINIMUM AMOUNT DUE",
        "AMOUNT DUE",
        "PREVIOUS PURCHASES",
        "FINANCE CHARGE",
        "STATEMENT DATE",
        "ENDING BALANCE",
    ]

    for t in txns:
        desc = (t.get("description") or "").upper()
        assert all(p not in desc for p in banned_phrases)
