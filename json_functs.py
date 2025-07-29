import json

# This function reads a JSON file and returns the entire content or a specific key's value.
def read(key=None, file_path='storage/my_config.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get(key) if key else data

# This function updates a specific key in the JSON file with a new value.
def update(key, value, file_path='storage/my_config.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if key:
        data[key] = value
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    return data

# This function iterates a numeric value in the JSON file by a specified iteration amount.
def iterate(key, iteration, file_path='storage/my_config.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if type(data[key]) == int:
        data[key] = data[key] + iteration
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    return data

# This function appends a value to the 'flagged_markets' list in the JSON file.
def append_flagged_markets(value, file_path='storage/flagged_markets.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if value:
        data.get('markets', []).append(value)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return data

# This function removes a value from the 'flagged_markets' list in the JSON file.
def remove_flagged_markets(value, file_path='storage/flagged_markets.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if value:
        data.get('markets', []).remove(value)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return data

# This function retrieves and replaces the current value of a specific setting from the config.JSON file.
async def set_setting(key, value):
    """
    Asynchronously updates a configuration setting with a new value after validating the key and value.

    Parameters:
        key (str): The name of the setting to update. Must be one of the valid keys:
            ['offset', 'min_volume', 'min_growth_rate_diff', 'min_pnl_diff', 'min_bot_count_diff', 'min_share_price', 'max_share_price'].
        value (float or int): The new value to set for the specified key. For 'min_share_price' and 'max_share_price', must be a float between 0.0 and 1.0.
            For other keys, must be an integer greater than 0. For 'min_bot_count_diff', must be an integer between 0 and 20.

    Returns:
        str: A formatted message indicating the result of the operation, including validation errors or confirmation of the update.
    """
    old_setting = read(key)
    valid_keys = ['rundown_time', 'offset', 'min_volume', 'min_growth_rate_diff', 'min_pnl_diff', 'min_bot_count_diff', 'min_share_price', 'max_share_price']
    if key not in valid_keys:
        return "```Invalid setting. Valid settings are: \n" + ", ".join(valid_keys) + "```"
    else:
        if key in ['min_share_price', 'max_share_price']:
            try:
                value = float(value)
                if value < 0.0 or value > 1.0:
                    return f"```{key} must be between 0.0 and 1.0```"
                update(key, value)
                return f"```Setting '{key}' updated from {old_setting} to: {value}```"
            except ValueError:
                return "```Invalid value for share price settings. Please provide a valid float value.```"
        else:
            try:
                value = int(value)
                if value <= 0:
                    return f"```{key.replace('_', ' ').title()} must be greater than 0.```"
                if key == 'min_bot_count_diff' and (value < 0 or value > 20):
                    return "```Minimum bot count difference must be between 0 and 20.```"
                if key == 'rundown_time' and (value < 0 or value > 24):
                    return "```Rundown time must be between 0 and 24 (military time)```"

                update(key, value)
                return f"```Setting '{key}' updated from {old_setting} to: {value}```"
            except ValueError:
                return "```Invalid value for integer settings. Please provide a valid integer value.```"