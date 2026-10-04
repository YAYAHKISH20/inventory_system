"""OpenFoodFacts API client.

Fetches product details by barcode or by name and normalises them into the
fields our inventory uses.
Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/
"""
import requests

BASE_URL = "https://world.openfoodfacts.org"
HEADERS = {"User-Agent": "InventoryAdminPortal/1.0 (lab project)"}
TIMEOUT = 10


class ExternalAPIError(Exception):
    """Raised when the external API cannot be reached or returns bad data."""


PRODUCT_FIELDS = (
    "product_name", "brands", "ingredients_text", "categories",
    "quantity", "nutriscore_grade", "image_url",
)


def _normalise(product):
    """Return {"barcode": ..., "product": {...}} with only the fields we store."""
    details = {field: product.get(field) or "" for field in PRODUCT_FIELDS}
    details["product_name"] = details["product_name"] or "Unknown"
    return {"barcode": product.get("code", ""), "product": details}


def fetch_product_by_barcode(barcode):
    """Return a normalised product dict, or None if the barcode is unknown."""
    url = f"{BASE_URL}/api/v2/product/{barcode}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Could not reach OpenFoodFacts: {exc}") from exc

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise ExternalAPIError(f"OpenFoodFacts returned HTTP {resp.status_code}")

    data = resp.json()
    if data.get("status") != 1 or "product" not in data:
        return None
    return _normalise(data["product"])


def search_products_by_name(name, page_size=5):
    """Return a list of normalised products matching ``name``."""
    url = f"{BASE_URL}/cgi/search.pl"
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Could not reach OpenFoodFacts: {exc}") from exc

    if resp.status_code != 200:
        raise ExternalAPIError(f"OpenFoodFacts returned HTTP {resp.status_code}")

    return [_normalise(p) for p in resp.json().get("products", [])]
