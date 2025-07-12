from modulefinder import test
import discord
import json
from discord.ext import commands
import asyncio
import search, json_functs, helper_functs   # external modules



# ——— Bot setup ———
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='-', intents=intents)

# This will hold our channel reference after on_ready fires
SCANNER_ALL = None
SCANNER_FLAGGED = None
SETTINGS = None

# ——— Start Up Event ———
@bot.event
async def on_ready():
    global SCANNER_ALL
    global SCANNER_FLAGGED
    global SETTINGS

    # Try cache the channel so get_channel() won't return None later
    SCANNER_ALL = bot.get_channel(json_functs.read('scanner_unfiltered'))
    SCANNER_FLAGGED = bot.get_channel(json_functs.read('flagged_buys'))
    SETTINGS = bot.get_channel(json_functs.read('settings'))

    print("Bot is ready!")

@bot.command()
async def set(ctx, key = None, value = None):
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
async def scan(ctx):
    """Continuously scan markets and post results."""
    if SCANNER_ALL is None:
        await ctx.send("Scanner channel not ready yet. Please try again in a few seconds.")
        return

    scanner_on  = json_functs.update('scanner_on', True)['scanner_on']

    await SCANNER_ALL.send("Scanning Markets…")
    try:
        while scanner_on:
            # Load the settings from the JSON file
            settings  = json_functs.read()

            # get market data and flagged markets
            market = await search.get_market(settings['min_volume'], settings['offset'])
            flagged = json_functs.read('markets', file_path='storage/flagged_markets.json')

            # Check if the market is None or if its conditionId is in flagged markets (means every market has been scanned)
            if (market is None):
                settings = json_functs.iterate('offset', -settings['offset'])
                offset, scanner_on = settings['offset'], settings['scanner_on']
                continue

            # If the market's conditionId is in flagged markets, skip it
            if market.get('conditionId') in flagged:
                settings = json_functs.iterate('offset', 1)
                offset, scanner_on = settings['offset'], settings['scanner_on']
                continue

            condition_id = market['conditionId']
            question = market['question']
            print(f"Question: {question}")

            # unpack market data
            md = await search.get_market_data(condition_id)
            (gr_y, gr_n), (pnl_y, pnl_n), (ps_y, ps_n), (acc_y, acc_n), (bot_y, bot_n) = (
                md[k] for k in ('growth_rates','PNLs','pos_size','account_size','is_bot')
            )

            # compute results
            results = {
                "Scaled Growth Avg": {  
                    "yes": round(await helper_functs.scaled_avg(gr_y, ps_y)),
                    "no":  round(await helper_functs.scaled_avg(gr_n, ps_n)),
                },
                "Scaled PNL Avg": {
                    "yes": round(await helper_functs.scaled_avg(pnl_y, ps_y)),
                    "no":  round(await helper_functs.scaled_avg(pnl_n, ps_n)),
                },
                "Avg Prop of Account": {
                    "yes": round(await helper_functs.avg_prop(ps_y, acc_y), 3),
                    "no":  round(await helper_functs.avg_prop(ps_n, acc_n), 3),
                },
                "Number of Bots": {
                    "yes": round(sum(bot_y)),
                    "no":  round(sum(bot_n)),
                },
                "volume": round(float(str(market['volume']).replace(',', ''))),
                "prices": json.loads(market['outcomePrices']),
                "question": question,
                "ticker": market['events'][0]['ticker'],
                "resolves" : market['endDate']
            }

            # Prepare data for Google sheets:
            sheets_data = [
                results['question'],
                f"https://polymarket.com/event/{results['ticker']}",
                results['volume'],
                results['resolves'][0:10],
                results['prices'][0],
                results['prices'][1],
                results['Scaled Growth Avg']['yes'],
                results['Scaled Growth Avg']['no'],
                abs(results['Scaled Growth Avg']['yes'] - results['Scaled Growth Avg']['no']),
                results['Scaled PNL Avg']['yes'],
                results['Scaled PNL Avg']['no'],
                abs(results['Scaled PNL Avg']['yes'] - results['Scaled PNL Avg']['no']),
                results['Avg Prop of Account']['yes'],
                results['Avg Prop of Account']['no'],
                abs(results['Avg Prop of Account']['yes'] - results['Avg Prop of Account']['no']),
                results['Number of Bots']['yes'],
                results['Number of Bots']['no']
            ]

            # build message
            msg = (
                f"**{results['question']}**\n"
                f"```Volume: ${round(results['volume'])}{((10 - len(str(results['volume']))) * ' ')}   YES:      NO:\n"
                f"• Share Price:        ${results['prices'][0]}{((9 - len(str(results['prices'][0]))) * ' ')}${results['prices'][1]}\n"
                f"• Scaled Growth:      {results['Scaled Growth Avg']['yes']}{((10 - len(str(results['Scaled Growth Avg']['yes']))) * ' ')}{results['Scaled Growth Avg']['no']}\n"
                f"• Scaled PNL:         {results['Scaled PNL Avg']['yes']}{((10 - len(str(results['Scaled PNL Avg']['yes']))) * ' ')}{results['Scaled PNL Avg']['no']}\n"
                f"• Prop of Account:    {results['Avg Prop of Account']['yes']}{((10 - len(str(results['Avg Prop of Account']['yes']))) * ' ')}{results['Avg Prop of Account']['no']}\n"
                f"• Number of Bots:     {results['Number of Bots']['yes']}{((10 - len(str(results['Number of Bots']['yes']))) * ' ')}{results['Number of Bots']['no']}```"
                f"https://polymarket.com/event/{results['ticker']}"
            )

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

            if condition_id not in json_functs.read('markets', file_path='storage/in_sheets.json'):
                await helper_functs.insert_row_at_top(sheets_data)
                json_functs.append_flagged_markets(condition_id, file_path='storage/in_sheets.json')
            elif flag_market:
                await helper_functs.insert_row_at_top(sheets_data)
            
            # Update the offset for the next market and check if scanning should continue
            settings = json_functs.iterate('offset', 1)
            offset, scanner_on = settings['offset'], settings['scanner_on']

            # avoid spamming and rate‐limits
            await asyncio.sleep(5)
        await SCANNER_ALL.send("Market scanning stopped.")

    except asyncio.CancelledError:
        await scanner_unfiltered.send("Market scan stopped.")
    except Exception as e:
        await SCANNER_ALL.send(f"Error during scan: {e}")
        raise

# ——— Stop Scan Command ———
@bot.command()
async def stop_scan(ctx):
    """Stop the market scanning."""
    json_functs.update('scanner_on', False)
    await SCANNER_ALL.send("Stopping scan after current market scan…")

# ——— Run Bot ———
if __name__ == '__main__':
    token = json_functs.read('Server_Token')
    bot.run(token)
