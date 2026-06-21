"""Parse Bill-of-Materials files from suppliers into normalized part rows."""

import csv
import io
import os
import re

HEADER_ALIASES = {
    "quantity": [
        "quantity", "qty", "order qty", "order quantity", "qty ordered",
        "quantity ordered", "qnty", "amount",
    ],
    "part_number": [
        "manufacture part number", "manufacturer part number", "mfr part #",
        "mfr part number", "manufacturer part #", "mpn",
        "manufacturer partno", "mfg part #", "mfg part number",
    ],
    "supplier_pn": [
        "lcsc part number", "lcsc part", "lcsc", "digikey part number",
        "digi-key part number", "digikey part #", "supplier part number",
        "supplier part", "order code", "customer no.", "stock code",
    ],
    "manufacturer": ["manufacturer", "manufacture", "mfr", "brand", "mfg"],
    "description": ["description", "desc", "details", "comment", "specification"],
    "package": ["package", "footprint", "case", "package/case", "case/package"],
    "value": ["value", "comment", "comp value", "val"],
    "unit_cost": [
        "unit price", "unit price($)", "unit price(usd)", "price", "unit cost",
        "unit price (usd)", "unitprice",
    ],
    "datasheet_url": ["datasheet", "datasheet url", "datasheet link"],
    "designator": [
        "designator", "designators", "reference", "references", "refdes",
        "ref des", "ref", "customer reference",
    ],
}

# Categorization runs top to bottom and returns the FIRST match, so order
# matters: the finer "purpose" categories sit above the broad families, so a
# linear regulator becomes "voltage regulator" instead of the generic "ic", and
# a MOSFET becomes "mosfet" instead of the catch-all "transistor". To add a new
# purpose, drop another (name, [patterns]) tuple in the right spot — nothing else
# needs to change; a category with stock automatically gets its own tab.
CATEGORY_RULES = [
    # --- finer purposes (checked first) ---
    ("voltage regulator", [r"\bvoltage regulator", r"\bregulator\b", r"\bLDO\b",
                           r"\bbuck\b", r"\bboost\b", r"\bdc[-/ ]?dc\b",
                           r"\bswitching reg", r"\blinear reg", r"\bpmic\b"]),
    ("voltage reference", [r"\bvoltage reference", r"\bvref\b", r"\bshunt reference"]),
    ("optocoupler", [r"\boptocoupler", r"\bopto-?isolator", r"\boptoisolator",
                     r"\bphotocoupler"]),
    ("mosfet", [r"\bmosfet", r"\bn-?channel\b", r"\bp-?channel\b"]),
    ("microcontroller", [r"\bmicro ?controller", r"\bmcu\b"]),
    # --- broad families ---
    ("resistor", [r"\bresistor", r"\bres\b", r"\d+\s*k?ohm", r"\d+\s*k?Ω", r"\bRC\d{3,4}"]),
    ("capacitor", [r"\bcapacitor", r"\bcap\b", r"\d+\s*[pnuµ]f", r"mlcc", r"tantalum"]),
    ("inductor", [r"\binductor", r"\bferrite", r"\d+\s*[pnuµm]h\b", r"\bbead\b"]),
    ("diode", [r"\bdiode", r"\bzener", r"\bschottky", r"\bled\b", r"\brectifier"]),
    ("transistor", [r"\btransistor", r"\bbjt\b", r"\bnpn\b", r"\bpnp\b", r"\bigbt", r"\bjfet"]),
    ("ic", [r"\bic\b", r"\bamplifier", r"\beeprom", r"\bflash\b", r"\bop-?amp",
            r"\blogic\b", r"\bdriver\b", r"\bsensor"]),
    ("connector", [r"\bconnector", r"\bheader", r"\bsocket", r"\bjack\b", r"\bterminal",
                   r"\busb\b", r"\bjst\b"]),
    ("crystal", [r"\bcrystal", r"\boscillator", r"\bresonator", r"\bMHz\b"]),
    ("switch", [r"\bswitch", r"\bbutton", r"\btactile", r"\brelay\b"]),
    ("fuse", [r"\bfuse", r"\bptc\b", r"\bpolyfuse"]),
]

# Fallback when the description text matches nothing: many parts arrive as a bare
# manufacturer part number (e.g. "AO3407") with no descriptive words, so we map
# common part-number families to a category. Matched with re.match (anchored at
# the start) against the UPPERCASED part number. Add families freely.
PART_PREFIXES = [
    ("mosfet", [r"AO3\d{3}", r"AO\d{4}", r"IRF\d", r"IRL[ZU]?\d", r"BSS\d",
                r"2N7000", r"SI\d{4}", r"2SK\d", r"FQP\d", r"FD[SN]\d", r"AOD\d"]),
    ("transistor", [r"2N\d", r"BC[0-9]", r"2SC\d", r"2SA\d", r"MMBT", r"S8050",
                    r"S8550", r"BD\d", r"TIP\d", r"BCP\d"]),
    ("voltage regulator", [r"LM78\d", r"LM79\d", r"LM317", r"LM337", r"LM1117",
                           r"AMS1117", r"LD1117", r"MIC5\d", r"MCP170\d", r"TPS\d",
                           r"LP29\d", r"XC6206", r"HT75\d", r"AOZ\d", r"RT9\d{3}",
                           r"ME6211", r"SY8\d{3}"]),
    ("voltage reference", [r"TL431", r"LM4040", r"LM336", r"LM385", r"REF\d{2}"]),
    ("optocoupler", [r"PC817", r"PC8\d", r"EL817", r"6N13\d", r"TLP\d", r"LTV\d"]),
    ("diode", [r"1N4\d", r"1N5\d", r"BAT\d", r"BAV\d", r"SS1\d", r"SS3\d", r"US1\w"]),
    ("microcontroller", [r"ATMEGA", r"ATTINY", r"STM32", r"STM8", r"ESP32", r"ESP8266",
                         r"PIC1\d", r"RP2040", r"GD32", r"CH32"]),
    ("ic", [r"NE555", r"LM358", r"LM324", r"LM393", r"TL07\d", r"TL08\d", r"SN74",
            r"74[HL][CS]", r"CD40\d", r"MAX232", r"AT24C", r"MCP23\d"]),
    ("crystal", [r"HC-49", r"ABM\d", r"ECS-"]),
]


