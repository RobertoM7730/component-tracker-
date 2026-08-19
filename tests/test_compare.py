"""BOM comparison feature — matching, KiCad footprint normalization, shopping list."""

import io
import json
import os

import pytest

import db
import bom
import specs


def _post_file(client, url, path, extra=None):
    with open(path, "rb") as f:
        data = {"bom": (io.BytesIO(f.read()), os.path.basename(path))}
    if extra:
        data.update(extra)
    return client.post(url, data=data, content_type="multipart/form-data")


# ---- KiCad footprint normalization ----------------------------------------

def test_normalize_smd_passive():
    assert bom.normalize_kicad_footprint("Resistor_SMD:R_0603_1608Metric") == "0603"
    assert bom.normalize_kicad_footprint("Capacitor_SMD:C_0402_1005Metric") == "0402"
    assert bom.normalize_kicad_footprint("Inductor_SMD:L_1210_3225Metric") == "1210"


def test_normalize_ic_packages():
    assert bom.normalize_kicad_footprint("Package_QFP:LQFP-48_7x7mm_P0.5mm") == "LQFP-48"
    assert bom.normalize_kicad_footprint("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm") == "SOIC-8"
    assert bom.normalize_kicad_footprint("Package_TO_SOT_SMD:SOT-23") == "SOT-23"
    assert bom.normalize_kicad_footprint("Package_DFN_QFN:QFN-16-1EP_3x3mm") == "QFN-16"


def test_normalize_through_hole():
    assert bom.normalize_kicad_footprint("Package_TO_SOT_THT:TO-220-3_Vertical") == "TO-220"
    assert bom.normalize_kicad_footprint("Package_DIP:DIP-8_W7.62mm") == "DIP-8"


def test_normalize_empty():
    assert bom.normalize_kicad_footprint("") == ""
    assert bom.normalize_kicad_footprint(None) == ""


# ---- KiCad value parsing -------------------------------------------------

def test_parse_kicad_resistor_values():
    assert specs.parse_value_for_category("10k", "resistor") == ("resistance", 10000.0)
    assert specs.parse_value_for_category("4k7", "resistor") == ("resistance", 4700.0)
    assert specs.parse_value_for_category("100", "resistor") == ("resistance", 100.0)
    assert specs.parse_value_for_category("100R", "resistor") == ("resistance", 100.0)
    assert specs.parse_value_for_category("1M", "resistor") == ("resistance", 1e6)


def test_parse_kicad_capacitor_values():
    name, val = specs.parse_value_for_category("100n", "capacitor")
    assert name == "capacitance"
    assert val == pytest.approx(1e-7)
    name, val = specs.parse_value_for_category("10u", "capacitor")
    assert name == "capacitance"
    assert val == pytest.approx(1e-5)
    name, val = specs.parse_value_for_category("47p", "capacitor")
    assert name == "capacitance"
    assert val == pytest.approx(4.7e-11)


def test_parse_value_unknown_category():
    assert specs.parse_value_for_category("10k", "ic") is None
    assert specs.parse_value_for_category("", "resistor") is None


# ---- Parametric matching (db.find_compatible) -----------------------------

def test_find_compatible_exact_spec(client):
    cid = db.add_component({"category": "resistor", "part_number": "RES10K",
                            "package": "0805", "quantity": 50})
    db.replace_specs(cid, [{"name": "resistance", "value_text": "10kΩ",
                            "value_num": 10000.0, "unit": "Ω"}])
    matches = db.find_compatible("resistor", "resistance", 10000.0, "0805")
    assert len(matches) >= 1
    assert matches[0]["id"] == cid


def test_find_compatible_no_package_fallback(client):
    cid = db.add_component({"category": "resistor", "part_number": "RES10K_0603",
                            "package": "0603", "quantity": 20})
    db.replace_specs(cid, [{"name": "resistance", "value_text": "10kΩ",
                            "value_num": 10000.0, "unit": "Ω"}])
    matches = db.find_compatible("resistor", "resistance", 10000.0, "0805")
    assert len(matches) >= 1
    assert matches[0]["id"] == cid


def test_find_compatible_no_match(client):
    matches = db.find_compatible("resistor", "resistance", 99999.0)
    assert matches == []


# ---- Compare flow via HTTP ------------------------------------------------

def test_compare_preview_page(client, sample_dir):
    r = _post_file(client, "/compare/preview",
                   os.path.join(sample_dir, "kicad_bom.csv"),
                   extra={"name": "Test board", "board_qty": "1"})
    assert r.status_code == 200
    assert b"BOM comparison" in r.data
    assert b"Need to buy" in r.data


def test_compare_finds_exact_match(client, sample_dir):
    db.add_component({"category": "microcontroller",
                      "part_number": "STM32F103C8T6", "quantity": 5})
    r = _post_file(client, "/compare/preview",
                   os.path.join(sample_dir, "kicad_bom.csv"),
                   extra={"name": "MCU board", "board_qty": "1"})
    assert r.status_code == 200
    assert b"matched" in r.data.lower()


def test_compare_finds_compatible_match(client, sample_dir):
    cid = db.add_component({"category": "resistor", "part_number": "GENERIC10K",
                            "package": "0805", "quantity": 100})
    db.replace_specs(cid, [{"name": "resistance", "value_text": "10kΩ",
                            "value_num": 10000.0, "unit": "Ω"}])
    r = _post_file(client, "/compare/preview",
                   os.path.join(sample_dir, "kicad_bom.csv"),
                   extra={"name": "Res board", "board_qty": "1"})
    assert r.status_code == 200
    assert b"compatible" in r.data.lower() or b"matched" in r.data.lower()


def test_compare_board_qty_multiplier(client, sample_dir):
    cid = db.add_component({"category": "resistor", "part_number": "GENERIC10K",
                            "package": "0805", "quantity": 5})
    db.replace_specs(cid, [{"name": "resistance", "value_text": "10kΩ",
                            "value_num": 10000.0, "unit": "Ω"}])
    r = _post_file(client, "/compare/preview",
                   os.path.join(sample_dir, "kicad_bom.csv"),
                   extra={"name": "Multi", "board_qty": "3"})
    assert r.status_code == 200
    # R1-R3 need 3 per board * 3 boards = 9, stock is 5 → short
    assert b"short" in r.data.lower()


def test_shopping_list_csv(client):
    payload = json.dumps([
        {"part_number": "STM32F103C8T6", "value": "STM32F103C8T6",
         "package": "LQFP-48", "category": "microcontroller",
         "designator": "U1", "description": "", "quantity": 1,
         "need": 1, "short": 1, "match_type": "none"},
        {"part_number": "GENERIC10K", "value": "10k",
         "package": "0805", "category": "resistor",
         "designator": "R1, R2", "description": "", "quantity": 2,
         "need": 2, "short": 0, "match_type": "exact"},
    ])
    r = client.post("/compare/shopping-list.csv",
                    data={"payload": payload, "board_qty": "1", "name": "test"})
    assert r.status_code == 200
    assert r.content_type == "text/csv; charset=utf-8"
    text = r.data.decode()
    assert "STM32F103C8T6" in text
    assert "GENERIC10K" not in text  # matched, not short → excluded
