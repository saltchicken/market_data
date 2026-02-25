import sys
import logging


def _abort_security_check(message):
    """
    Extracted the critical failure state to ensure consistent
    logging and exiting across all security checks.
    """
    logging.critical(
        f"‼️ DANGER: {message} Aborting immediately to prevent real trades."
    )
    sys.exit(1)


def verify_paper_account(ib):
    """
    IBKR paper trading account numbers always begin with 'D' (e.g., DU12345).
    """
    accounts = ib.managedAccounts()
    if not accounts:
        raise ConnectionError("No accounts found. Is the broker fully initialized?")

    for acc in accounts:
        if not acc.startswith("D"):

            _abort_security_check(f"Live account detected ({acc})!")

    logging.info(
        f"Security Check Passed: Verified Paper Trading Account(s) -> {accounts}"
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

        _abort_security_check("Could not verify AccountType from broker.")

    # Note: You previously commented this out, leaving it intact here.
    # if account_type.upper() != "CASH":
    #     _abort_security_check(f"Account is not CASH (Found: {account_type}).")
