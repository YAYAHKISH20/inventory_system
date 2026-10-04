"""Mock database: a list (array) of inventory items.

Each item mirrors the shape of an OpenFoodFacts API response
({"status": 1, "product": {...}}) and adds store-specific fields:
an ``id`` (our primary key), ``barcode``, ``price`` and ``stock``.
"""
import copy

SEED_DATA = [
    {
        "id": 1,
        "barcode": "0025293600232",
        "price": 3.99,
        "stock": 40,
        "status": 1,
        "product": {
            "product_name": "Organic Almond Milk",
            "brands": "Silk",
            "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, locust bean gum",
            "categories": "Plant-based beverages, Almond milks",
            "quantity": "1.89 L",
            "nutriscore_grade": "c",
        },
    },
    {
        "id": 2,
        "barcode": "3017620422003",
        "price": 5.49,
        "stock": 25,
        "status": 1,
        "product": {
            "product_name": "Nutella",
            "brands": "Ferrero",
            "ingredients_text": "Sugar, palm oil, hazelnuts 13%, skimmed milk powder 8.7%, fat-reduced cocoa 7.4%, emulsifier: lecithins (soya), vanillin",
            "categories": "Spreads, Sweet spreads, Hazelnut spreads",
            "quantity": "400 g",
            "nutriscore_grade": "e",
        },
    },
    {
        "id": 3,
        "barcode": "5449000000996",
        "price": 1.25,
        "stock": 120,
        "status": 1,
        "product": {
            "product_name": "Coca-Cola",
            "brands": "Coca-Cola",
            "ingredients_text": "Carbonated water, sugar, colour (caramel E150d), acid (phosphoric acid), natural flavourings including caffeine",
            "categories": "Beverages, Carbonated drinks, Sodas",
            "quantity": "330 ml",
            "nutriscore_grade": "e",
        },
    },
]

inventory = copy.deepcopy(SEED_DATA)


def reset_inventory():
    """Restore the seed data (used by tests)."""
    inventory.clear()
    inventory.extend(copy.deepcopy(SEED_DATA))
