"""Tests for the CLI: HTTP helpers, formatting, and interactive menu flows."""
from unittest.mock import MagicMock, patch

import requests

import cli

ITEM = {
    "id": 1, "barcode": "123", "price": 3.99, "stock": 40, "status": 1,
    "product": {"product_name": "Organic Almond Milk", "brands": "Silk",
                "ingredients_text": "Water, almonds"},
}


def fake_response(status_code, payload):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


# ---------------- HTTP helpers ----------------
@patch("cli.requests.request")
def test_list_items_calls_api(mock_req):
    mock_req.return_value = fake_response(200, [ITEM])
    status, body = cli.list_items()
    assert status == 200 and body == [ITEM]
    method, url = mock_req.call_args[0]
    assert method == "GET" and url.endswith("/inventory")


@patch("cli.requests.request")
def test_add_item_sends_json(mock_req):
    mock_req.return_value = fake_response(201, ITEM)
    payload = {"product": {"product_name": "X"}}
    cli.add_item(payload)
    assert mock_req.call_args[0][0] == "POST"
    assert mock_req.call_args.kwargs["json"] == payload


@patch("cli.requests.request")
def test_update_and_delete_use_correct_methods(mock_req):
    mock_req.return_value = fake_response(200, ITEM)
    cli.update_item(1, {"stock": 5})
    assert mock_req.call_args[0][:2] == ("PATCH", f"{cli.API_URL}/inventory/1")
    cli.delete_item(1)
    assert mock_req.call_args[0][:2] == ("DELETE", f"{cli.API_URL}/inventory/1")


@patch("cli.requests.request")
def test_import_product(mock_req):
    mock_req.return_value = fake_response(201, ITEM)
    cli.import_product("123", 2.5, 7)
    assert mock_req.call_args[0][1].endswith("/inventory/import/123")
    assert mock_req.call_args.kwargs["json"] == {"price": 2.5, "stock": 7}


@patch("cli.requests.request", side_effect=requests.ConnectionError())
def test_api_unreachable(_):
    status, body = cli.list_items()
    assert status is None and "Cannot connect" in body["error"]


# ---------------- Formatting ----------------
def test_format_item():
    text = cli.format_item(ITEM)
    assert "[1] Organic Almond Milk (Silk)" in text
    assert "$3.99" in text and "Stock: 40" in text


def test_show_result_error(capsys):
    assert cli.show_result(404, {"error": "Item not found"}) is False
    assert "Error: Item not found" in capsys.readouterr().out


# ---------------- Interactive flows ----------------
@patch("cli.add_item", return_value=(201, ITEM))
@patch("builtins.input", side_effect=["Oat Milk", "Oatly", "Oats, water", "999", "4.5", "10"])
def test_action_add(_, mock_add, capsys):
    cli.action_add()
    payload = mock_add.call_args[0][0]
    assert payload["product"]["product_name"] == "Oat Milk"
    assert payload["price"] == 4.5 and payload["stock"] == 10
    assert "Organic Almond Milk" in capsys.readouterr().out


@patch("cli.add_item", return_value=(201, ITEM))
@patch("builtins.input", side_effect=["", "Milk", "", "", "", "abc", "2", ""])
def test_action_add_reprompts_on_bad_input(_, mock_add, capsys):
    cli.action_add()
    payload = mock_add.call_args[0][0]
    assert payload["product"]["product_name"] == "Milk"
    assert payload["price"] == 2.0 and payload["stock"] == 0
    out = capsys.readouterr().out
    assert "required" in out and "non-negative" in out


@patch("cli.update_item", return_value=(200, ITEM))
@patch("cli.get_item", return_value=(200, ITEM))
@patch("builtins.input", side_effect=["1", "", "", "", "", "5.25", ""])
def test_action_update_only_sends_changed_fields(_, __, mock_update):
    cli.action_update()
    mock_update.assert_called_once_with(1, {"price": 5.25})


@patch("cli.update_item")
@patch("cli.get_item", return_value=(404, {"error": "Item not found"}))
@patch("builtins.input", side_effect=["99"])
def test_action_update_missing_item(_, __, mock_update):
    cli.action_update()
    mock_update.assert_not_called()


@patch("cli.delete_item", return_value=(200, {"message": "Item 1 deleted"}))
@patch("builtins.input", side_effect=["1", "y"])
def test_action_delete_confirmed(_, mock_delete, capsys):
    cli.action_delete()
    mock_delete.assert_called_once_with(1)
    assert "Item 1 deleted" in capsys.readouterr().out


@patch("cli.delete_item")
@patch("builtins.input", side_effect=["1", "n"])
def test_action_delete_cancelled(_, mock_delete):
    cli.action_delete()
    mock_delete.assert_not_called()


@patch("cli.search_products", return_value=(200, [{"barcode": "1", "product": {"product_name": "Nutella"}}]))
@patch("builtins.input", side_effect=["nutella"])
def test_action_search(_, __, capsys):
    cli.action_search()
    assert "Nutella" in capsys.readouterr().out


@patch("builtins.input", side_effect=["42", "0"])
def test_main_menu_invalid_then_exit(_, capsys):
    cli.main()
    out = capsys.readouterr().out
    assert "Invalid choice" in out and "Goodbye" in out


@patch("cli.list_items", return_value=(200, [ITEM]))
@patch("builtins.input", side_effect=["1", "", "0"])
def test_main_menu_view_all(_, mock_list, capsys):
    cli.main()
    mock_list.assert_called_once_with("")
    assert "Organic Almond Milk" in capsys.readouterr().out
