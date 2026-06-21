"""Categorization: finer purposes, part-number fallback, and auto-created tabs."""

import db
import bom


# --- offline keyword rules: finer purposes win over broad families ---------- #

def test_regulator_description_is_voltage_regulator():
    assert bom.guess_category("AMS1117-3.3 LDO linear regulator") == "voltage regulator"


def test_mosfet_description_is_mosfet_not_transistor():
    assert bom.guess_category("MOSFET P-Channel 30V 4.2A") == "mosfet"


def test_voltage_reference_keyword():
    assert bom.guess_category("2.5V shunt voltage reference") == "voltage reference"


def test_optocoupler_keyword():
    assert bom.guess_category("Optocoupler, phototransistor output") == "optocoupler"


def test_existing_broad_families_still_work():
    assert bom.guess_category("100nF MLCC capacitor") == "capacitor"
    assert bom.guess_category("10kΩ resistor 0805") == "resistor"


# --- part-number fallback: bare part numbers with no description ------------ #

def test_ao3407_bare_part_number_is_mosfet():
    # The motivating case: a P-channel MOSFET given only by part number.
    assert bom.guess_category("", "", "AO3407") == "mosfet"


def test_lm1117_part_number_is_regulator():
    assert bom.guess_category("", "", "LM1117-3.3") == "voltage regulator"


def test_pc817_part_number_is_optocoupler():
    assert bom.guess_category("", "", "PC817") == "optocoupler"


def test_unknown_part_number_still_uncategorized():
    assert bom.guess_category("", "", "ZZQ-9999-X") == "uncategorized"


def test_description_beats_part_number_prefix():
    # A real connector that happens to start like a transistor prefix: the
    # descriptive word should win over the part-number guess.
    assert bom.guess_category("USB Type-C connector", "", "2N-USB") == "connector"


# --- auto-created tabs: a new purpose shows up on its own tab ---------------- #

def test_new_category_gets_its_own_tab(client):
    db.add_component({"category": "voltage regulator", "value": "LM1117",
                      "quantity": 4})
    r = client.get("/")
    assert r.status_code == 200
    # The auto-created tab is title-cased in the UI.
    assert b"Voltage Regulator" in r.data


def test_uncategorized_filter(client):
    db.add_component({"category": "uncategorized", "value": "mystery", "quantity": 1})
    db.add_component({"category": "resistor", "value": "1k", "quantity": 1})
    only = db.list_components(category="uncategorized")
    assert len(only) == 1
    assert only[0]["value"] == "mystery"
