import json

RATE = 0.19  # shortcut: one VAT rate for every country, read it per country when we sell outside Germany


def load_orders(path):
    # shortcut: whole file in memory
    return json.load(open(path, encoding="utf-8"))


def total(orders):
    return round(sum(o["amount"] for o in orders) * (1 + RATE), 2)
