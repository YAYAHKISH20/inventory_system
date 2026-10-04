# Inventory Admin Portal

A Flask REST API and command-line admin portal for managing a small retailer's
inventory, with product details pulled from the
[OpenFoodFacts API](https://openfoodfacts.github.io/openfoodfacts-server/api/).

## Project structure

```
inventory_system/
├── app.py            # Flask REST API (CRUD + OpenFoodFacts routes)
├── data.py           # Mock database: in-memory array of items
├── external_api.py   # OpenFoodFacts client (barcode lookup + name search)
├── cli.py            # Interactive command-line interface
├── requirements.txt
└── tests/
    ├── test_app.py           # API routes
    ├── test_external_api.py  # OpenFoodFacts client (HTTP mocked)
    └── test_cli.py           # CLI helpers and menu flows
```

## Setup

```bash
git clone <your-repo-url> && cd inventory_system
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running

Terminal 1 – start the API:

```bash
python app.py                      # http://127.0.0.1:5000
```

Terminal 2 – start the CLI:

```bash
python cli.py
```

Run the tests (no network needed; external calls are mocked):

```bash
pytest -v
```

## Data model (mock database)

Inventory is stored in the list `data.inventory`. Each item follows the shape of an
OpenFoodFacts response (`status` + nested `product`) and adds store fields:

```json
{
  "id": 1,
  "barcode": "0025293600232",
  "price": 3.99,
  "stock": 40,
  "status": 1,
  "product": {
    "product_name": "Organic Almond Milk",
    "brands": "Silk",
    "ingredients_text": "Filtered water, almonds, cane sugar, ...",
    "categories": "Plant-based beverages, Almond milks",
    "quantity": "1.89 L",
    "nutriscore_grade": "c"
  }
}
```

`id` is assigned by the server (highest existing id + 1, so ids are never reused).
The array resets when the server restarts.

## Route design

| Method | Route | Input | Output | Change to data | CLI option |
|---|---|---|---|---|---|
| GET | `/inventory` | optional `?q=` (name/brand filter) | 200 + list of items | none | 1. View all inventory |
| GET | `/inventory/<id>` | item id in URL | 200 + item, or 404 | none | 2. View one item |
| POST | `/inventory` | JSON: `product.product_name` (required), other `product` fields, `barcode`, `price`, `stock` | 201 + new item, or 400 | appends an item to the array | 3. Add item |
| PATCH | `/inventory/<id>` | id in URL; JSON with any fields to change | 200 + updated item, 400, or 404 | updates fields in place; `product` fields are merged | 4. Update item |
| DELETE | `/inventory/<id>` | id in URL | 200 + message, or 404 | removes the item from the array | 5. Delete item |
| GET | `/products/barcode/<barcode>` | barcode in URL | 200 + `{barcode, product}`, 404, or 502 | none (read from OpenFoodFacts) | 6. Look up by barcode |
| GET | `/products/search?name=` | product name | 200 + list of matches, 400, or 502 | none (read from OpenFoodFacts) | 7. Search by name |
| POST | `/inventory/import/<barcode>` | barcode in URL; optional JSON `price`, `stock` | 201 + new item, 404, or 502 | appends an item built from OpenFoodFacts data | 8. Import by barcode |
| POST | `/inventory/<id>/enrich` | id in URL (item must have a barcode) | 200 + item, 400, 404, or 502 | fills empty `product` fields from OpenFoodFacts, keeps existing values | 9. Enrich item |

Errors are always returned as `{"error": "..."}`. A 502 means OpenFoodFacts could not
be reached or returned an error.

## Example requests

```bash
curl http://127.0.0.1:5000/inventory
curl -X POST http://127.0.0.1:5000/inventory -H "Content-Type: application/json" \
     -d '{"product": {"product_name": "Oat Milk", "brands": "Oatly"}, "price": 4.5, "stock": 10}'
curl -X PATCH http://127.0.0.1:5000/inventory/1 -H "Content-Type: application/json" -d '{"stock": 35}'
curl -X DELETE http://127.0.0.1:5000/inventory/1
curl http://127.0.0.1:5000/products/barcode/3017620422003
curl "http://127.0.0.1:5000/products/search?name=almond%20milk"
curl -X POST http://127.0.0.1:5000/inventory/import/3017620422003 \
     -H "Content-Type: application/json" -d '{"price": 5.49, "stock": 20}'
```

## Notes

- OpenFoodFacts asks clients to send a descriptive `User-Agent`; this is set in `external_api.py`.
- The name search uses OpenFoodFacts' `cgi/search.pl` endpoint and can be slow; requests time out after 10 seconds.

## Development workflow

Features are built on separate branches and merged into `main` through pull requests:

1. `git checkout -b feature-name`
2. Commit changes and push: `git push -u origin feature-name`
3. Open a pull request on GitHub, review, and merge
4. Delete the branch after merging

## Running on another port

If port 5000 is busy:

    flask --app app run --port 5001