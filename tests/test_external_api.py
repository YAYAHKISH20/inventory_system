"""Tests for the OpenFoodFacts client (HTTP calls are mocked)."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from external_api import (
    ExternalAPIError,
    fetch_product_by_barcode,
    search_products_by_name,
)

RAW_PRODUCT = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Ferrero",
    "ingredients_text": "Sugar, palm oil",
    "nutriscore_grade": "e",
    "unused_field": "ignored",
}


def fake_response(status_code=200, payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    return resp


@patch("external_api.requests.get")
def test_fetch_by_barcode_success(mock_get):
    mock_get.return_value = fake_response(200, {"status": 1, "product": RAW_PRODUCT})
    result = fetch_product_by_barcode("3017620422003")
    assert result["barcode"] == "3017620422003"
    assert result["product"]["product_name"] == "Nutella"
    assert result["product"]["categories"] == ""
    assert "unused_field" not in result["product"]
    assert "3017620422003" in mock_get.call_args[0][0]


@patch("external_api.requests.get")
def test_fetch_by_barcode_status_zero(mock_get):
    mock_get.return_value = fake_response(200, {"status": 0, "status_verbose": "product not found"})
    assert fetch_product_by_barcode("000") is None


@patch("external_api.requests.get")
def test_fetch_by_barcode_404(mock_get):
    mock_get.return_value = fake_response(404)
    assert fetch_product_by_barcode("000") is None


@patch("external_api.requests.get")
def test_fetch_by_barcode_server_error(mock_get):
    mock_get.return_value = fake_response(500)
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("000")


@patch("external_api.requests.get", side_effect=requests.ConnectionError("no network"))
def test_fetch_by_barcode_network_error(_):
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("000")


@patch("external_api.requests.get")
def test_fetch_missing_name_defaults_to_unknown(mock_get):
    mock_get.return_value = fake_response(200, {"status": 1, "product": {"code": "1"}})
    assert fetch_product_by_barcode("1")["product"]["product_name"] == "Unknown"


@patch("external_api.requests.get")
def test_search_by_name(mock_get):
    mock_get.return_value = fake_response(200, {"products": [RAW_PRODUCT, RAW_PRODUCT]})
    results = search_products_by_name("nutella", page_size=2)
    assert len(results) == 2
    assert results[0]["product"]["brands"] == "Ferrero"
    params = mock_get.call_args.kwargs["params"]
    assert params["search_terms"] == "nutella" and params["page_size"] == 2


@patch("external_api.requests.get")
def test_search_no_results(mock_get):
    mock_get.return_value = fake_response(200, {"products": []})
    assert search_products_by_name("zzzz") == []


@patch("external_api.requests.get", side_effect=requests.Timeout())
def test_search_timeout(_):
    with pytest.raises(ExternalAPIError):
        search_products_by_name("milk")
