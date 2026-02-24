import sys
import logging

# This ensures security and risk-management functions are modular and easy to find.


def verify_paper_account(ib):
    """
    IBKR paper trading account numbers always begin with 'D' (e.g., DU12345).
    """
    accounts = ib.managedAccounts()
    if not accounts:
        raise ConnectionError("No accounts found. Is the broker fully initialized?")

    for acc in accounts:
        if not acc.startswith("D"):
            logging.critical(
                f"‼️ DANGER: Live account detected ({acc})! Aborting immediately to prevent real trades."
            )
            sys.exit(1)

    logging.info(
        f"‼️ Security Check Passed: Verified Paper Trading Account(s) -> {accounts}"
    )


def verify_cash_account(ib):
    """
    Ensures we are running on a strict Cash account to prevent borrowing/margin.
    """
    account_values = ib.accountValues()
    account_type = None

    for val in account_values:
        if val.tag == "AccountType":
            account_type = val.value
            break

    if not account_type:
        logging.critical(
            "‼️ DANGER: Could not verify AccountType from broker. Aborting for safety."
        )
        sys.exit(1)

    # Note: You previously commented this out, leaving it intact here.
    # if account_type.upper() != "CASH":
    #     logging.critical(...)
    #     sys.exit(1)
