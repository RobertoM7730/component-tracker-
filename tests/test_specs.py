"""Spec extraction, spec-aware search, mounting detection, and category tabs."""

import db
import specs


def test_extract_resistor():
    s = specs.extract_specs("resistor", "10kΩ 1%", "", "0805")
    by = {x["name"]: x for x in s}
    assert by["resistance"]["value_text"] == "10kΩ"
    assert by["resistance"]["value_num"] == 10000.0
    assert by["tolerance"]["value_text"] == "±1%"


def test_extract_capacitor_and_inductor():
    c = {x["name"]: x for x in specs.extract_specs("capacitor", "10µF 16V", "", "0805")}
    assert c["capacitance"]["unit"] == "F"
    assert c["voltage"]["value_num"] == 16.0
    i = {x["name"]: x for x in specs.extract_specs("inductor", "10µH 2A", "", "")}
    assert i["inductance"]["value_text"].endswith("H")
    assert i["current"]["value_num"] == 2.0


def test_rkm_shorthand():
    s = {x["name"]: x for x in specs.extract_specs("resistor", "4k7", "", "")}
    assert s["resistance"]["value_num"] == 4700.0


def test_fraction_wattage():
    s = {x["name"]: x for x in specs.extract_specs("resistor", "100R 1/4W", "", "")}
    assert s["wattage"]["value_num"] == 0.25


def test_mount_detection():
    assert specs.guess_mount("0805") == "SMD"
    assert specs.guess_mount("DIP-8") == "THT"
    assert specs.guess_mount("TO-220") == "THT"
    assert specs.guess_mount("") == ""


def test_search_by_spec(client):
    cid = db.add_component({"category": "resistor", "value": "10kΩ", "quantity": 5})
    db.replace_specs(cid, specs.extract_specs("resistor", "10kΩ 1%", "", "0805"))
    # The bare value field doesn't contain "10000", but the spec search should
    # still find it by its human spec text.
    hits = db.list_components(search="10k")
    assert any(c["id"] == cid for c in hits)
    # Attached specs come back with the row.
    assert hits[0]["specs"]


def test_search_by_mount(client):
    cid = db.add_component({"category": "ic", "value": "MCU", "quantity": 1,
                            "mount": "THT", "package": "DIP-28"})
    assert any(c["id"] == cid for c in db.list_components(search="THT"))


def test_other_category_filter(client):
    db.add_component({"category": "resistor", "quantity": 1})
    db.add_component({"category": "fuse", "quantity": 1})          # not canonical
    db.add_component({"category": "uncategorized", "quantity": 1})  # not canonical
    other = db.list_components(category="other")
    cats = sorted(c["category"] for c in other)
    assert cats == ["fuse", "uncategorized"]


def test_order_import_stores_specs(client, sample_dir):
    import io, json, os, bom
    with open(os.path.join(sample_dir, "lcsc_order.csv"), "rb") as f:
        client.post("/import/order",
                    data={"bom": (io.BytesIO(f.read()), "lcsc_order.csv")},
                    content_type="multipart/form-data")
    res = bom.parse_bom(os.path.join(sample_dir, "lcsc_order.csv"))
    form = {"payload": json.dumps(res["rows"]), "include": ["0"]}
    form["qty_0"] = "100"
    form["category_0"] = res["rows"][0]["category"]
    client.post("/import/order/commit", data=form, follow_redirects=True)
    comp = db.find_component_by_part("RC0805FR-0710KL")
    saved = db.get_specs(comp["id"])
    assert any(s["name"] == "resistance" for s in saved)
