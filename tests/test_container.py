"""Per-component container label: set/edit from the scan page, list, search."""

import db


def test_container_column_exists(client):
    cid = db.add_component({"category": "resistor", "value": "10kΩ", "quantity": 1,
                            "container": "Drawer B3 Bin 12"})
    assert db.get_component(cid)["container"] == "Drawer B3 Bin 12"


def test_set_container_route_alphanumeric(client):
    cid = db.add_component({"category": "resistor", "value": "4.7kΩ", "quantity": 1})
    resp = client.post(f"/c/{cid}/container", data={"container": "A12-Bin7"})
    assert resp.status_code == 200
    assert b"A12-Bin7" in resp.data
    assert db.get_component(cid)["container"] == "A12-Bin7"


def test_update_container_overwrites(client):
    cid = db.add_component({"category": "ic", "value": "555", "quantity": 1,
                            "container": "Old spot"})
    client.post(f"/c/{cid}/container", data={"container": "Drawer C1"})
    assert db.get_component(cid)["container"] == "Drawer C1"


def test_clear_container(client):
    cid = db.add_component({"category": "diode", "value": "1N4148", "quantity": 1,
                            "container": "Bin 9"})
    client.post(f"/c/{cid}/container", data={"container": "  "})
    assert db.get_component(cid)["container"] in (None, "")


def test_container_shows_on_detail_and_list(client):
    cid = db.add_component({"category": "resistor", "value": "1kΩ", "quantity": 1,
                            "part_number": "RES1K", "container": "Drawer B3"})
    assert b"Drawer B3" in client.get(f"/c/{cid}").data
    assert b"Drawer B3" in client.get("/").data


def test_search_by_container(client):
    db.add_component({"category": "resistor", "value": "10kΩ", "quantity": 1,
                      "part_number": "RA", "container": "Drawer B3"})
    db.add_component({"category": "resistor", "value": "22kΩ", "quantity": 1,
                      "part_number": "RB", "container": "Drawer Z9"})
    resp = client.get("/search?q=B3")
    assert b"RA" in resp.data and b"RB" not in resp.data


def test_container_in_csv_export(client):
    db.add_component({"category": "resistor", "value": "3k3", "quantity": 1,
                      "container": "Bin 42"})
    resp = client.get("/export.csv")
    assert b"container" in resp.data and b"Bin 42" in resp.data


def test_set_container_missing_404(client):
    assert client.post("/c/999999/container", data={"container": "x"}).status_code == 404
