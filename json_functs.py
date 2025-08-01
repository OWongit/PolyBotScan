import json


def read(key=None, file_path="storage/config.json"):
    """
    Reads data from a JSON file and optionally retrieves the value for a specified key.

    Args:
        key (str, optional): The key whose value should be retrieved from the JSON data. If None, returns the entire data.
        file_path (str, optional): The path to the JSON file. Defaults to "storage/my_config.json".

    Returns:
        Any: The value associated with the specified key if provided, otherwise the entire JSON data as a dictionary.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get(key) if key else data


def update(key, value, file_path="storage/config.json"):
    """
    Updates the value associated with a given key in a JSON file.

    Args:
        key (str): The key to update in the JSON data.
        value (Any): The new value to assign to the key.
        file_path (str, optional): Path to the JSON file. Defaults to "storage/my_config.json".

    Returns:
        dict: The updated JSON data as a dictionary.

    Raises:
        FileNotFoundError: If the specified JSON file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key:
        data[key] = value
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    return data


def iterate(key, iteration, file_path="storage/config.json"):
    """
    Increments the value of a specified key in the JSON file by a given iteration amount.

    Args:
        key (str): The key to update in the JSON data.
        iteration (int): The amount to increment the key's value by.
        file_path (str, optional): Path to the JSON file. Defaults to "storage/my_config.json".

    Returns:
        dict: The updated JSON data as a dictionary.

    Raises:
        FileNotFoundError: If the specified JSON file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if type(data[key]) == int:
        data[key] = data[key] + iteration
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    return data


def append_flagged_markets(value, file_path="storage/flagged_markets.json"):
    """
    Appends a given market value to the 'markets' list in a JSON file.

    Args:
        value (Any): The market value to append to the list.
        file_path (str, optional): Path to the JSON file containing flagged markets. Defaults to "storage/flagged_markets.json".

    Returns:
        dict: The updated data loaded from the JSON file after appending the value.

    Raises:
        FileNotFoundError: If the specified JSON file does not exist.
        json.JSONDecodeError: If the JSON file contains invalid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if value:
        data.get("markets", []).append(value)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data


def remove_flagged_markets(value, file_path="storage/flagged_markets.json"):
    """
    Removes a given market value from the 'markets' list in a JSON file.

    Args:
        value (Any): The market value to remove from the list.
        file_path (str, optional): Path to the JSON file containing flagged markets. Defaults to "storage/flagged_markets.json".

    Returns:
        dict: The updated data loaded from the JSON file after removing the value.

    Raises:
        FileNotFoundError: If the specified JSON file does not exist.
        json.JSONDecodeError: If the JSON file contains invalid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if value:
        data.get("markets", []).remove(value)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data


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
    valid_keys = [
        "rundown_time",
        "offset",
        "min_volume",
        "min_growth_rate_diff",
        "min_pnl_diff",
        "min_bot_count_diff",
        "min_share_price",
        "max_share_price",
    ]
    if key not in valid_keys:
        return "```Invalid setting. Valid settings are: \n" + ", ".join(valid_keys) + "```"
    else:
        if key in ["min_share_price", "max_share_price"]:
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
                if key == "min_bot_count_diff" and (value < 0 or value > 20):
                    return "```Minimum bot count difference must be between 0 and 20.```"
                if key == "rundown_time" and (value < 0 or value > 24):
                    return "```Rundown time must be between 0 and 24 (military time)```"

                update(key, value)
                return f"```Setting '{key}' updated from {old_setting} to: {value}```"
            except ValueError:
                return "```Invalid value for integer settings. Please provide a valid integer value.```"
