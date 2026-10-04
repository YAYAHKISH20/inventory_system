"""Tests for the Flask REST API (CRUD + external API routes)."""
from unittest.mock import patch

import pytest

import data
from app import create_app
from external_api import ExternalAPIError

OFF_RESULT = {
    "barcode": "737628064502",
    "product": {
        "product_name": "Thai Peanut Noodle Kit",
        "brands": "Simply Asia",
        "ingredients_text": "Rice noodles, peanuts",
        "categories": "Noodles",
        "quantity": "155 g",
        "nutriscore_grade": "d",
        "image_url": "",
    },
}


@pytest.fixture
def client():
    data.reset_inventory()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------- READ ----------------
def test_list_inventory(client):
    resp = client.get("/inventory")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 3


def test_list_inventory_filter(client):
    resp = client.get("/inventory?q=ferrero")
    assert [i["id"] for i in resp.get_json()] == [2]


def test_items_have_id_and_off_shape(client):
    for item in client.get("/inventory").get_json():
        assert "id" in item and item["status"] == 1
        assert "product_name" in item["product"]


def test_get_item(client):
    resp = client.get("/inventory/1")
    assert resp.status_code == 200
    assert resp.get_json()["product"]["product_name"] == "Organic Almond Milk"


def test_get_missing_item(client):
    resp = client.get("/inventory/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ---------------- CREATE ----------------
def test_add_item(client):
    payload = {"product": {"product_name": "Oat Milk", "brands": "Oatly"}, "price": 4.5, "stock": 10}
    resp = client.post("/inventory", json=payload)
    assert resp.status_code == 201
    item = resp.get_json()
    assert item["id"] == 4 and item["stock"] == 10
    assert len(data.inventory) == 4


def test_add_item_defaults(client):
    item = client.post("/inventory", json={"product": {"product_name": "Bread"}}).get_json()
    assert item["price"] == 0.0 and item["stock"] == 0 and item["barcode"] == ""


@pytest.mark.parametrize("payload, message", [
    ({}, "product_name"),
    ({"product": {"brands": "X"}}, "product_name"),
    ({"product": {"product_name": "X"}, "price": -1}, "price"),
    ({"product": {"product_name": "X"}, "stock": 2.5}, "stock"),
    ({"product": {"product_name": "X"}, "colour": "red"}, "Unknown field"),
    ({"product": {"product_name": "X", "foo": 1}}, "Unknown product field"),
])
def test_add_item_validation(client, payload, message):
    resp = client.post("/inventory", json=payload)
    assert resp.status_code == 400
    assert message in resp.get_json()["error"]
    assert len(data.inventory) == 3


def test_add_item_non_json(client):
    resp = client.post("/inventory", data="not json")
    assert resp.status_code == 400


# ---------------- UPDATE ----------------
def test_update_item(client):
    resp = client.patch("/inventory/1", json={"price": 4.25, "product": {"brands": "Silk Co"}})
    assert resp.status_code == 200
    item = resp.get_json()
    assert item["price"] == 4.25
    assert item["product"]["brands"] == "Silk Co"
    assert item["product"]["product_name"] == "Organic Almond Milk"  # untouched


def test_update_missing_item(client):
    assert client.patch("/inventory/999", json={"stock": 1}).status_code == 404


def test_update_invalid(client):
    resp = client.patch("/inventory/1", json={"stock": -5})
    assert resp.status_code == 400
    assert data.inventory[0]["stock"] == 40


def test_update_empty_name(client):
    assert client.patch("/inventory/1", json={"product": {"product_name": ""}}).status_code == 400


# ---------------- DELETE ----------------
def test_delete_item(client):
    resp = client.delete("/inventory/2")
    assert resp.status_code == 200
    assert all(i["id"] != 2 for i in data.inventory)
    assert client.get("/inventory/2").status_code == 404


def test_delete_missing_item(client):
    assert client.delete("/inventory/999").status_code == 404


def test_ids_not_reused_after_delete(client):
    client.delete("/inventory/1")
    item = client.post("/inventory", json={"product": {"product_name": "New"}}).get_json()
    assert item["id"] == 4


# ---------------- EXTERNAL API ROUTES ----------------
@patch("app.fetch_product_by_barcode", return_value=OFF_RESULT)
def test_lookup_barcode(mock_fetch, client):
    resp = client.get("/products/barcode/737628064502")
    assert resp.status_code == 200
    assert resp.get_json()["product"]["brands"] == "Simply Asia"
    mock_fetch.assert_called_once_with("737628064502")


@patch("app.fetch_product_by_barcode", return_value=None)
def test_lookup_barcode_not_found(_, client):
    assert client.get("/products/barcode/000").status_code == 404


@patch("app.fetch_product_by_barcode", side_effect=ExternalAPIError("down"))
def test_lookup_barcode_api_down(_, client):
    resp = client.get("/products/barcode/000")
    assert resp.status_code == 502
    assert resp.get_json()["error"] == "down"


@patch("app.search_products_by_name", return_value=[OFF_RESULT])
def test_search_products(mock_search, client):
    resp = client.get("/products/search?name=noodle")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1
    mock_search.assert_called_once_with("noodle")


def test_search_requires_name(client):
    assert client.get("/products/search").status_code == 400


@patch("app.fetch_product_by_barcode", return_value=OFF_RESULT)
def test_import_product(_, client):
    resp = client.post("/inventory/import/737628064502", json={"price": 2.99, "stock": 15})
    assert resp.status_code == 201
    item = resp.get_json()
    assert item["id"] == 4 and item["price"] == 2.99 and item["stock"] == 15
    assert item["product"]["product_name"] == "Thai Peanut Noodle Kit"
    assert len(data.inventory) == 4


@patch("app.fetch_product_by_barcode", return_value=None)
def test_import_product_not_found(_, client):
    assert client.post("/inventory/import/000").status_code == 404
    assert len(data.inventory) == 3


def test_import_invalid_price(client):
    assert client.post("/inventory/import/123", json={"price": "free"}).status_code == 400


@patch("app.fetch_product_by_barcode", return_value=OFF_RESULT)
def test_enrich_item(_, client):
    item = client.post("/inventory", json={
        "product": {"product_name": "Noodles"}, "barcode": "737628064502"}).get_json()
    resp = client.post(f"/inventory/{item['id']}/enrich")
    assert resp.status_code == 200
    enriched = resp.get_json()["product"]
    assert enriched["product_name"] == "Noodles"        # existing value kept
    assert enriched["brands"] == "Simply Asia"          # empty value filled


def test_enrich_item_without_barcode(client):
    item = client.post("/inventory", json={"product": {"product_name": "X"}}).get_json()
    assert client.post(f"/inventory/{item['id']}/enrich").status_code == 400


def test_unknown_route(client):
    assert client.get("/nope").status_code == 404


def test_method_not_allowed(client):
    assert client.put("/inventory").status_code == 405
