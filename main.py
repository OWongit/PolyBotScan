from asyncio import tasks
import discord
from discord.ext import commands, tasks
import asyncio
import search, json_functs, helper_functs  # external modules
from datetime import datetime
import pytz


# ——— Bot setup ———
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)

# This will hold our channel reference after on_ready fires
SCANNER_ALL = None
SCANNER_FLAGGED = None
SETTINGS = None
DAILY_RUNDOWN = None

# ——— Global Variables ———
USER = None
RUNDOWN_TIME = None
RUNDOWN_FLAG = False

# ——— Start Up Event ———
@bot.event
async def on_ready():
    """
    Callback function executed when the bot is ready.
    Initializes global variables for various Discord channels and user settings by reading from a JSON configuration.
    Caches channel objects to avoid None returns from `get_channel()`.
    Sends a status message to the scanner channel indicating whether the scanner is enabled.
    Starts the scanner and position rundown loops if they are not already running.
    Globals:
        SCANNER_ALL (discord.TextChannel): Channel for unfiltered scanner messages.
        SCANNER_FLAGGED (discord.TextChannel): Channel for flagged buy messages.
        SETTINGS (discord.TextChannel): Channel for bot settings.
        DAILY_RUNDOWN (discord.TextChannel): Channel for daily rundown messages.
        USER (str): Proxywallet user ID.
        RUNDOWN_TIME (Any): Time for daily rundown.
    """
    global SCANNER_ALL
    global SCANNER_FLAGGED
    global SETTINGS
    global DAILY_RUNDOWN
    global USER
    global RUNDOWN_TIME

    # Try cache the channel so get_channel() won't return None later
    SCANNER_ALL = bot.get_channel(json_functs.read("scanner_unfiltered"))
    SCANNER_FLAGGED = bot.get_channel(json_functs.read("flagged_buys"))
    SETTINGS = bot.get_channel(json_functs.read("settings"))
    DAILY_RUNDOWN = bot.get_channel(json_functs.read("daily_rundown"))

    # get user's proxywallet ID
    USER = json_functs.read("user")
    RUNDOWN_TIME = json_functs.read("rundown_time")

    print("Bot is ready!")
    if json_functs.read("scanner_on"):
        await SCANNER_ALL.send("**Starting Scanner...**")
        if not scan_loop.is_running():
            scan_loop.start()
    else:
        await SCANNER_ALL.send("**Scanner is not enabled. Use '-scan' to enable.**")
    if not position_rundown.is_running():
        position_rundown.start()

# ——— Change Settings Command ———
@bot.command()
async def set(key=None, value=None):
    """
    Sets a configuration setting to a specified value.

    If no key or value is provided, sends a message listing all available settings and their current values,
    along with usage instructions.

    Args:
        ctx: The context in which the command was invoked.
        key (str, optional): The name of the setting to update.
        value (any, optional): The new value to assign to the setting.

    Returns:
        None

    Side Effects:
        - Sends a message to the SETTINGS channel with either usage instructions or the result of the setting update.
    """
    settings = json_functs.read()
    if key is None or value is None:
        await SETTINGS.send(
            "```Please provide a setting and value to set. Usage: -set <key> <value>\n\n"
            "Available settings: \n"
            f"rundown_time:           {settings.get('rundown_time')}{((13 - len(str(settings.get('rundown_time')))) * ' ')}<between 0 and 24, integer> \n"
            f"offset:                 {settings.get('offset')}{((13 - len(str(settings.get('offset')))) * ' ')}<greater than 0, integer> \n"
            f"min_volume:             {settings.get('min_volume')}{((13 - len(str(settings.get('min_volume')))) * ' ')}<greater than 0, integer> \n"
            f"min_growth_rate_diff:   {settings.get('min_growth_rate_diff')}{((13 - len(str(settings.get('min_growth_rate_diff')))) * ' ')}<greater than 0, integer> \n"
            f"min_pnl_diff:           {settings.get('min_pnl_diff')}{((13 - len(str(settings.get('min_pnl_diff')))) * ' ')}<greater than 0, integer> \n"
            f"min_bot_count_diff:     {settings.get('min_bot_count_diff')}{((13 - len(str(settings.get('min_bot_count_diff')))) * ' ')}<between 0 and 20, integer> \n"
            f"min_share_price:        {settings.get('min_share_price')}{((13 - len(str(settings.get('min_share_price')))) * ' ')}<between 0.0 and 1.0, float> \n"
            f"max_share_price:        {settings.get('max_share_price')}{((13 - len(str(settings.get('max_share_price')))) * ' ')}<between 0.0 and 1.0, float>```"
        )
    else:
        msg = await json_functs.set_setting(key, value)
        await SETTINGS.send(msg)


# ——— Scan Command ———
@bot.command()
async def scan():
    """
    Starts the market scanning process, continuously checking markets and posting results.
    If the scanner is already running, it will notify the user.
    """
    if SCANNER_ALL is None:
        await SCANNER_ALL.send("**Scanner channel not ready yet. Please try again in a few seconds.**")
        return

    scanner_on = json_functs.read("scanner_on")
    if scanner_on:
        if not scan_loop.is_running():
            scan_loop.start()
        await SCANNER_ALL.send("**Scanner is already configured to be running.**")
    else:
        json_functs.update("scanner_on", True)
        await SCANNER_ALL.send("**Starting Scan…**")
        if not scan_loop.is_running():
            scan_loop.start()


