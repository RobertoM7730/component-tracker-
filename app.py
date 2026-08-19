"""Flask app for the electrical component tracker.

Routes stay thin: parse the request, call a function in ``db``, render a
template. SQL lives in ``db.py``, BOM parsing in ``bom.py``, spec extraction in
``specs.py``, and search-query parsing in ``query.py``.
"""

import csv
import io
import json
import os
import tempfile

from flask import (
    Flask, render_template, request, redirect, url_for, abort, Response, flash
)

import db
import bom
import categories
import specs
import query
import lookup

try:
    import segno  # pure-Python QR code generator, no extra dependencies
except ImportError:  # QR just won't render until `pip install segno`
    segno = None

app = Flask(__name__)
app.secret_key = os.environ.get("TRACKER_SECRET", "dev-only-change-me")

db.init_db()

ALLOWED_EXT = {".csv", ".xlsx", ".xlsm", ".xls"}

# Labels come from categories.py, so a tab is named the same way everywhere.
CANON_TABS = [(categories.label(c), c) for c in categories.PRIMARY]


@app.template_filter("category_label")
def category_label(value):
    """Render a category the way the tabs do, so a part's pill reads "ICs"
    rather than the raw stored "ic"."""
    return categories.label(value)


@app.template_filter("money")
def money(v):
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def build_tabs(active):
    """Build the tab bar: All, each primary category, then any other category
    that's actually in use (auto-created from the data), then Uncategorized.

    The primary tabs always show (even at count 0) so the core families stay
    put. A new purpose like "voltage regulator" appears on its own tab the moment
    a part lands in it — no code change needed — and drops off when emptied.
    Every name is normalized first, so "IC", "ICs" and "Ic" share one tab
    instead of splitting the shelf three ways."""
    raw_counts = db.category_counts()
    counts = {}
    for name, n in raw_counts.items():
        counts[categories.normalize(name)] = counts.get(
            categories.normalize(name), 0) + n
    active = categories.normalize(active) if active else ""
    total = sum(counts.values())
    tabs = [{"label": "All", "value": "", "count": total,
             "active": active in (None, "")}]
    for label, value in CANON_TABS:
        tabs.append({"label": label, "value": value,
                     "count": counts.get(value, 0), "active": active == value})

    # Auto-created tabs: any in-use category that isn't primary or the
    # uncategorized bucket, ordered the way categories.py groups them.
    extra = sorted((c for c in counts
                    if c not in db.CANONICAL_CATEGORIES
                    and c != categories.UNCATEGORIZED),
                   key=categories.sort_key)
    for value in extra:
        tabs.append({"label": categories.label(value), "value": value,
                     "count": counts.get(value, 0), "active": active == value})

    tabs.append({"label": "Uncategorized", "value": "uncategorized",
                 "count": counts.get(categories.UNCATEGORIZED, 0),
                 "active": active == categories.UNCATEGORIZED})
    return tabs


def _spec_meta():
    """Category -> [(spec_name, label, unit)] for the edit form's fields."""
    meta = {}
    for cat, pairs in specs.SPECS_BY_CATEGORY.items():
        meta[cat] = [(name, specs.LABEL_BY_NAME.get(name, name), unit)
                     for name, unit in pairs]
    return meta


# Spec rows shown in the filter panel per category. "all" is the default set
# used on the All/Other tabs (or any category without its own specs).
_FILTER_ALL = ["resistance", "capacitance", "inductance", "voltage",
               "current", "wattage", "tolerance", "frequency"]


def _filter_meta():
    meta = {"all": [(n, specs.LABEL_BY_NAME.get(n, n), specs.UNIT_BY_NAME.get(n, ""))
                    for n in _FILTER_ALL]}
    for cat, pairs in specs.SPECS_BY_CATEGORY.items():
        meta[cat] = [(name, specs.LABEL_BY_NAME.get(name, name), unit)
                     for name, unit in pairs]
    return meta


def _parse_search():
    """Combine the free-text box (q) and panel-built operators (q_specs), then
    return (display_text, free_text_for_db, spec_conditions)."""
    q = request.args.get("q", "").strip()
    q_specs = request.args.get("q_specs", "").strip()
    combined = (q + " " + q_specs).strip()
    text, conditions = query.parse_query(combined)
    return q, text, conditions


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #

