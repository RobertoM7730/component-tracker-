"""Category naming: one spelling per family, everywhere."""

import app as app_module
import categories
import db


# --- normalization ---------------------------------------------------------- #

def test_case_and_plural_fold_to_one_name():
    for spelling in ["ic", "IC", "Ic", "ICs", "ics", "integrated circuit", "chip"]:
        assert categories.normalize(spelling) == "ic"


def test_punctuation_and_spacing_fold():
    for spelling in ["op-amp", "Op Amp", "OPAMP", "op   amp", "operational amplifier"]:
        assert categories.normalize(spelling) == "op-amp"


def test_synonyms_merge_into_their_family():
    assert categories.normalize("LEDs") == "diode"
    assert categories.normalize("buttons") == "switch"
    assert categories.normalize("LDO") == "voltage regulator"
    assert categories.normalize("MCU") == "microcontroller"
    assert categories.normalize("trimpot") == "potentiometer"


def test_blank_and_vague_names_are_uncategorized():
    for spelling in ["", "   ", None, "Other", "misc", "unknown", "Uncategorized"]:
        assert categories.normalize(spelling) == "uncategorized"


def test_unknown_category_is_kept_but_tidied():
    assert categories.normalize("  Power   Stuff ") == "power stuff"


def test_labels_keep_acronym_casing():
    assert categories.label("ic") == "ICs"
    assert categories.label("mosfet") == "MOSFETs"
    assert categories.label("adc") == "ADCs"
    assert categories.label("op-amp") == "Op-Amps"
    assert categories.label("power stuff") == "Power Stuff"


def test_every_canonical_name_is_its_own_normal_form():
    # Guards against an alias in one family shadowing another family's name.
    for name in categories.ALL:
        assert categories.normalize(name) == name


# --- writes are normalized -------------------------------------------------- #

def test_stored_category_is_canonical(client):
    cid = db.add_component({"category": "ICs", "value": "NE555", "quantity": 1})
    assert db.get_component(cid)["category"] == "ic"
    db.update_component(cid, {"category": "Integrated Circuit"})
    assert db.get_component(cid)["category"] == "ic"


def test_variant_spellings_share_one_tab(client):
    db.add_component({"category": "IC", "value": "NE555", "quantity": 1})
    db.add_component({"category": "ics", "value": "SN74HC595", "quantity": 2})
    db.add_component({"category": "Ic", "value": "MAX232", "quantity": 3})
    tabs = {t["value"]: t for t in app_module.build_tabs("")}
    assert tabs["ic"]["count"] == 3
    assert tabs["ic"]["label"] == "ICs"
    # No second tab spelled another way.
    assert [t["label"] for t in tabs.values()].count("ICs") == 1


def test_startup_merges_legacy_spellings(client):
    # Simulate rows written before normalization existed.
    conn = db.get_connection()
    with conn:
        conn.execute(
            "INSERT INTO components (category, value, quantity, created_at, "
            "updated_at) VALUES ('Ic', 'legacy', 1, '2026-01-01', '2026-01-01')"
        )
    conn.close()
    db.init_db()
    assert [c["category"] for c in db.list_components(category="ic")] == ["ic"]


def test_filter_accepts_any_spelling(client):
    db.add_component({"category": "ic", "value": "NE555", "quantity": 1})
    assert b"NE555" in client.get("/?category=ICs").data
    assert b"NE555" in client.get("/?category=Integrated+Circuit").data
