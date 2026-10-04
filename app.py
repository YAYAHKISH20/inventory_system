"""Flask REST API for inventory management.

Inventory lives in the in-memory list ``data.inventory`` (simulated database).
Run with:  python app.py   (serves on http://127.0.0.1:5000)
"""
from flask import Flask, jsonify, request

import data
from external_api import (
    PRODUCT_FIELDS,
    ExternalAPIError,
    fetch_product_by_barcode,
    search_products_by_name,
)

TOP_LEVEL_FIELDS = {"barcode", "price", "stock", "product"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _next_id():
    return max((item["id"] for item in data.inventory), default=0) + 1


def _find(item_id):
    return next((i for i in data.inventory if i["id"] == item_id), None)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate(payload, partial=False):
    """Return an error message, or None if the payload is valid."""
    if not isinstance(payload, dict):
        return "Request body must be a JSON object"
    unknown = set(payload) - TOP_LEVEL_FIELDS
    if unknown:
        return f"Unknown field(s): {', '.join(sorted(unknown))}"

    product = payload.get("product")
    if product is not None:
        if not isinstance(product, dict):
            return "'product' must be an object"
        bad = set(product) - set(PRODUCT_FIELDS)
        if bad:
            return f"Unknown product field(s): {', '.join(sorted(bad))}"
    if not partial and not (product or {}).get("product_name"):
        return "'product.product_name' is required"
    if partial and product is not None and "product_name" in product and not product["product_name"]:
        return "'product.product_name' cannot be empty"

    if "price" in payload and (not _is_number(payload["price"]) or payload["price"] < 0):
        return "'price' must be a non-negative number"
    if "stock" in payload and (
        not isinstance(payload["stock"], int) or isinstance(payload["stock"], bool) or payload["stock"] < 0
    ):
        return "'stock' must be a non-negative integer"
    if "barcode" in payload and not isinstance(payload["barcode"], str):
        return "'barcode' must be a string"
    return None


def _error(message, status):
    return jsonify(error=message), status


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)

    # ---------------- READ ----------------
    @app.get("/inventory")
    def list_items():
        """All items. Optional ?q= filters by product name / brand."""
        q = request.args.get("q", "").strip().lower()
        items = data.inventory
        if q:
            items = [
                i for i in items
                if q in i["product"].get("product_name", "").lower()
                or q in i["product"].get("brands", "").lower()
            ]
        return jsonify(items), 200

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        item = _find(item_id)
        return (jsonify(item), 200) if item else _error("Item not found", 404)

    # ---------------- CREATE ----------------
    @app.post("/inventory")
    def add_item():
        payload = request.get_json(silent=True)
        error = _validate(payload)
        if error:
            return _error(error, 400)
        item = {
            "id": _next_id(),
            "barcode": payload.get("barcode", ""),
            "price": payload.get("price", 0.0),
            "stock": payload.get("stock", 0),
            "status": 1,
            "product": dict(payload["product"]),
        }
        data.inventory.append(item)
        return jsonify(item), 201

    # ---------------- UPDATE ----------------
    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        item = _find(item_id)
        if item is None:
            return _error("Item not found", 404)
        payload = request.get_json(silent=True)
        error = _validate(payload, partial=True)
        if error:
            return _error(error, 400)
        for key in ("barcode", "price", "stock"):
            if key in payload:
                item[key] = payload[key]
        if "product" in payload:
            item["product"].update(payload["product"])
        return jsonify(item), 200

    # ---------------- DELETE ----------------
    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        item = _find(item_id)
        if item is None:
            return _error("Item not found", 404)
        data.inventory.remove(item)
        return jsonify(message=f"Item {item_id} deleted", item=item), 200

    # ---------------- EXTERNAL API (OpenFoodFacts) ----------------
    @app.get("/products/barcode/<barcode>")
    def lookup_barcode(barcode):
        try:
            result = fetch_product_by_barcode(barcode)
        except ExternalAPIError as exc:
            return _error(str(exc), 502)
        if result is None:
            return _error("Product not found on OpenFoodFacts", 404)
        return jsonify(result), 200

    @app.get("/products/search")
    def search_name():
        name = request.args.get("name", "").strip()
        if not name:
            return _error("Query parameter 'name' is required", 400)
        try:
            results = search_products_by_name(name)
        except ExternalAPIError as exc:
            return _error(str(exc), 502)
        return jsonify(results), 200

    @app.post("/inventory/import/<barcode>")
    def import_from_barcode(barcode):
        """Fetch a product from OpenFoodFacts and add it to the inventory."""
        body = request.get_json(silent=True) or {}
        extra = {k: body[k] for k in ("price", "stock") if k in body}
        error = _validate(extra, partial=True)
        if error:
            return _error(error, 400)
        try:
            result = fetch_product_by_barcode(barcode)
        except ExternalAPIError as exc:
            return _error(str(exc), 502)
        if result is None:
            return _error("Product not found on OpenFoodFacts", 404)
        item = {
            "id": _next_id(),
            "barcode": result["barcode"] or barcode,
            "price": extra.get("price", 0.0),
            "stock": extra.get("stock", 0),
            "status": 1,
            "product": result["product"],
        }
        data.inventory.append(item)
        return jsonify(item), 201

    @app.post("/inventory/<int:item_id>/enrich")
    def enrich_item(item_id):
        """Fill in empty product fields on an item using its barcode."""
        item = _find(item_id)
        if item is None:
            return _error("Item not found", 404)
        if not item.get("barcode"):
            return _error("Item has no barcode to look up", 400)
        try:
            result = fetch_product_by_barcode(item["barcode"])
        except ExternalAPIError as exc:
            return _error(str(exc), 502)
        if result is None:
            return _error("Product not found on OpenFoodFacts", 404)
        for key, value in result["product"].items():
            if value and not item["product"].get(key):
                item["product"][key] = value
        return jsonify(item), 200

    @app.errorhandler(404)
    def not_found(_):
        return _error("Route not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_):
        return _error("Method not allowed", 405)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
