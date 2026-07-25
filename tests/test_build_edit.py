"""Editing/deleting a build after creation, with stock reconciliation."""

import db


def _make_build(board_qty, stock=100, per_board=3):
    """A resistor with `stock` on hand, consumed by a build of `board_qty`
    boards using `per_board` each. Returns (component_id, build_id)."""
    cid = db.add_component({"category": "resistor", "part_number": "R1",
                            "quantity": stock})
    items = [{"component_id": cid, "part_number": "R1", "value": "10k",
              "designator": "R1", "qty_per_board": per_board}]
    bid, shortages = db.record_build("Board A", board_qty, "", items)
    return cid, bid


def test_record_deducts(client):
    cid, bid = _make_build(board_qty=2)          # 3 * 2 = 6 consumed
    assert db.get_component(cid)["quantity"] == 94


def test_increase_qty_deducts_more(client):
    cid, bid = _make_build(board_qty=2)          # 94 left, consumed 6
    ok, shortages = db.update_build(bid, board_qty=5)   # now 3*5 = 15
    assert ok and not shortages
    assert db.get_component(cid)["quantity"] == 85       # 100 - 15
    assert db.get_build(bid)["board_qty"] == 5


def test_decrease_qty_returns_stock(client):
    cid, bid = _make_build(board_qty=5)          # consumed 15 -> 85 left
    ok, shortages = db.update_build(bid, board_qty=1)   # now 3
    assert ok and not shortages
    assert db.get_component(cid)["quantity"] == 97       # 100 - 3


def test_increase_beyond_stock_flags_shortage_and_clamps(client):
    cid, bid = _make_build(board_qty=1, stock=5) # consumed 3 -> 2 left
    ok, shortages = db.update_build(bid, board_qty=10)  # needs 30, only 5 exist
    assert ok and shortages
    assert db.get_component(cid)["quantity"] == 0        # never negative
    # qty_consumed on the item reflects what was actually taken (5, not 30).
    assert db.get_build(bid)["items"][0]["qty_consumed"] == 5


def test_delete_returns_parts(client):
    cid, bid = _make_build(board_qty=4)          # consumed 12 -> 88 left
    restocked = db.delete_build(bid)
    assert restocked == 12
    assert db.get_component(cid)["quantity"] == 100
    assert db.get_build(bid) is None
    assert len(db.list_builds()) == 0


def test_edit_route_reconciles(client):
    cid, bid = _make_build(board_qty=2)          # 94 left
    r = client.post(f"/builds/{bid}/update", data={"board_qty": "4"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert db.get_component(cid)["quantity"] == 88   # 100 - 12


def test_delete_route(client):
    cid, bid = _make_build(board_qty=2)
    r = client.post(f"/builds/{bid}/delete", follow_redirects=True)
    assert r.status_code == 200
    assert db.get_component(cid)["quantity"] == 100
    assert db.list_builds() == []


def test_edit_missing_build_404(client):
    assert client.post("/builds/999/update", data={"board_qty": "2"}).status_code == 404
    assert client.post("/builds/999/delete").status_code == 404
