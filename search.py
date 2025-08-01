import aiohttp
import asyncio
import helper_functs
import json

# Base API endpoints
BASE_GAMMA = "https://gamma-api.polymarket.com"
BASE_DATA = "https://data-api.polymarket.com"
BASE_PNL = "https://user-pnl-api.polymarket.com"


async def _get(url, retries=5, **params):
    """Helper to send GET requests asynchronously and return parsed JSON. Retries on failure."""
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={k: str(v) for k, v in params.items()}) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < retries - 1:
                await asyncio.sleep(100)  # Wait before retrying
            else:
                print(f"API request failed after {retries} attempts: {e}")
                return None  # Or handle as appropriate for your app


async def get_market(min_volume, offset, condition_ids=None):
    """Fetch an active, open market with at least `min_volume`, skipping `offset` entries."""
    if condition_ids:
        market = await _get(
            f"{BASE_GAMMA}/markets",
            condition_ids=condition_ids,
        )
        return market if market else None
    else:
        markets = await _get(f"{BASE_GAMMA}/markets", limit=1, offset=offset, active="true", closed="false", volume_num_min=min_volume)
        if not markets or len(markets) == 0:
            return None
        return markets[0]


async def get_holders(condition_id):
    """Return two lists of proxy wallets for the holders of a given market."""
    groups = await _get(f"{BASE_DATA}/holders", market=condition_id)
    return [[h["proxyWallet"] for h in g["holders"]] for g in groups]


async def get_position(user, condition_id):
    """Return (currentValue, cashPnl) for a user in a market, or (0, 0) if none exists."""
    data = await _get(f"{BASE_DATA}/positions", user=user, market=condition_id)

    if data:
        if not condition_id:
            return data
        return data[0]["currentValue"], data[0]["cashPnl"]
    return 0, 0


async def get_market_data(condition_id):
    """
    Asynchronously retrieves and computes market data metrics for user groups associated with a given condition.
    Args:
        condition_id (str or int): The identifier for the market condition to query user groups.
    Returns:
        dict: A dictionary with the following keys, each mapping to a list of lists (one per group):
            - "growth_rates": List of lists containing the daily growth rates for each user in each group.
            - "PNLs": List of lists containing the profit and loss values for each user in each group.
            - "pos_size": List of lists containing the current position size for each user in each group.
            - "account_size": List of lists containing the account size for each user in each group.
            - "is_bot": List of lists containing boolean values indicating if each user in each group is likely a bot.
    Notes:
        - Users with insufficient PnL history (less than 2 entries) are skipped.
        - The function aggregates metrics per group, as returned by `get_holders(condition_id)`.
        - Bot activity is determined by checking if a user has 500 trades within a 50-day span.
    """
    keys = ["growth_rates", "PNLs", "pos_size", "account_size", "is_bot"]
    data = {k: [] for k in keys}

    for group in await get_holders(condition_id):
        group_metrics = {k: [] for k in keys}
        for user in group:
            pnl_history = await _get(f"{BASE_PNL}/user-pnl", user_address=user, interval="max", fidelity="12h")

            if len(pnl_history) < 2:  # Not enough data to compute metrics for this user
                continue

            curr_val, cash_pnl = await get_position(user, condition_id)
            start, end = pnl_history[0], pnl_history[-1]
            days = (end["t"] - start["t"]) / 86400
            pnl_diff = (end["p"] - start["p"]) - cash_pnl

            # Compute metrics
            group_metrics["growth_rates"].append(round(pnl_diff / days))
            group_metrics["PNLs"].append(round(end["p"] - cash_pnl))
            group_metrics["pos_size"].append(round(curr_val))

            # Get account size
            account = (await _get(f"{BASE_DATA}/value", user=user))[0]["value"]
            group_metrics["account_size"].append(round(account))

            # Determine bot activity by trade span
            trades = await _get(f"{BASE_DATA}/activity", user=user, limit=500, sortDirection="DESC", type="TRADE")
            span_days = (trades[0]["timestamp"] - trades[-1]["timestamp"]) / 86400
            group_metrics["is_bot"].append(len(trades) == 500 and span_days < 50)

        # Append each metric list for this group
        for k in keys:
            data[k].append(group_metrics[k])

    return data


