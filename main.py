import discord
import json
from discord.ext import commands
import asyncio
import search, json_functions   # external modules



# ——— Bot setup ———
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='-', intents=intents)

# This will hold our channel reference after on_ready fires
scanner_unfiltered = None
flagged_buys = None


# ——— Event handlers ———
@bot.event
async def on_ready():
    global scanner_unfiltered
    global flagged_buys

    # Try cache the channel so get_channel() won't return None later
    scanner_unfiltered = bot.get_channel(json_functions.read('scanner_unfiltered'))
    flagged_buys = bot.get_channel(json_functions.read('flagged_buys'))

    print("Bot is ready!")

# ——— Commands ———
@bot.command()
async def hello(ctx):
    """A simple test command."""
    await ctx.send("testing hello command")
    print("testing hello")

# ——— Set Offset Command ———
@bot.command()
async def scan(ctx):
    """Continuously scan markets and post results."""
    if scanner_unfiltered is None:
        await ctx.send("Scanner channel not ready yet. Please try again in a few seconds.")
        return

    scanner_on  = json_functions.update('scanner_on', True)['scanner_on']

    await scanner_unfiltered.send("Scanning Markets…")
    try:
        while scanner_on:
            # Load the settings from the JSON file
            settings  = json_functions.read()

            # get market data and flagged markets
            market = await search.get_market(settings['min_volume'], settings['offset'])
            flagged = set(json_functions.append_flagged_markets(None)['flagged_markets'])

            # Check if the market is None or if its conditionId is in flagged markets (means every market has been scanned)
            if (market is None):
                settings = json_functions.iterate('offset', -settings['offset'])
                offset, scanner_on = settings['offset'], settings['scanner_on']
                continue

            # If the market's conditionId is in flagged markets, skip it
            if market.get('conditionId') in flagged:
                settings = json_functions.iterate('offset', 1)
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
                    "yes": round(await search.scaled_avg(gr_y, ps_y)),
                    "no":  round(await search.scaled_avg(gr_n, ps_n)),
                },
                "Scaled PNL Avg": {
                    "yes": round(await search.scaled_avg(pnl_y, ps_y)),
                    "no":  round(await search.scaled_avg(pnl_n, ps_n)),
                },
                "Avg Prop of Account": {
                    "yes": round(await search.avg_prop(ps_y, acc_y), 3),
                    "no":  round(await search.avg_prop(ps_n, acc_n), 3),
                },
                "Number of Bots": {
                    "yes": round(sum(bot_y)),
                    "no":  round(sum(bot_n)),
                },
                "volume": round(float(str(market['volume']).replace(',', ''))),
                "prices": json.loads(market['outcomePrices']),
                "question": question,
                "ticker": market['events'][0]['ticker']
            }

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
                json_functions.append_flagged_markets(condition_id)
                await flagged_buys.send(f"** Buy {flag_market}**\n" + "----------------\n" + msg)
            
            # send to unfiltered channel regardless of flag
            await scanner_unfiltered.send(msg)

            # Update the offset for the next market and check if scanning should continue
            settings = json_functions.iterate('offset', 1)
            offset, scanner_on = settings['offset'], settings['scanner_on']

            # avoid spamming and rate‐limits
            await asyncio.sleep(5)
        await scanner_unfiltered.send("Market scanning stopped.")

    except asyncio.CancelledError:
        await scanner_unfiltered.send("Market scan stopped.")
    except Exception as e:
        await scanner_unfiltered.send(f"Error during scan: {e}")
        raise

# ——— Stop Scan Command ———
@bot.command()
async def stop_scan(ctx):
    """Stop the market scanning."""
    # Check if the scanner channel is ready
    with open('sets.json', 'r', encoding='utf-8') as f:        
        settings = json.load(f)
        settings['scanner_on'] = False
    with open('sets.json', 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
    await scanner_unfiltered.send("Stopping scan after current market scan…")

# ——— Run Bot ———
if __name__ == '__main__':
    token = json_functions.read('Server_Token')
    bot.run(token)
