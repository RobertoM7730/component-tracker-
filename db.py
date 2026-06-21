"""All database access for the component tracker.

Routes call functions here; SQL lives here only. Every value passed to the
database goes through a parameterized query (the ``?`` placeholders) so a part
number that happens to contain SQL can never break or hijack a query.
"""

import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("TRACKER_DB", os.path.join(DATA_DIR, "components.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

COMPONENT_FIELDS = [
    "part_number", "category", "value", "package", "quantity", "min_quantity",
    "location", "manufacturer", "supplier", "supplier_pn", "unit_cost",
    "mount", "datasheet_url", "notes",
]

CANONICAL_CATEGORIES = [
    "resistor", "capacitor", "inductor", "diode", "transistor",
    "ic", "connector", "crystal", "switch",
]

_SPEC_OPS = {">=": ">=", "<=": "<=", ">": ">", "<": "<", "=": "="}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Wait up to 5s for a lock instead of erroring when multiple gunicorn
    # workers write at once (a personal app rarely hits this, but it's cheap).
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    """Create tables if missing, then apply additive migrations. Never destroys
    data: tables use IF NOT EXISTS and columns are added only when absent."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection()
    with conn:
        conn.executescript(schema)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(components)")}
        if "mount" not in existing:
            conn.execute("ALTER TABLE components ADD COLUMN mount TEXT")
    conn.close()


# --------------------------------------------------------------------------- #
# Components: read
# --------------------------------------------------------------------------- #

def list_components(search=None, category=None, sort="updated_at", low_stock=False,
                    spec_conditions=None):
    """Return components (as dicts, each with a ``specs`` list attached),
    optionally filtered by search, category, and/or spec range conditions.

    Free-text search is split on whitespace and every term must match (AND).
    ``spec_conditions`` is a list of (name, op, value) tuples compared against a
    spec's normalized value_num; all must hold (AND). Operators are whitelisted
    so they can never inject SQL. Category "other" selects everything outside
    the canonical set."""
    sql = "SELECT * FROM components WHERE 1=1"
    params = []

    if search:
        for term in search.split():
            like = f"%{term}%"
            sql += (" AND (part_number LIKE ? OR value LIKE ? OR category LIKE ?"
                    " OR manufacturer LIKE ? OR supplier_pn LIKE ? OR location LIKE ?"
                    " OR package LIKE ? OR mount LIKE ?"
                    " OR id IN (SELECT component_id FROM component_specs"
                    "           WHERE value_text LIKE ? OR name LIKE ?))")
            params += [like] * 10

    for name, op, value in (spec_conditions or []):
        o = _SPEC_OPS.get(op)
        if o is None:
            continue
        sql += (" AND id IN (SELECT component_id FROM component_specs"
                "           WHERE name = ? AND value_num IS NOT NULL"
                f"           AND value_num {o} ?)")
        params += [name, value]

    if category == "uncategorized":
        sql += " AND (category IS NULL OR category = '' OR category = 'uncategorized')"
    elif category == "other":
        placeholders = ", ".join("?" for _ in CANONICAL_CATEGORIES)
        sql += f" AND category NOT IN ({placeholders})"
        params += CANONICAL_CATEGORIES
    elif category:
        sql += " AND category = ?"
        params.append(category)

    if low_stock:
        sql += " AND quantity <= min_quantity"

    allowed_sorts = {
        "updated_at": "updated_at DESC",
        "part_number": "part_number COLLATE NOCASE ASC",
        "category": "category COLLATE NOCASE ASC, value COLLATE NOCASE ASC",
        "quantity": "quantity ASC",
    }
    sql += " ORDER BY " + allowed_sorts.get(sort, "updated_at DESC")

    conn = get_connection()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    _attach_specs(conn, rows)
    conn.close()
    return rows


def _attach_specs(conn, rows):
    """Attach a ``specs`` list to each row dict (one query for the whole page)."""
    if not rows:
        return
    ids = [r["id"] for r in rows]
    placeholders = ", ".join("?" for _ in ids)
    spec_rows = conn.execute(
        f"SELECT * FROM component_specs WHERE component_id IN ({placeholders}) "
        "ORDER BY id", ids
    ).fetchall()
    by_id = {}
    for s in spec_rows:
        by_id.setdefault(s["component_id"], []).append(dict(s))
    for r in rows:
        r["specs"] = by_id.get(r["id"], [])


def replace_specs(component_id, specs):
    """Replace all specs for a component. ``specs`` is a list of dicts with
    keys name, value_text, value_num, unit."""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM component_specs WHERE component_id = ?",
                     (component_id,))
        for s in specs:
            if not s.get("value_text"):
                continue
            conn.execute(
                "INSERT INTO component_specs "
                "(component_id, name, value_text, value_num, unit) "
                "VALUES (?, ?, ?, ?, ?)",
                (component_id, s["name"], s.get("value_text"),
                 s.get("value_num"), s.get("unit")),
            )
    conn.close()


def get_specs(component_id):
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM component_specs WHERE component_id = ? ORDER BY id",
        (component_id,)
    ).fetchall()]
    conn.close()
    return rows


def category_counts():
    """Return {category: count} across all components (raw category values)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT category, COUNT(*) AS n FROM components GROUP BY category"
    ).fetchall()
    conn.close()
    return {r["category"]: r["n"] for r in rows}


def list_categories():
    """Return the distinct, non-empty category names actually in use, sorted.
    Drives the auto-created category tabs so a new purpose (e.g. the first time a
    "voltage regulator" is added) shows up without any code change."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT category FROM components "
        "WHERE category IS NOT NULL AND category != '' "
        "ORDER BY category COLLATE NOCASE ASC"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_component(cid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM components WHERE id = ?", (cid,)).fetchone()
    if row is None:
        conn.close()
        return None
    row = dict(row)
    _attach_specs(conn, [row])
    conn.close()
    return row


def find_component_by_part(part_number, supplier_pn=None):
    """Look up an existing component by manufacturer PN, falling back to supplier
    PN. Used by BOM import to merge into an existing row instead of duplicating."""
    if not part_number and not supplier_pn:
        return None
    conn = get_connection()
    row = None
    if part_number:
        row = conn.execute(
            "SELECT * FROM components WHERE part_number = ? COLLATE NOCASE",
            (part_number,),
        ).fetchone()
    if row is None and supplier_pn:
        row = conn.execute(
            "SELECT * FROM components WHERE supplier_pn = ? COLLATE NOCASE",
            (supplier_pn,),
        ).fetchone()
    conn.close()
    return row


def stats():
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS lines, "
        "COALESCE(SUM(quantity), 0) AS units, "
        "COALESCE(SUM(quantity * COALESCE(unit_cost, 0)), 0) AS value, "
        "SUM(CASE WHEN quantity <= min_quantity THEN 1 ELSE 0 END) AS low "
        "FROM components"
    ).fetchone()
    conn.close()
    return row


# --------------------------------------------------------------------------- #
# Components: write
# --------------------------------------------------------------------------- #

def _clean(data):
    out = {}
    for f in COMPONENT_FIELDS:
        if f in data and data[f] not in (None, ""):
            out[f] = data[f]
    for f in ("quantity", "min_quantity"):
        if f in out:
            out[f] = int(out[f])
    if "unit_cost" in out:
        try:
            out["unit_cost"] = float(out["unit_cost"])
        except (TypeError, ValueError):
            out.pop("unit_cost")
    return out


def add_component(data):
    d = _clean(data)
    d.setdefault("category", "uncategorized")
    d.setdefault("quantity", 0)
    d.setdefault("min_quantity", 0)
    cols = list(d.keys()) + ["created_at", "updated_at"]
    now = _now()
    placeholders = ", ".join("?" for _ in cols)
    params = [d[c] for c in d] + [now, now]
    conn = get_connection()
    with conn:
        cur = conn.execute(
            f"INSERT INTO components ({', '.join(cols)}) VALUES ({placeholders})",
            params,
        )
        new_id = cur.lastrowid
    conn.close()
    return new_id


def update_component(cid, data):
    d = _clean(data)
    if not d:
        return
    d["updated_at"] = _now()
    assignments = ", ".join(f"{c} = ?" for c in d)
    params = list(d.values()) + [cid]
    conn = get_connection()
    with conn:
        conn.execute(f"UPDATE components SET {assignments} WHERE id = ?", params)
    conn.close()


def adjust_quantity(cid, delta):
    """Bump quantity by delta (clamped at 0). Returns the new quantity."""
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE components SET quantity = MAX(0, quantity + ?), updated_at = ? "
            "WHERE id = ?",
            (delta, _now(), cid),
        )
        row = conn.execute(
            "SELECT quantity FROM components WHERE id = ?", (cid,)
        ).fetchone()
    conn.close()
    return row["quantity"] if row else None


def delete_component(cid):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM components WHERE id = ?", (cid,))
    conn.close()


# --------------------------------------------------------------------------- #
# PCB build consumption
# --------------------------------------------------------------------------- #

def record_build(name, board_qty, notes, items):
    """Persist a consumed PCB BOM and deduct the parts from stock. Returns
    (build_id, list of shortage messages)."""
    board_qty = max(1, int(board_qty))
    now = _now()
    shortages = []
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "INSERT INTO pcb_builds (name, board_qty, notes, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, board_qty, notes, now),
        )
        build_id = cur.lastrowid
        for it in items:
            need = int(it.get("qty_per_board", 1)) * board_qty
            cid = it.get("component_id")
            consumed = 0
            if cid:
                comp = conn.execute(
                    "SELECT quantity, part_number FROM components WHERE id = ?",
                    (cid,),
                ).fetchone()
                if comp:
                    consumed = min(need, comp["quantity"])
                    conn.execute(
                        "UPDATE components SET quantity = quantity - ?, "
                        "updated_at = ? WHERE id = ?",
                        (consumed, now, cid),
                    )
                    if consumed < need:
                        shortages.append(
                            f"{comp['part_number'] or it.get('part_number')}: "
                            f"needed {need}, only {consumed} in stock"
                        )
            else:
                shortages.append(
                    f"{it.get('part_number') or it.get('value') or 'unknown'}: "
                    f"not in inventory ({need} needed)"
                )
            conn.execute(
                "INSERT INTO build_items "
                "(build_id, component_id, part_number, value, designator, "
                "qty_per_board, qty_consumed) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (build_id, cid, it.get("part_number"), it.get("value"),
                 it.get("designator"), int(it.get("qty_per_board", 1)), consumed),
            )
    conn.close()
    return build_id, shortages


def list_builds():
    conn = get_connection()
    rows = conn.execute(
        "SELECT b.*, COUNT(i.id) AS line_count, "
        "COALESCE(SUM(i.qty_consumed), 0) AS parts_used "
        "FROM pcb_builds b LEFT JOIN build_items i ON i.build_id = b.id "
        "GROUP BY b.id ORDER BY b.created_at DESC"
    ).fetchall()
    conn.close()
    return rows
