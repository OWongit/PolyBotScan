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