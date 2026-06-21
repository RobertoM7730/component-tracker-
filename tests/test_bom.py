"""BOM parsing + the two import flows (order adds stock, PCB consumes it)."""

import io
import os

import db
import bom


def _post_file(client, url, path, extra=None):
    with open(path, "rb") as f:
        data = {"bom": (io.BytesIO(f.read()), os.path.basename(path))}
    if extra:
        data.update(extra)
    return client.post(url, data=data, content_type="multipart/form-data")


def test_parse_lcsc(sample_dir):
    res = bom.parse_bom(os.path.join(sample_dir, "lcsc_order.csv"))
    assert res["supplier"] == "LCSC"
    assert len(res["rows"]) == 3
    first = res["rows"][0]
    assert first["part_number"] == "RC0805FR-0710KL"
    assert first["supplier_pn"] == "C25744"
    assert first["quantity"] == 100
    assert first["category"] == "resistor"


def test_parse_digikey(sample_dir):
    res = bom.parse_bom(os.path.join(sample_dir, "digikey_order.csv"))
    assert res["supplier"] == "DigiKey"
    assert len(res["rows"]) == 3
    assert res["rows"][1]["part_number"] == "SN74HC595N"
    assert res["rows"][1]["quantity"] == 25


def test_parse_xlsx(tmp_path, sample_dir):
    # Build an xlsx from the LCSC sample and confirm it parses the same.
    from openpyxl import Workbook
    import csv
    wb = Workbook()
    ws = wb.active
    with open(os.path.join(sample_dir, "lcsc_order.csv"), newline="") as f:
        for row in csv.reader(f):
            ws.append(row)
    xlsx_path = tmp_path / "lcsc.xlsx"
    wb.save(xlsx_path)
    res = bom.parse_bom(str(xlsx_path))
    assert res["supplier"] == "LCSC"
    assert len(res["rows"]) == 3


def test_order_import_flow(client, sample_dir):
    # Preview, then commit — should add 3 new components.
    r = _post_file(client, "/import/order", os.path.join(sample_dir, "lcsc_order.csv"))
    assert r.status_code == 200
    assert b"Order import preview" in r.data

    # Re-parse to get the payload the form would submit.
    res = bom.parse_bom(os.path.join(sample_dir, "lcsc_order.csv"))
    import json
    payload = json.dumps(res["rows"])
    form = {"payload": payload, "include": ["0", "1", "2"]}
    for i, row in enumerate(res["rows"]):
        form[f"qty_{i}"] = str(row["quantity"])
        form[f"category_{i}"] = row["category"]
    r2 = client.post("/import/order/commit", data=form, follow_redirects=True)
    assert r2.status_code == 200
    comps = db.list_components()
    assert len(comps) == 3
    total = sum(c["quantity"] for c in comps)
    assert total == 160  # 100 + 50 + 10


def test_order_restock_merges(client, sample_dir):
    # Pre-seed one matching part, then import should restock not duplicate.
    db.add_component({"category": "resistor", "part_number": "RC0805FR-0710KL",
                      "quantity": 5})
    res = bom.parse_bom(os.path.join(sample_dir, "lcsc_order.csv"))
    import json
    form = {"payload": json.dumps(res["rows"]), "include": ["0"]}
    form["qty_0"] = "100"
    form["category_0"] = "resistor"
    client.post("/import/order/commit", data=form, follow_redirects=True)
    match = db.find_component_by_part("RC0805FR-0710KL")
    assert match["quantity"] == 105  # 5 + 100, merged not duplicated
    assert len(db.list_components()) == 1


def test_pcb_consume_flow(client, sample_dir):
    # Stock up via the order BOM first.
    res = bom.parse_bom(os.path.join(sample_dir, "lcsc_order.csv"))
    import json
    form = {"payload": json.dumps(res["rows"]), "include": ["0", "1", "2"]}
    for i, row in enumerate(res["rows"]):
        form[f"qty_{i}"] = str(row["quantity"])
        form[f"category_{i}"] = row["category"]
    client.post("/import/order/commit", data=form, follow_redirects=True)

    # Now build 2 boards from the PCB BOM.
    pcb = bom.parse_bom(os.path.join(sample_dir, "pcb_bom.csv"))
    items = []
    for row in pcb["rows"]:
        existing = db.find_component_by_part(row["part_number"], row["supplier_pn"])
        items.append({**row, "component_id": existing["id"] if existing else None,
                      "qty_per_board": row["quantity"]})
    form2 = {"payload": json.dumps(items), "name": "Test board", "board_qty": "2"}
    r = client.post("/import/pcb/commit", data=form2, follow_redirects=True)
    assert r.status_code == 200

    # 10kΩ resistor: had 100, used 3*2 = 6 -> 94 left.
    res_part = db.find_component_by_part("RC0805FR-0710KL")
    assert res_part["quantity"] == 94
    # Build recorded.
    assert len(db.list_builds()) == 1


def test_pcb_preview_flags_shortage(client, sample_dir):
    db.add_component({"category": "resistor", "part_number": "RC0805FR-0710KL",
                      "quantity": 2})
    r = _post_file(client, "/import/pcb",
                   os.path.join(sample_dir, "pcb_bom.csv"),
                   extra={"name": "Short board", "board_qty": "5"})
    assert r.status_code == 200
    assert b"short" in r.data.lower()