def _category_arg():
    """The category filter from the query string, folded to its canonical name so
    an old bookmark of ``?category=ICs`` still lands on the ICs tab."""
    raw = request.args.get("category", "").strip()
    return categories.normalize(raw) if raw else ""


@app.route("/")
def index():
    q_display, text, conditions = _parse_search()
    category = _category_arg()
    sort = request.args.get("sort", "updated_at")
    components = db.list_components(search=text, category=category, sort=sort,
                                   spec_conditions=conditions)
    return render_template(
        "index.html",
        components=components,
        tabs=build_tabs(category),
        stats=db.stats(),
        search=q_display,
        q_specs=request.args.get("q_specs", ""),
        filter_meta=_filter_meta(),
        category=category,
        sort=sort,
    )


@app.route("/search")
def search():
    """HTMX endpoint: returns just the table body as the user types/filters."""
    q_display, text, conditions = _parse_search()
    category = _category_arg()
    sort = request.args.get("sort", "updated_at")
    components = db.list_components(search=text, category=category, sort=sort,
                                   spec_conditions=conditions)
    return render_template("partials/rows.html", components=components)


@app.route("/component/new")
def new_component():
    return render_template("edit.html", component=None, spec_meta=_spec_meta(),
                           all_categories=categories.ALL)


@app.route("/component/<int:cid>/edit")
def edit_component(cid):
    component = db.get_component(cid)
    if component is None:
        abort(404)
    return render_template("edit.html", component=component,
                           spec_meta=_spec_meta(),
                           all_categories=categories.ALL)


@app.route("/component/save", methods=["POST"])
@app.route("/component/<int:cid>/save", methods=["POST"])
def save_component(cid=None):
    data = {f: request.form.get(f, "").strip() for f in db.COMPONENT_FIELDS}
    # Normalize here too (not just on the way into the database) so the specs
    # extracted below are the ones for the canonical category.
    data["category"] = categories.normalize(data.get("category"))
    if not data.get("mount"):
        data["mount"] = specs.guess_mount(data.get("package"), data.get("notes"))
    spec_list = _specs_from_form(data["category"], request.form,
                                 data.get("value"), data.get("notes"),
                                 data.get("package"))
    if cid:
        db.update_component(cid, data)
        db.replace_specs(cid, spec_list)
        flash("Component updated.", "ok")
    else:
        new_id = db.add_component(data)
        db.replace_specs(new_id, spec_list)
        flash("Component added.", "ok")
    return redirect(url_for("index"))


def _specs_from_form(category, form, value, description, package):
    """Build the spec list to store. Prefer typed spec fields; otherwise
    auto-extract from the value/description text."""
    manual = []
    for name in specs.specs_for_category(category):
        raw = form.get(f"spec_{name}", "").strip()
        if not raw:
            continue
        parsed = specs.PARSERS[name](raw)
        text, num = parsed if parsed else (raw, None)
        manual.append({"name": name, "value_text": text, "value_num": num,
                       "unit": specs.UNIT_BY_NAME.get(name, "")})
    if manual:
        return manual
    return specs.extract_specs(category, value, description, package)


@app.route("/component/<int:cid>/delete", methods=["POST"])
def delete_component(cid):
    db.delete_component(cid)
    if request.headers.get("HX-Request"):
        return ""
    flash("Component deleted.", "ok")
    return redirect(url_for("index"))


@app.route("/component/<int:cid>/qty", methods=["POST"])
def adjust_qty(cid):
    """HTMX stepper. delta=+1/-1 (or any int). Returns the refreshed row."""
    try:
        delta = int(request.form.get("delta", "0"))
    except ValueError:
        delta = 0
    db.adjust_quantity(cid, delta)
    component = db.get_component(cid)
    if component is None:
        abort(404)
    return render_template("partials/row.html", c=component)


# --------------------------------------------------------------------------- #
# Component detail page  (this is what an NFC tag points to)
# --------------------------------------------------------------------------- #

def _qr_svg(url):
    """Return an inline SVG QR code for the URL, or None if segno isn't
    installed. The QR is a convenience/fallback — the NFC tag itself just stores
    the plain URL, so scanning a tag works with or without this."""
    if segno is None:
        return None
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=4, border=2,
                                    xmldecl=False)
    return buf.getvalue().decode("utf-8")


