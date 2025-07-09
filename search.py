import asyncio
import aiohttp

# Base API endpoints
BASE_GAMMA = "https://gamma-api.polymarket.com"
BASE_DATA  = "https://data-api.polymarket.com"
BASE_PNL   = "https://user-pnl-api.polymarket.com"


async def _get(url, **params):
    """Helper to send GET requests asynchronously and return parsed JSON."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={k: str(v) for k, v in params.items()}) as resp:
            resp.raise_for_status()
            return await resp.json()

async def get_market(min_volume, offset):
    """Fetch an active, open market with at least `min_volume`, skipping `offset` entries."""
    markets = await _get(
        f"{BASE_GAMMA}/markets",
        limit=1,
        offset=offset,
        active="true",
        closed="false",
        volume_num_min=min_volume
    )

    if markets is None or len(markets) == 0:
        return None
    return markets[0]

async def get_holders(condition_id):
    """Return two lists of proxy wallets for the holders of a given market."""
    groups = await _get(f"{BASE_DATA}/holders", market=condition_id)
    return [[h['proxyWallet'] for h in g['holders']] for g in groups]

async def get_position(user, condition_id):
    """Return (currentValue, cashPnl) for a user in a market, or (0, 0) if none exists."""
    data = await _get(
        f"{BASE_DATA}/positions",
        user=user,
        market=condition_id
    )
    if data:
        return data[0]["currentValue"], data[0]["cashPnl"]
    return 0, 0

async def get_market_data(condition_id):
    """Aggregate growth rates, PNLs, position sizes, account sizes, and bot flags per holder group."""
    keys = ["growth_rates", "PNLs", "pos_size", "account_size", "is_bot"]
    data = {k: [] for k in keys}

    for group in await get_holders(condition_id):
        group_metrics = {k: [] for k in keys}
        for user in group:
            pnl_history = await _get(
                f"{BASE_PNL}/user-pnl",
                user_address=user,
                interval="max",
                fidelity="12h"
            )
            
            if len(pnl_history) < 2: # Not enough data to compute metrics for this user
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
            trades = await _get(
                f"{BASE_DATA}/activity",
                user=user,
                limit=500,
                sortDirection="DESC",
                type="TRADE"
            )
            span_days = (trades[0]["timestamp"] - trades[-1]["timestamp"]) / 86400
            group_metrics["is_bot"].append(len(trades) == 500 and span_days < 50)

        # Append each metric list for this group
        for k in keys:
            data[k].append(group_metrics[k])

    return data

async def flag_market(results, settings):           #currentlt setting things to float, may change later in main.py, send over float value rather than string
    # Check for yes:
    if float(results['prices'][0]) > settings['min_share_price'] and float(results['prices'][0]) < settings['max_share_price']:
        if float(results['Scaled Growth Avg']['yes']) - float(results['Scaled Growth Avg']['no']) > settings['min_growth_rate_diff']:
            return 'YES'
    # Check for no:
    if float(results['prices'][1]) > settings['min_share_price'] and float(results['prices'][1]) < settings['max_share_price']:
        if float(results['Scaled Growth Avg']['no']) - float(results['Scaled Growth Avg']['yes']) > settings['min_growth_rate_diff']:
            return 'NO'
    return None


#helpers
async def scaled_avg(vals, sizes):
    # sum(val*size) / (sum(sizes) * count)
    if (sum(sizes) * len(vals)) == 0:
        return 0
    return sum(v*s for v, s in zip(vals, sizes)) / (sum(sizes) * len(vals))

async def avg_prop(sizes, accounts):
    if sum(accounts) == 0:
        return 0
    return sum(s/a for s, a in zip(sizes, accounts) if a != 0) / len(sizes)
    