async def organize_market_data(condition_id, market):
    """
    Organizes and computes market data statistics for a given condition and market.
    Args:
        condition_id (str): The unique identifier for the market condition.
        market (dict): The market data dictionary containing relevant fields.
    Returns:
        tuple:
            sheets_data (list): A list of processed market statistics formatted for Google Sheets.
            msg (str): A formatted message string summarizing key market statistics.
            results (dict): A dictionary containing computed statistics and extracted market information.
    Raises:
        ValueError: If the market data is invalid or None.
    The function performs the following:
        - Retrieves and processes market data for the specified condition.
        - Computes scaled averages, proportions, and bot counts for 'yes' and 'no' outcomes.
        - Extracts and formats market information such as volume, prices, question, ticker, and resolve date.
        - Prepares a summary message and a list of statistics for external use (e.g., Google Sheets).
    """
    if not market or not isinstance(market, dict):
        raise ValueError("Market data is invalid or None.")

    md = await get_market_data(condition_id)
    (gr_y, gr_n), (pnl_y, pnl_n), (ps_y, ps_n), (acc_y, acc_n), (bot_y, bot_n) = (
        md[k] for k in ("growth_rates", "PNLs", "pos_size", "account_size", "is_bot")
    )

    # compute results
    results = {
        "Scaled Growth Avg": {
            "yes": round(await helper_functs.scaled_avg(gr_y, ps_y)),
            "no": round(await helper_functs.scaled_avg(gr_n, ps_n)),
        },
        "Scaled PNL Avg": {
            "yes": round(await helper_functs.scaled_avg(pnl_y, ps_y)),
            "no": round(await helper_functs.scaled_avg(pnl_n, ps_n)),
        },
        "Avg Prop of Account": {
            "yes": round(await helper_functs.avg_prop(ps_y, acc_y), 3),
            "no": round(await helper_functs.avg_prop(ps_n, acc_n), 3),
        },
        "Number of Bots": {
            "yes": sum(bot_y) if bot_y is not None else "N/A",
            "no": sum(bot_n) if bot_n is not None else "N/A",
        },
        "volume": round(float(str(market.get("volume", "0")).replace(",", ""))) if market.get("volume") else "N/A",
        "prices": json.loads(market.get("outcomePrices", "[]")),
        "question": market.get("question", "N/A"),
        "ticker": market.get("events", [{}])[0].get("ticker", "N/A") if market.get("events") else "N/A",
        "resolves": market.get("endDate", "N/A"),
    }

    # Prepare data for Google sheets:
    sheets_data = [
        results["question"],
        f"https://polymarket.com/event/{results['ticker']}",
        results["volume"],
        results["resolves"][0:10],
        results["prices"][0],
        results["prices"][1],
        results["Scaled Growth Avg"]["yes"],
        results["Scaled Growth Avg"]["no"],
        abs(results["Scaled Growth Avg"]["yes"] - results["Scaled Growth Avg"]["no"]),
        results["Scaled PNL Avg"]["yes"],
        results["Scaled PNL Avg"]["no"],
        abs(results["Scaled PNL Avg"]["yes"] - results["Scaled PNL Avg"]["no"]),
        results["Avg Prop of Account"]["yes"],
        results["Avg Prop of Account"]["no"],
        abs(results["Avg Prop of Account"]["yes"] - results["Avg Prop of Account"]["no"]),
        results["Number of Bots"]["yes"],
        results["Number of Bots"]["no"],
    ]

    # build message
    msg = (
        f"**{results['question']}**\n"
        f"<https://polymarket.com/event/{results['ticker']}>\n"
        f"```Volume: ${round(results['volume'])}{((10 - len(str(results['volume']))) * ' ')}   YES:      NO:\n"
        f"• Share Price:        ${results['prices'][0]}{((9 - len(str(results['prices'][0]))) * ' ')}${results['prices'][1]}\n"
        f"• Scaled Growth:      {results['Scaled Growth Avg']['yes']}{((10 - len(str(results['Scaled Growth Avg']['yes']))) * ' ')}{results['Scaled Growth Avg']['no']}\n"
        f"• Scaled PNL:         {results['Scaled PNL Avg']['yes']}{((10 - len(str(results['Scaled PNL Avg']['yes']))) * ' ')}{results['Scaled PNL Avg']['no']}\n"
        f"• Prop of Account:    {results['Avg Prop of Account']['yes']}{((10 - len(str(results['Avg Prop of Account']['yes']))) * ' ')}{results['Avg Prop of Account']['no']}\n"
        f"• Number of Bots:     {results['Number of Bots']['yes']}{((10 - len(str(results['Number of Bots']['yes']))) * ' ')}{results['Number of Bots']['no']}```"
    )
    return sheets_data, msg, results


async def flag_market(results, settings):
    """
    Analyzes market results and flags a market as 'YES', 'NO', or None based on price and growth rate criteria. Currently only considers share price and scaled growth averages.

    Args:
        results (dict): A dictionary containing market data, including 'prices' (list of floats or strings)
            and 'Scaled Growth Avg' (dict with 'yes' and 'no' keys).
        settings (dict): A dictionary containing threshold settings:
            - 'min_share_price' (float): Minimum allowed share price.
            - 'max_share_price' (float): Maximum allowed share price.
            - 'min_growth_rate_diff' (float): Minimum required difference in scaled growth averages.

    Returns:
        str or None: Returns 'YES' if the 'yes' market meets the criteria, 'NO' if the 'no' market meets the criteria,
            or None if neither condition is satisfied.
    """
    # TODO: Add more conditions to flag a market, such as volume, account size, etc. (Must analyze market data and evaluate market resolution mechanisms).
    # Check for yes:
    if float(results["prices"][0]) > settings["min_share_price"] and float(results["prices"][0]) < settings["max_share_price"]:
        if float(results["Scaled Growth Avg"]["yes"]) - float(results["Scaled Growth Avg"]["no"]) > settings["min_growth_rate_diff"]:
            return "YES"
    # Check for no:
    if float(results["prices"][1]) > settings["min_share_price"] and float(results["prices"][1]) < settings["max_share_price"]:
        if float(results["Scaled Growth Avg"]["no"]) - float(results["Scaled Growth Avg"]["yes"]) > settings["min_growth_rate_diff"]:
            return "NO"
    return None