@app.route("/c/<int:cid>")
def component_detail(cid):
    """Detail page for one component. Kept at the short path /c/<id> so the URL
    written onto the NFC tag stays small. Tap the tag -> phone opens this page."""
    component = db.get_component(cid)
    if component is None:
        abort(404)
    nfc_url = url_for("component_detail", cid=cid, _external=True)
    return render_template("detail.html", c=component, nfc_url=nfc_url,
                           qr_svg=_qr_svg(nfc_url),
                           spec_label=specs.LABEL_BY_NAME)


@app.route("/c/<int:cid>/container", methods=["POST"])
def set_container(cid):
    """Set/update the free-text container label for a component. This is the field
    you fill in when you scan a container's tag, so the tracker remembers where the
    part lives for next time. Accepts letters, numbers, and simple punctuation."""
    if db.get_component(cid) is None:
        abort(404)
    container = request.form.get("container", "").strip()
    db.update_component(cid, {"container": container})
    # update_component ignores empty values, so clear explicitly when blanked.
    if not container:
        db.clear_container(cid)
    component = db.get_component(cid)
    return render_template("partials/container_field.html", c=component, saved=True)


@app.route("/c/<int:cid>/qty", methods=["POST"])
def detail_adjust_qty(cid):
    """HTMX stepper for the detail page. Returns just the quantity control so the
    number updates in place without reloading (handy when scanning at the bench)."""
    try:
        delta = int(request.form.get("delta", "0"))
    except ValueError:
        delta = 0
    db.adjust_quantity(cid, delta)
    component = db.get_component(cid)
    if component is None:
        abort(404)
    return render_template("partials/qty_control.html", c=component)


@app.route("/low-stock")
def low_stock():
    components = db.list_components(low_stock=True, sort="quantity")
    return render_template("low_stock.html", components=components,
                           stats=db.stats())


@app.route("/export.csv")
def export_csv():
    components = db.list_components(sort="category")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(db.COMPONENT_FIELDS)
    for c in components:
        writer.writerow([c.get(f) for f in db.COMPONENT_FIELDS])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"},
    )


# --------------------------------------------------------------------------- #
# BOM import — shared helpers
# --------------------------------------------------------------------------- #

def _save_upload():
    file = request.files.get("bom")
    if not file or not file.filename:
        return None, "Please choose a file to upload."
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return None, f"Unsupported file type '{ext}'. Use CSV or XLSX."
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    file.save(path)
    return path, None


def _parse_or_flash(path):
    try:
        result = bom.parse_bom(path)
    except Exception as e:
        return None, f"Could not read that file: {e}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if not result["rows"]:
        return None, "No part rows were found in that file."
    return result, None


# --------------------------------------------------------------------------- #
# BOM import — order (adds stock)
# --------------------------------------------------------------------------- #

@app.route("/import")
def import_home():
    return render_template("import.html")


@app.route("/import/order", methods=["POST"])
def import_order_preview():
    path, err = _save_upload()
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))
    result, err = _parse_or_flash(path)
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))

    for r in result["rows"]:
        # Offline rules already set r["category"]; only spend an online lookup on
        # the ones they couldn't place (and only if a key is configured).
        if r.get("category") == "uncategorized":
            online = lookup.lookup_category(r.get("part_number"))
            if online:
                r["category"] = online
        existing = db.find_component_by_part(r["part_number"], r["supplier_pn"])
        r["existing_id"] = existing["id"] if existing else None
        r["existing_qty"] = existing["quantity"] if existing else None
        r["mount"] = specs.guess_mount(r.get("package"), r.get("description"))
        r["specs"] = specs.extract_specs(r.get("category"), r.get("value"),
                                         r.get("description"), r.get("package"))

    return render_template("import_order_preview.html", result=result,
                           payload=json.dumps(result["rows"]))


