"""CRUD, search, quantity stepper, and low-stock behaviour."""

import db


def test_add_and_list(client):
    cid = db.add_component({"category": "resistor", "value": "1kΩ", "quantity": 5,
                            "part_number": "RC0805FR-071KL"})
    assert cid
    rows = db.list_components()
    assert len(rows) == 1
    assert rows[0]["value"] == "1kΩ"


def test_index_page_loads(client):
    db.add_component({"category": "capacitor", "value": "100nF", "quantity": 10})
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"100nF" in resp.data


def test_quantity_stepper(client):
    cid = db.add_component({"category": "ic", "value": "555", "quantity": 3})
    resp = client.post(f"/component/{cid}/qty", data={"delta": "2"})
    assert resp.status_code == 200
    assert db.get_component(cid)["quantity"] == 5
    # Cannot go below zero.
    db.adjust_quantity(cid, -100)
    assert db.get_component(cid)["quantity"] == 0


def test_search_filters(client):
    db.add_component({"category": "resistor", "value": "10kΩ", "quantity": 1,
                      "part_number": "RES10K"})
    db.add_component({"category": "capacitor", "value": "1µF", "quantity": 1,
                      "part_number": "CAP1U"})
    resp = client.get("/search?q=RES10K")
    assert b"RES10K" in resp.data and b"CAP1U" not in resp.data


def test_low_stock_view(client):
    db.add_component({"category": "diode", "value": "1N4148", "quantity": 2,
                      "min_quantity": 5})
    db.add_component({"category": "diode", "value": "1N4007", "quantity": 50,
                      "min_quantity": 5})
    resp = client.get("/low-stock")
    assert b"1N4148" in resp.data and b"1N4007" not in resp.data


def test_delete(client):
    cid = db.add_component({"category": "misc", "quantity": 1})
    client.post(f"/component/{cid}/delete", headers={"HX-Request": "true"})
    assert db.get_component(cid) is None


def test_export_csv(client):
    db.add_component({"category": "resistor", "value": "4k7", "quantity": 9})
    resp = client.get("/export.csv")
    assert resp.status_code == 200
    assert b"4k7" in resp.data