def _norm_header(h):
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def guess_category(*texts):
    """Best-effort category from a part's text. Tries descriptive keywords first
    (most reliable when present), then falls back to part-number families so a
    bare part number still gets categorized, and finally "uncategorized"."""
    blob = " ".join(t for t in texts if t).lower()
    if blob:
        for cat, patterns in CATEGORY_RULES:
            for p in patterns:
                if re.search(p, blob, re.IGNORECASE):
                    return cat
    for t in texts:
        token = (t or "").strip().upper()
        if not token:
            continue
        for cat, patterns in PART_PREFIXES:
            for p in patterns:
                if re.match(p, token):
                    return cat
    return "uncategorized"


def detect_supplier(headers, sample_codes=None):
    joined = " | ".join(_norm_header(h) for h in headers)
    if "lcsc part number" in joined or "lcsc" in joined:
        return "LCSC"
    if "digikey" in joined or "digi-key" in joined:
        return "DigiKey"
    for code in (sample_codes or []):
        c = (code or "").strip().upper()
        if c.endswith("-ND") or c.endswith("-CT") or c.endswith("-TR"):
            return "DigiKey"
        if re.fullmatch(r"C\d{3,}", c):
            return "LCSC"
    return "Generic"


def _build_column_map(headers):
    colmap = {}
    bare_part_idx = None
    for idx, h in enumerate(headers):
        nh = _norm_header(h)
        if nh == "part number":
            bare_part_idx = idx
            continue
        for field, aliases in HEADER_ALIASES.items():
            if nh in aliases and field not in colmap:
                colmap[field] = idx
    if bare_part_idx is not None:
        if "part_number" not in colmap:
            colmap["part_number"] = bare_part_idx
        elif "supplier_pn" not in colmap:
            colmap["supplier_pn"] = bare_part_idx
    return colmap


def _clean_price(raw):
    if raw is None:
        return None
    s = re.sub(r"[^0-9.]+", "", str(raw))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _read_rows(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _read_xlsx(path)
    return _read_csv(path)


def _read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()
    reader = list(csv.reader(io.StringIO(text)))
    reader = [r for r in reader if any(c.strip() for c in r)]
    header_idx = _find_header_row(reader)
    headers = reader[header_idx]
    return headers, reader[header_idx + 1:]


def _read_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(values_only=True):
        rows.append(["" if c is None else str(c) for c in r])
    wb.close()
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    header_idx = _find_header_row(rows)
    headers = rows[header_idx]
    return headers, rows[header_idx + 1:]


def _find_header_row(rows):
    known = {a for aliases in HEADER_ALIASES.values() for a in aliases}
    for i, row in enumerate(rows[:10]):
        if sum(1 for c in row if _norm_header(c) in known) >= 2:
            return i
    return 0


def parse_bom(path):
    headers, raw_rows = _read_rows(path)
    colmap = _build_column_map(headers)
    warnings = []
    if "quantity" not in colmap:
        warnings.append("No quantity column found - defaulting each line to 1.")
    if "part_number" not in colmap and "supplier_pn" not in colmap:
        warnings.append("No part-number column found - rows may be hard to match.")

    def cell(row, field):
        i = colmap.get(field)
        if i is None or i >= len(row):
            return ""
        return str(row[i]).strip()

    rows = []
    for row in raw_rows:
        if not any(str(c).strip() for c in row):
            continue
        qty_raw = cell(row, "quantity")
        try:
            qty = int(float(qty_raw)) if qty_raw else 1
        except ValueError:
            qty = 1
        part = {
            "part_number": cell(row, "part_number"),
            "supplier_pn": cell(row, "supplier_pn"),
            "manufacturer": cell(row, "manufacturer"),
            "description": cell(row, "description"),
            "package": cell(row, "package"),
            "value": cell(row, "value") or cell(row, "description"),
            "quantity": qty,
            "unit_cost": _clean_price(cell(row, "unit_cost")),
            "designator": cell(row, "designator"),
        }
        if not (part["part_number"] or part["supplier_pn"] or part["value"]):
            continue
        part["category"] = guess_category(
            part["description"], part["value"], part["part_number"]
        )
        rows.append(part)

    supplier = detect_supplier(headers, [r["supplier_pn"] for r in rows])
    for r in rows:
        r["supplier"] = supplier if supplier != "Generic" else ""

    return {
        "supplier": supplier,
        "columns": sorted(colmap.keys()),
        "rows": rows,
        "warnings": warnings,
    }
