"""Query parsing and spec range filtering (the extended characteristic search)."""

import db
import specs
import query


def test_parse_plain_text():
    text, conds = query.parse_query("10k 0805")
    assert text == "10k 0805"
    assert conds == []


def test_parse_operators_to_base_units():
    text, conds = query.parse_query("resistance>=1k wattage>=0.25")
    assert text == ""
    assert ("resistance", ">=", 1000.0) in conds
    assert ("wattage", ">=", 0.25) in conds


def test_parse_aliases_and_suffixes():
    _, conds = query.parse_query("cap>=1u tol<=1 voltage<25")
    names = {c[0] for c in conds}
    assert names == {"capacitance", "tolerance", "voltage"}
    cap = [c for c in conds if c[0] == "capacitance"][0]
    assert cap[2] == 1e-06


def test_parse_mixes_text_and_conditions():
    text, conds = query.parse_query("voltage>=25 SMD")
    assert text == "SMD"
    assert conds == [("voltage", ">=", 25.0)]


def _seed(client):
    def add(cat, value, pkg, qty=10):
        cid = db.add_component({"category": cat, "value": value, "package": pkg,
                                "quantity": qty})
        db.replace_specs(cid, specs.extract_specs(cat, value, "", pkg))
        return cid
    return {
        "r10k_q": add("resistor", "10kΩ 0.25W 1%", "0805"),
        "r1k_w":  add("resistor", "1kΩ 1W 5%", "2512"),
        "c10u":   add("capacitor", "10µF 16V", "0805"),
        "c100n":  add("capacitor", "100nF 50V", "0603"),
    }


def test_range_filter_resistance(client):
    ids = _seed(client)
    hits = db.list_components(spec_conditions=[("resistance", ">=", 5000)])
    got = {c["id"] for c in hits}
    assert ids["r10k_q"] in got and ids["r1k_w"] not in got


def test_range_filter_and_logic(client):
    ids = _seed(client)
    # resistance >= 500 AND wattage >= 0.5  -> only the 1kΩ 1W part
    hits = db.list_components(spec_conditions=[("resistance", ">=", 500),
                                              ("wattage", ">=", 0.5)])
    got = {c["id"] for c in hits}
    assert got == {ids["r1k_w"]}


def test_range_filter_voltage(client):
    ids = _seed(client)
    hits = db.list_components(spec_conditions=[("voltage", ">=", 25)])
    got = {c["id"] for c in hits}
    assert ids["c100n"] in got and ids["c10u"] not in got


def test_search_route_with_q_specs(client):
    _seed(client)
    r = client.get("/search?q_specs=" + "resistance>=5000")
    assert r.status_code == 200
    assert b"10k" in r.data and b"1k" not in r.data.replace(b"10k", b"")


def test_bad_operator_is_ignored(client):
    _seed(client)
    # An operator not in the whitelist must not reach SQL; passing a junk op
    # simply yields no spec constraint.
    hits = db.list_components(spec_conditions=[("resistance", "DROP", 1)])
    assert len(hits) == 4
