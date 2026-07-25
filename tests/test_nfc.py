"""Component detail page + NFC/QR helper + detail-page quantity stepper."""

import db


def test_detail_page_loads(client):
    cid = db.add_component({"category": "resistor", "value": "10kΩ", "quantity": 7,
                            "part_number": "RC0805FR-0710KL", "location": "Drawer B3",
                            "manufacturer": "Yageo"})
    resp = client.get(f"/c/{cid}")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    # Key facts the user scans a tag to see:
    assert "RC0805FR-0710KL" in body
    assert "Drawer B3" in body
    assert "Yageo" in body


def test_detail_page_shows_nfc_url_and_qr(client):
    cid = db.add_component({"category": "ic", "value": "ATmega328P", "quantity": 3})
    body = client.get(f"/c/{cid}").data.decode("utf-8")
    # The exact URL to write to the tag is present...
    assert f"/c/{cid}" in body
    # ...and a QR code renders (segno installed).
    assert "<svg" in body


def test_detail_missing_component_404(client):
    assert client.get("/c/999999").status_code == 404


def test_detail_quantity_stepper(client):
    cid = db.add_component({"category": "diode", "value": "1N4148", "quantity": 4})
    resp = client.post(f"/c/{cid}/qty", data={"delta": "3"})
    assert resp.status_code == 200
    assert db.get_component(cid)["quantity"] == 7
    # Clamps at zero, never negative.
    client.post(f"/c/{cid}/qty", data={"delta": "-100"})
    assert db.get_component(cid)["quantity"] == 0


def test_inventory_row_links_to_detail(client):
    cid = db.add_component({"category": "resistor", "value": "1kΩ", "quantity": 1,
                            "part_number": "RES1K"})
    body = client.get("/").data.decode("utf-8")
    assert f"/c/{cid}" in body