# ——— Stop Scan Command ———
@bot.command()
async def stop_scan():
    """Stop the market scanning."""
    if SCANNER_ALL is None:
        await SCANNER_ALL.send("**Scanner channel not ready yet. Please try again in a few seconds.**")
        return

    scanner_on = json_functs.read("scanner_on")
    if not scanner_on:
        await SCANNER_ALL.send("**Scanner is configured to not be running.**")
        if scan_loop.is_running():
            scan_loop.stop()
        return

    json_functs.update("scanner_on", False)
    await SCANNER_ALL.send("**Stopping scan after current market scan…**")
    if scan_loop.is_running():
        scan_loop.stop()


# ——— Market Scan Logic ———
@tasks.loop()
async def scan_loop():
    """Continuously scan markets and post results."""

    try:
        # Load the settings from the JSON file
        settings = json_functs.read()

        # get market data and flagged markets
        market = await search.get_market(settings["min_volume"], settings["offset"])
        flagged = json_functs.read("markets", file_path="storage/flagged_markets.json")

        # Check if the market is None or if its conditionId is in flagged markets (means every market has been scanned)
        if market is None:
            settings = json_functs.iterate("offset", -settings["offset"])
            offset, scanner_on = settings["offset"], settings["scanner_on"]
            return

        # If the market's conditionId is in flagged markets, skip it
        if market.get("conditionId") in flagged:
            settings = json_functs.iterate("offset", 1)
            offset, scanner_on = settings["offset"], settings["scanner_on"]
            return

        condition_id = market["conditionId"]
        question = market["question"]
        print(f"Question: {question}")

        # unpack market data
        sheets_data, msg, results = await search.organize_market_data(condition_id, market)

        # Send the message to the flagged-buys channel if the market meets the criteria
        flag_market = await search.flag_market(results, settings)
        if flag_market:
            json_functs.append_flagged_markets(condition_id)
            await SCANNER_FLAGGED.send(f"** Buy {flag_market}**\n" + "----------------\n" + msg)
            sheets_data.insert(0, f"BUY {flag_market}")
        else:
            sheets_data.insert(0, "NO FLAG")

        # send to unfiltered channel and google sheets regardless of flag
        await SCANNER_ALL.send(msg)

        if condition_id not in json_functs.read("markets", file_path="storage/in_sheets.json"):
            await helper_functs.insert_row_at_top(sheets_data)
            json_functs.append_flagged_markets(condition_id, file_path="storage/in_sheets.json")
        elif flag_market:
            await helper_functs.insert_row_at_top(sheets_data)

        # Update the offset for the next market and check if scanning should continue
        settings = json_functs.iterate("offset", 1)
        offset, scanner_on = settings["offset"], settings["scanner_on"]

    except asyncio.CancelledError:
        await SCANNER_ALL.send("**Market scan stopped.**")
    except Exception as e:
        await SCANNER_ALL.send(f"**Error during scan: {e}**")
        raise


# ——— Position Rundown Logic ———
@tasks.loop(minutes=15)
async def position_rundown():
    """
    Generates and sends a daily rundown message of user positions at a specified hour.
    This asynchronous function checks the current time against a predefined rundown hour (`RUNDOWN_TIME`).
    If the rundown has not yet been sent for the day (`RUNDOWN_FLAG` is False), it retrieves the user's positions,
    formats a summary message including the date, time, and total positions, and sends it to the designated channel (`DAILY_RUNDOWN`).
    For each position, it fetches and organizes market data to append to the message.
    After sending, it sets the rundown flag to prevent duplicate sends within the same hour.
    Resets the flag when the hour changes.
    Globals:
        RUNDOWN_FLAG (bool): Tracks if the rundown has been sent for the current hour.
        RUNDOWN_TIME (int): The hour (in 24-hour format) to send the rundown.
        USER: The user identifier for position lookup.
        DAILY_RUNDOWN: The channel or object to send the rundown message.
    Returns:
        None
    """
    global RUNDOWN_FLAG
    now = datetime.now(pytz.timezone("US/Pacific"))

    if now.hour == RUNDOWN_TIME and not RUNDOWN_FLAG:
        data = await search.get_position(user=USER, condition_id=None)
        condition_ids = [item["conditionId"] for item in data if "conditionId" in item]
        MESSAGE = (
            "**-------- Daily Rundown -------**\n"
            f"Date: {now.date()}\n"
            f"Time: {now.strftime("%I:%M %p")}\n"
            f"Total Positions: {len(condition_ids)}\n"
            "**--------------------------------**\n"
        )
        for conditionId in condition_ids:
            market = await search.get_market(min_volume=None, offset=None, condition_ids=conditionId)
            market = market[0] if isinstance(market, list) else market
            _, msg, _ = await search.organize_market_data(conditionId, market)
            MESSAGE += msg + "**--------------------------------**\n"
        await DAILY_RUNDOWN.send(MESSAGE)
        RUNDOWN_FLAG = True
    elif now.hour != RUNDOWN_TIME and RUNDOWN_FLAG:
        RUNDOWN_FLAG = False


# ——— Run Bot ———
if __name__ == "__main__":
    token = json_functs.read("Bot_Token")
    bot.run(token)
