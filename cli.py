"""Command-line admin portal for the inventory API.

Start the API first (python app.py), then run:  python cli.py
Set INVENTORY_API_URL to point at a different server.
"""
import os

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")
TIMEOUT = 15


# ---------------------------------------------------------------------------
# HTTP helpers – each returns (status_code, json_body)
# ---------------------------------------------------------------------------
def api_request(method, path, **kwargs):
    try:
        resp = requests.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException:
        return None, {"error": f"Cannot connect to API at {API_URL}. Is app.py running?"}
    try:
        body = resp.json()
    except ValueError:
        body = {"error": resp.text}
    return resp.status_code, body


def list_items(query=""):
    return api_request("GET", "/inventory", params={"q": query} if query else None)


def get_item(item_id):
    return api_request("GET", f"/inventory/{item_id}")


def add_item(payload):
    return api_request("POST", "/inventory", json=payload)


def update_item(item_id, payload):
    return api_request("PATCH", f"/inventory/{item_id}", json=payload)


def delete_item(item_id):
    return api_request("DELETE", f"/inventory/{item_id}")


def lookup_barcode(barcode):
    return api_request("GET", f"/products/barcode/{barcode}")


def search_products(name):
    return api_request("GET", "/products/search", params={"name": name})


def import_product(barcode, price=0.0, stock=0):
    return api_request("POST", f"/inventory/import/{barcode}",
                       json={"price": price, "stock": stock})


def enrich_item(item_id):
    return api_request("POST", f"/inventory/{item_id}/enrich")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def format_item(item):
    p = item.get("product", {})
    lines = [
        f"[{item.get('id', '-')}] {p.get('product_name', 'Unknown')} ({p.get('brands') or 'no brand'})",
        f"    Barcode: {item.get('barcode') or '-'}   Price: ${float(item.get('price', 0)):.2f}   Stock: {item.get('stock', 0)}",
    ]
    if p.get("quantity"):
        lines.append(f"    Size: {p['quantity']}")
    if p.get("nutriscore_grade"):
        lines.append(f"    Nutri-Score: {p['nutriscore_grade'].upper()}")
    if p.get("ingredients_text"):
        lines.append(f"    Ingredients: {p['ingredients_text']}")
    return "\n".join(lines)


def show_result(status, body, ok_codes=(200, 201)):
    """Print a response; return True on success."""
    if status in ok_codes:
        if isinstance(body, list):
            print("\n".join(format_item(i) for i in body) if body else "No items found.")
        elif "product" in body:
            print(format_item(body))
        else:
            print(body.get("message", body))
        return True
    print(f"Error: {body.get('error', 'Unknown error')}")
    return False


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def prompt(text, required=False):
    while True:
        value = input(text).strip()
        if value or not required:
            return value
        print("This field is required.")


def prompt_number(text, cast=float, default=None):
    while True:
        raw = input(text).strip()
        if not raw:
            return default
        try:
            value = cast(raw)
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            print(f"Please enter a non-negative {'whole ' if cast is int else ''}number.")


def prompt_id():
    return prompt_number("Item ID: ", cast=int)


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------
def action_view_all():
    show_result(*list_items(prompt("Filter by name/brand (blank for all): ")))


def action_view_one():
    item_id = prompt_id()
    if item_id is not None:
        show_result(*get_item(item_id))


def action_add():
    payload = {
        "product": {
            "product_name": prompt("Product name: ", required=True),
            "brands": prompt("Brand: "),
            "ingredients_text": prompt("Ingredients: "),
        },
        "barcode": prompt("Barcode: "),
        "price": prompt_number("Price: ", default=0.0),
        "stock": prompt_number("Stock: ", cast=int, default=0),
    }
    show_result(*add_item(payload))


def action_update():
    item_id = prompt_id()
    if item_id is None:
        return
    status, current = get_item(item_id)
    if not show_result(status, current):
        return
    print("Leave a field blank to keep its current value.")
    payload, product = {}, {}
    for field, label in (("product_name", "Product name"), ("brands", "Brand"),
                         ("ingredients_text", "Ingredients")):
        value = prompt(f"{label}: ")
        if value:
            product[field] = value
    if product:
        payload["product"] = product
    barcode = prompt("Barcode: ")
    if barcode:
        payload["barcode"] = barcode
    price = prompt_number("Price: ")
    if price is not None:
        payload["price"] = price
    stock = prompt_number("Stock: ", cast=int)
    if stock is not None:
        payload["stock"] = stock
    if not payload:
        print("Nothing to update.")
        return
    show_result(*update_item(item_id, payload))


def action_delete():
    item_id = prompt_id()
    if item_id is None:
        return
    if prompt(f"Delete item {item_id}? (y/n): ").lower() == "y":
        show_result(*delete_item(item_id))
    else:
        print("Cancelled.")


def action_lookup_barcode():
    show_result(*lookup_barcode(prompt("Barcode: ", required=True)))


def action_search():
    status, body = search_products(prompt("Product name: ", required=True))
    if status == 200:
        print("\n".join(format_item(r) for r in body) if body else "No products found.")
    else:
        show_result(status, body)


def action_import():
    barcode = prompt("Barcode: ", required=True)
    price = prompt_number("Price: ", default=0.0)
    stock = prompt_number("Stock: ", cast=int, default=0)
    show_result(*import_product(barcode, price, stock))


def action_enrich():
    item_id = prompt_id()
    if item_id is not None:
        show_result(*enrich_item(item_id))


MENU = [
    ("View all inventory", action_view_all),
    ("View one item", action_view_one),
    ("Add item", action_add),
    ("Update item", action_update),
    ("Delete item", action_delete),
    ("Look up product by barcode (OpenFoodFacts)", action_lookup_barcode),
    ("Search products by name (OpenFoodFacts)", action_search),
    ("Import product into inventory by barcode", action_import),
    ("Enrich item details from OpenFoodFacts", action_enrich),
]


def main():
    print("=== Inventory Admin Portal ===")
    while True:
        print()
        for number, (label, _) in enumerate(MENU, start=1):
            print(f"{number}. {label}")
        print("0. Exit")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            break
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            print()
            MENU[int(choice) - 1][1]()
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    main()
