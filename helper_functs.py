import gspread
from oauth2client.service_account import ServiceAccountCredentials


async def insert_row_at_top(insert):
    # 1) Define the scopes
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("storage/my_sheets_key.json",SCOPES)
    client = gspread.authorize(creds)

    # 3) Open your spreadsheet by URL
    spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/13DQJk0G1Dgw8Jcae0vQbqhzrNXjShquQByw0mQMAeDE/edit?gid=0#gid=0")
    sheet = spreadsheet.sheet1

    # 5) Insert at the very top
    sheet.insert_row(insert, index=3, value_input_option='USER_ENTERED')

# This function computes the scaled average of values weighted by their sizes.
async def scaled_avg(vals, sizes):
    # avg sum(val*size) / (sum(sizes) * count)
    if (sum(sizes) * len(vals)) == 0:
        return 0
    return sum(v*s for v, s in zip(vals, sizes)) / (sum(sizes) * len(vals))

# This function computes the average proportion of sizes to accounts.
async def avg_prop(sizes, accounts):
    # avg sum(sizes / accounts) / len(sizes)
    if sum(accounts) == 0:
        return 0
    return sum(s/a for s, a in zip(sizes, accounts) if a != 0) / len(sizes)