@app.route("/import/order/commit", methods=["POST"])
def import_order_commit():
    rows = json.loads(request.form.get("payload", "[]"))
    selected = set(request.form.getlist("include"))
    added, merged = 0, 0
    for i, r in enumerate(rows):
        if str(i) not in selected:
            continue
        qty = int(request.form.get(f"qty_{i}", r.get("quantity", 0)) or 0)
        category = categories.normalize(
            request.form.get(f"category_{i}", r.get("category")))
        location = request.form.get(f"location_{i}", "").strip()
        spec_list = specs.extract_specs(category, r.get("value"),
                                        r.get("description"), r.get("package"))
        mount = specs.guess_mount(r.get("package"), r.get("description"))
        existing = db.find_component_by_part(r.get("part_number"), r.get("supplier_pn"))
        if existing:
            db.adjust_quantity(existing["id"], qty)
            if location:
                db.update_component(existing["id"], {"location": location})
            if not db.get_specs(existing["id"]):
                db.replace_specs(existing["id"], spec_list)
                db.update_component(existing["id"], {"mount": mount})
            merged += 1
        else:
            new_id = db.add_component({
                "part_number": r.get("part_number"),
                "category": category,
                "value": r.get("value"),
                "package": r.get("package"),
                "quantity": qty,
                "manufacturer": r.get("manufacturer"),
                "supplier": r.get("supplier"),
                "supplier_pn": r.get("supplier_pn"),
                "unit_cost": r.get("unit_cost"),
                "location": location,
                "mount": mount,
                "notes": r.get("description"),
            })
            db.replace_specs(new_id, spec_list)
            added += 1
    flash(f"Order imported: {added} new part(s) added, {merged} restocked.", "ok")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- #
# BOM import — PCB (consumes stock)
# --------------------------------------------------------------------------- #

@app.route("/import/pcb", methods=["POST"])
def import_pcb_preview():
    path, err = _save_upload()
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))
    result, err = _parse_or_flash(path)
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))

    board_qty = max(1, int(request.form.get("board_qty", "1") or 1))
    name = request.form.get("name", "").strip() or "Untitled board"

    for r in result["rows"]:
        existing = db.find_component_by_part(r["part_number"], r["supplier_pn"])
        r["component_id"] = existing["id"] if existing else None
        r["in_stock"] = existing["quantity"] if existing else 0
        r["qty_per_board"] = r.get("quantity", 1) or 1
        r["need"] = r["qty_per_board"] * board_qty
        r["short"] = max(0, r["need"] - r["in_stock"])

    buildable = all(r["short"] == 0 for r in result["rows"])
    return render_template("import_pcb_preview.html", result=result, name=name,
                           board_qty=board_qty, buildable=buildable,
                           payload=json.dumps(result["rows"]))


@app.route("/import/pcb/commit", methods=["POST"])
def import_pcb_commit():
    rows = json.loads(request.form.get("payload", "[]"))
    name = request.form.get("name", "Untitled board").strip() or "Untitled board"
    board_qty = max(1, int(request.form.get("board_qty", "1") or 1))
    notes = request.form.get("notes", "").strip()
    items = [{
        "component_id": r.get("component_id"),
        "part_number": r.get("part_number"),
        "value": r.get("value"),
        "designator": r.get("designator"),
        "qty_per_board": int(r.get("qty_per_board", 1) or 1),
    } for r in rows]
    build_id, shortages = db.record_build(name, board_qty, notes, items)
    if shortages:
        flash("Build recorded, but some parts ran short: " + "; ".join(shortages), "warn")
    else:
        flash(f"Build '{name}' x{board_qty} recorded and stock deducted.", "ok")
    return redirect(url_for("builds"))


# --------------------------------------------------------------------------- #
# BOM comparison (checks stock without consuming)
# --------------------------------------------------------------------------- #

