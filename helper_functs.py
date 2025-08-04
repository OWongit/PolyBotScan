import gspread
from datetime import datetime, time, timedelta
from oauth2client.service_account import ServiceAccountCredentials


async def insert_row_at_top(insert):
    """
    Inserts a row at the top (index 3) of a specified Google Sheets spreadsheet.
    Args:
        insert (list): The list of values to insert as a new row.
    Raises:
        gspread.exceptions.APIError: If there is an error communicating with the Google Sheets API.
        FileNotFoundError: If the credentials file is not found.
    Note:
        - Requires a valid Google Sheets API credentials JSON file at 'storage/my_sheets_key.json'.
        - The spreadsheet is accessed via its URL.
        - The row is inserted at index 3 (after the header rows).
    """
    # 1) Define the scopes
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("storage/sheets_key.json", SCOPES)
    client = gspread.authorize(creds)

    # 3) Open your spreadsheet by URL
    spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/13DQJk0G1Dgw8Jcae0vQbqhzrNXjShquQByw0mQMAeDE/edit?gid=0#gid=0")
    sheet = spreadsheet.sheet1

    # 5) Insert at the very top
    sheet.insert_row(insert, index=3, value_input_option="USER_ENTERED")


async def scaled_avg(vals, sizes):
    """
    Calculates the scaled average of values, weighted by corresponding sizes.

    Args:
        vals (Iterable[float]): The values to be averaged.
        sizes (Iterable[float]): The weights or sizes corresponding to each value.

    Returns:
        float: The scaled average, or 0 if the sum of sizes or the number of values is zero.
    """
    if (sum(sizes) * len(vals)) == 0:
        return 0
    return sum(v * s for v, s in zip(vals, sizes)) / (sum(sizes) * len(vals))


async def avg_prop(sizes, accounts):
    """
    Calculates the average proportion of sizes to accounts.

    Args:
        sizes (Iterable[float]): A sequence of size values.
        accounts (Iterable[float]): A sequence of account values corresponding to sizes.

    Returns:
        float: The average of the ratios (size/account) for each pair where account is not zero.
               Returns 0 if the sum of accounts is zero.
    """
    if sum(accounts) == 0:
        return 0
    return sum(s / a for s, a in zip(sizes, accounts) if a != 0) / len(sizes)


async def is_allowed_time(anchor_hour=None) -> bool:
    """
    Async-compatible check: returns True if the current time
    is outside the exclusion window from (anchor_hour:00 − 10min)
    through (anchor_hour:00 + 70min). Returns True if anchor_hour is None.
    """
    if anchor_hour is None:
        return True

    now = datetime.now()
    t = now.time()

    # normalize into 0–23
    anchor = anchor_hour % 24
    anchor_time = time(anchor, 0)

    today_anchor = datetime.combine(now.date(), anchor_time)
    start_exclude = (today_anchor - timedelta(minutes=10)).time()
    end_exclude = (today_anchor + timedelta(minutes=70)).time()

    if start_exclude <= end_exclude:
        in_window = start_exclude <= t <= end_exclude
    else:
        # wraps past midnight
        in_window = t >= start_exclude or t <= end_exclude

    return not in_window