@app.route("/compare/preview", methods=["POST"])
def compare_preview():
    path, err = _save_upload()
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))
    result, err = _parse_or_flash(path)
    if err:
        flash(err, "err")
        return redirect(url_for("import_home"))

    board_qty = max(1, int(request.form.get("board_qty", "1") or 1))
    name = request.form.get("name", "").strip() or "Untitled project"

    for r in result["rows"]:
        if r.get("package") and ":" in r["package"]:
            r["kicad_footprint"] = r["package"]
            r["package"] = bom.normalize_kicad_footprint(r["package"])

        r["qty_per_board"] = r.get("quantity", 1) or 1
        r["need"] = r["qty_per_board"] * board_qty

        category = r.get("category", "uncategorized")

        exact = db.find_component_by_part(r.get("part_number"), r.get("supplier_pn"))
        if exact:
            r["match_type"] = "exact"
            r["matched"] = dict(exact)
            r["in_stock"] = exact["quantity"]
            continue

        spec_name = specs.PRIMARY_SPEC.get(category)
        if spec_name:
            parsed = specs.parse_value_for_category(r.get("value", ""), category)
            if parsed:
                _, spec_value = parsed
                matches = db.find_compatible(category, spec_name, spec_value,
                                             r.get("package"))
                if matches:
                    best = matches[0]
                    pkg = r.get("package", "").lower()
                    best_pkg = (best.get("package") or "").lower()
                    pkg_match = pkg and pkg in best_pkg
                    r["match_type"] = "compatible" if pkg_match else "partial"
                    r["matched"] = best
                    r["in_stock"] = best["quantity"]
                    continue

        r["match_type"] = "none"
        r["matched"] = None
        r["in_stock"] = 0

    stock_remaining = {}
    for r in result["rows"]:
        matched = r.get("matched")
        if matched:
            cid = matched["id"]
            if cid not in stock_remaining:
                stock_remaining[cid] = r["in_stock"]
            allocated = min(r["need"], stock_remaining[cid])
            stock_remaining[cid] -= allocated
            r["short"] = r["need"] - allocated
        else:
            r["short"] = r["need"]

    matched_count = sum(1 for r in result["rows"] if r["match_type"] == "exact"
                        and r["short"] <= 0)
    compatible_count = sum(1 for r in result["rows"]
                          if r["match_type"] in ("compatible", "partial")
                          and r["short"] <= 0)
    missing_count = sum(1 for r in result["rows"] if r["match_type"] == "none")
    short_count = sum(1 for r in result["rows"]
                      if r["match_type"] != "none" and r["short"] > 0)

    payload_rows = []
    for r in result["rows"]:
        payload_rows.append({
            "part_number": r.get("part_number"),
            "value": r.get("value"),
            "package": r.get("package"),
            "category": r.get("category"),
            "designator": r.get("designator"),
            "description": r.get("description"),
            "quantity": r.get("quantity"),
            "need": r.get("need"),
            "short": r.get("short"),
            "match_type": r.get("match_type"),
        })

    return render_template(
        "compare_preview.html",
        result=result,
        name=name,
        board_qty=board_qty,
        matched_count=matched_count,
        compatible_count=compatible_count,
        missing_count=missing_count,
        short_count=short_count,
        payload=json.dumps(payload_rows),
    )


@app.route("/compare/shopping-list.csv", methods=["POST"])
def compare_shopping_list():
    rows = json.loads(request.form.get("payload", "[]"))
    board_qty = max(1, int(request.form.get("board_qty", "1") or 1))
    name = request.form.get("name", "project").strip().replace(" ", "_")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Quantity", "Part Number", "Value", "Package",
                     "Category", "Designator", "Description"])

    for r in rows:
        qty_to_buy = r.get("short", 0) or 0
        if r.get("match_type") == "none":
            qty_to_buy = r.get("need", r.get("quantity", 1))
        if qty_to_buy <= 0:
            continue
        writer.writerow([
            qty_to_buy,
            r.get("part_number", ""),
            r.get("value", ""),
            r.get("package", ""),
            r.get("category", ""),
            r.get("designator", ""),
            r.get("description", ""),
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename={name}_shopping_list.csv"},
    )


@app.route("/builds/<int:bid>/update", methods=["POST"])
def edit_build(bid):
    """Change a build's quantity (and optionally name/notes) after creation,
    reconciling stock. Used when you actually built a different number of boards
    than first recorded."""
    board_qty = request.form.get("board_qty")
    ok, shortages = db.update_build(
        bid,
        board_qty=board_qty if board_qty not in (None, "") else None,
        name=request.form.get("name"),
        notes=request.form.get("notes"),
    )
    if not ok:
        abort(404)
    if shortages:
        flash("Build updated, but some parts ran short: " + "; ".join(shortages),
              "warn")
    else:
        flash("Build updated and stock reconciled.", "ok")
    return redirect(url_for("builds"))


@app.route("/builds/<int:bid>/delete", methods=["POST"])
def remove_build(bid):
    """Delete a build and return the parts it consumed back to stock."""
    restocked = db.delete_build(bid)
    if restocked is None:
        abort(404)
    flash(f"Build deleted; {restocked} part(s) returned to stock.", "ok")
    return redirect(url_for("builds"))


@app.route("/builds")
def builds():
    return render_template("builds.html", builds=db.list_builds())


@app.cli.command("init-db")
def init_db_command():
    """flask --app app init-db  -> create the database file and tables."""
    db.init_db()
    print(f"Initialised database at {db.DB_PATH}")


if __name__ == "__main__":
    app.run(debug=True, port=8000)
