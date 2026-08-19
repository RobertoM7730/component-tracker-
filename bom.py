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
    # --- finer purposes (checked first, order matters) ---
    ("voltage regulator", [r"\bvoltage regulator", r"\bregulator\b", r"\bLDO\b",
                           r"\bbuck\b", r"\bboost\b", r"\bdc[-/ ]?dc\b",
                           r"\bswitching reg", r"\blinear reg", r"\bpmic\b"]),
    ("voltage reference", [r"\bvoltage reference", r"\bvref\b", r"\bshunt reference"]),
    ("optocoupler", [r"\boptocoupler", r"\bopto-?isolator", r"\boptoisolator",
                     r"\bphotocoupler"]),
    ("dac", [r"\bdac\b", r"\bdigital.to.analog", r"\bd/?a converter",
             r"\baudio dac\b"]),
    ("adc", [r"\badc\b", r"\banalog.to.digital", r"\ba/?d converter",
             r"\bsigma.delta"]),
    ("op-amp", [r"\bop-?amp", r"\boperational amplifier", r"\binstrumentation amp",
                r"\bdifferential amp", r"\brail.to.rail", r"\bcmos amp"]),
    ("mosfet", [r"\bmosfet", r"\bn-?channel\b", r"\bp-?channel\b",
                r"\bnmos\b", r"\bpmos\b", r"\benhancement mode",
                r"\bpower fet\b", r"\bVds\b", r"\bRds", r"\bsignal fet"]),
    ("microcontroller", [r"\bmicro ?controller", r"\bmcu\b", r"\bsoc\b",
                         r"\bsystem on chip"]),
    ("sensor", [r"\bsensor\b", r"\bthermistor\b", r"\baccelerometer\b",
                r"\bgyroscope\b", r"\bbarometer\b", r"\bhumidity\b",
                r"\btemperature sensor", r"\bIMU\b", r"\bproximity\b",
                r"\bhall effect\b", r"\bcurrent sense\b", r"\bphotodiode\b",
                r"\bphototransistor\b"]),
    ("memory", [r"\beeprom\b", r"\bflash\b(?!.*light)", r"\bsram\b", r"\bdram\b",
                r"\bsdram\b", r"\bfram\b", r"\bnand\b", r"\bnor flash",
                r"\bserial flash"]),
    ("led driver", [r"\bled driver", r"\bled controller", r"\bconstant current.*led",
                    r"\bbacklight driver"]),
    ("motor driver", [r"\bmotor driver", r"\bh-?bridge", r"\bhalf-?bridge",
                      r"\bstepper driver", r"\bbrushless driver", r"\bbldc driver",
                      r"\bgate driver"]),
    # --- broad families ---
    ("resistor", [r"\bresistor", r"\bres\b", r"\d+\s*k?ohm", r"\d+\s*k?Ω", r"\bRC\d{3,4}"]),
    ("capacitor", [r"\bcapacitor", r"\bcap\b", r"\d+\s*[pnuµ]f\b", r"mlcc", r"tantalum"]),
    ("inductor", [r"\binductor", r"\bferrite", r"\d+\s*[pnuµm]h\b", r"\bbead\b"]),
    ("diode", [r"\bdiode", r"\bzener", r"\bschottky", r"\bled\b", r"\brectifier",
               r"\btvs\b", r"\besd\b"]),
    ("transistor", [r"\btransistor", r"\bbjt\b", r"\bnpn\b", r"\bpnp\b", r"\bigbt", r"\bjfet"]),
    ("ic", [r"\bic\b", r"\bamplifier", r"\blogic\b", r"\bdriver\b",
            r"\bcomparator\b", r"\btimer\b", r"\bmultiplexer\b", r"\bmux\b",
            r"\blevel shift", r"\bcodec\b", r"\btransceiver\b", r"\buart\b",
            r"\bspi\b", r"\bi2c\b"]),
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
    # --- finer IC purposes (checked first) ---
    ("dac", [r"MCP47\d", r"MCP48\d", r"DAC8\d", r"DAC7\d", r"AD56\d", r"AD53\d",
             r"AD55\d", r"PCM5\d", r"TLC56\d", r"TLV56\d", r"MAX54\d", r"MAX55\d",
             r"DAC12\d", r"DAC08\d", r"DAC1\d{3}", r"PT8211"]),
    ("adc", [r"ADS1\d{3}", r"ADS8\d", r"MCP3\d{3}", r"MCP3\d{2}[0-9]",
             r"AD7\d{3}", r"AD9\d{3}", r"MAX1\d{3}", r"MAX1\d{2}[0-9]",
             r"ADS7\d", r"HX711", r"NAU7802", r"CS5\d{3}", r"PCM18\d"]),
    ("op-amp", [r"OPA\d", r"OPT\d", r"MCP6\d{3}", r"MCP6\d{2}[0-9]", r"AD8\d{3}",
                r"AD8\d{2}[0-9]", r"LM358", r"LM324", r"LM393",
                r"LMV\d{3}", r"TL07\d", r"TL08\d", r"NE5532", r"NE5534",
                r"LMC\d{3}", r"TSV\d{3}", r"INA\d{3}", r"MAX4\d{3}",
                r"LT1\d{3}", r"ADA4\d"]),
    ("sensor", [r"BME\d{3}", r"BMP\d{3}", r"BNO\d{3}", r"BMI\d{3}",
                r"MPU\d{4}", r"LSM\d{3}", r"ADXL\d", r"DHT\d", r"SHT\d",
                r"ACS7\d", r"AHT\d", r"LM35", r"TMP\d{2,3}", r"DS18B",
                r"MAX3\d{3}", r"MAX6\d{3}", r"HTU\d", r"SI7\d{3}",
                r"ICM\d{5}", r"VL53", r"TSL\d", r"BH17\d"]),
    ("memory", [r"AT24C", r"AT25\d", r"M24\d", r"M95\d", r"W25Q", r"W25N",
                r"IS25\w", r"MX25\w", r"S25FL", r"SST25", r"SST26",
                r"GD25", r"FM24\d", r"MB85", r"IS62\w", r"IS61\w",
                r"23K\d", r"23LC", r"24LC", r"24FC", r"93C\d{2}"]),
    ("led driver", [r"TLC59\d", r"PCA96\d", r"IS31\w", r"WS28\d",
                    r"AP33\d", r"AL8\d", r"CAT4\d", r"LM3\d{3}",
                    r"MAX7\d{3}", r"STP16\w"]),
    ("motor driver", [r"DRV8\d", r"L293", r"L298", r"A4988", r"TMC\d{4}",
                      r"TB6\d{3}", r"ULN2\d", r"IR21\d", r"IRS\d",
                      r"BTS7\d", r"VNH\d"]),
    # --- MOSFETs (comprehensive) ---
    ("mosfet", [r"AO3\d{3}", r"AO\d{4}", r"AOD\d", r"AON\d", r"AOB\d",
                r"IRF\d", r"IRL\w*\d", r"IRFP?\d", r"IRFB?\d",
                r"BSS\d", r"BSS138", r"BSH\d", r"BSO\d",
                r"2N7000", r"2N7002",
                r"SI\d{4}", r"SIS?\d{3}", r"SIA\d", r"SIR\d",
                r"2SK\d", r"2SJ\d",
                r"FQP\d", r"FQ[DP]\d", r"FD[SN]\d",
                r"DMN\d", r"DMP\d", r"DMG\d", r"DMC\d",
                r"NTR\d", r"NTS\d", r"NTD\d", r"NTMS\d", r"NVT\d",
                r"CJ\d{4}", r"CSD\d",
                r"PSMN\d", r"PMV\d", r"PHP\d", r"PHD\d",
                r"STP\d{1,2}N", r"STD\d", r"STB\d",
                r"IPD\d", r"IPB\d", r"IPA\d", r"IPP\d",
                r"TSM\d", r"TPN\d", r"TPH\d",
                r"NCE\d", r"RU\d{2,3}", r"WPM\d", r"AP\d{4}G",
                r"EPC\d", r"ZXMN\d", r"ZXMP\d"]),
    # --- transistors ---
    ("transistor", [r"2N\d", r"BC[0-9]", r"2SC\d", r"2SA\d", r"MMBT", r"S8050",
                    r"S8550", r"BD\d", r"TIP\d", r"BCP\d", r"BCX\d", r"BSR\d",
                    r"FMMT\d", r"KST\d", r"PMBT\d", r"PBSS\d", r"NSS\d",
                    r"MJE\d", r"MJ\d{4}", r"ZTX\d"]),
    # --- voltage regulators ---
    ("voltage regulator", [r"LM78\d", r"LM79\d", r"LM317", r"LM337", r"LM1117",
                           r"AMS1117", r"LD1117", r"MIC5\d", r"MCP170\d", r"TPS\d",
                           r"LP29\d", r"XC6206", r"HT75\d", r"AOZ\d", r"RT9\d{3}",
                           r"ME6211", r"SY8\d{3}", r"AP21\d", r"AP73\d",
                           r"NCP\d{3}", r"LT30\d", r"LT1\d{3}", r"MP\d{4}",
                           r"TLV\d{3,4}", r"SPX\d", r"TC1\d{3}", r"MIC29\d"]),
    ("voltage reference", [r"TL431", r"LM4040", r"LM336", r"LM385", r"REF\d{2}",
                           r"ADR\d{3}", r"LT1009", r"MAX60\d", r"MCP1\d{3}R"]),
    ("optocoupler", [r"PC817", r"PC8\d", r"EL817", r"6N13\d", r"TLP\d", r"LTV\d",
                     r"FOD\d", r"HCPL\d", r"SFH\d", r"CNY\d", r"4N\d{2}"]),
    ("diode", [r"1N4\d", r"1N5\d", r"BAT\d", r"BAV\d", r"SS1\d", r"SS3\d", r"US1\w",
               r"SMBJ\d", r"SMAJ\d", r"PESD\d", r"TVS\d", r"BZX\d", r"BZT\d",
               r"MBR\d", r"SB\d{3}", r"SK\d{2}", r"ES\d[A-Z]", r"FR\d{3}",
               r"UF\d{3}", r"RS\d[A-Z]"]),
    ("microcontroller", [r"ATMEGA", r"ATTINY", r"ATSAMD", r"ATSAM\w",
                         r"STM32", r"STM8",
                         r"ESP32", r"ESP8266",
                         r"PIC1\d", r"PIC1[268]", r"PIC24", r"PIC32",
                         r"RP2040", r"RP2350",
                         r"GD32", r"CH32", r"CH552", r"CH554",
                         r"NRF5\d", r"EFM32", r"EFR32", r"MSP430",
                         r"CY8C", r"SAMD\d", r"SAME\d"]),
    # --- generic ICs (catch-all, checked last in prefix list) ---
    ("ic", [r"NE555", r"SN74", r"74[HL][CS]", r"CD40\d",
            r"MAX232", r"MCP23\d", r"PCF8\d", r"TCA9\d",
            r"SN65\d", r"MAX3\d{2}[0-9]", r"SP3\d{3}",
            r"CD74\d", r"SN74\w", r"HEF4\d"]),
    ("crystal", [r"HC-49", r"ABM\d", r"ECS-", r"FA-\d", r"TSX-\d"]),
]


def _norm_header(h):
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def guess_category(*texts, package=None):
    """Best-effort category from a part's text. Tries descriptive keywords first
    (most reliable when present), then falls back to part-number families, then
    KiCad footprint library prefixes, and finally "uncategorized"."""
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
    if package:
        fp_cat = category_from_footprint(package)
        if fp_cat:
            return fp_cat
    return "uncategorized"


_FOOTPRINT_CATEGORIES = {
    "Resistor_SMD": "resistor", "Resistor_THT": "resistor",
    "Capacitor_SMD": "capacitor", "Capacitor_THT": "capacitor",
    "Inductor_SMD": "inductor", "Inductor_THT": "inductor",
    "Diode_SMD": "diode", "Diode_THT": "diode",
    "LED_SMD": "diode", "LED_THT": "diode",
    "Crystal": "crystal",
    "Button_Switch_SMD": "switch", "Button_Switch_THT": "switch",
    "Connector_PinHeader": "connector", "Connector_PinSocket": "connector",
    "Connector_JST": "connector",
}


def category_from_footprint(footprint):
    """Guess category from a KiCad footprint library prefix."""
    if not footprint or ":" not in footprint:
        return None
    lib = footprint.split(":")[0]
    for prefix, cat in _FOOTPRINT_CATEGORIES.items():
        if lib.startswith(prefix):
            return cat
    return None


def normalize_kicad_footprint(fp):
    """Extract a common package name from a KiCad footprint string.
    E.g. 'Resistor_SMD:R_0603_1608Metric' -> '0603'."""
    if not fp:
        return ""
    if ":" in fp:
        fp = fp.split(":", 1)[1]
    m = re.match(r"[RCL]_(\d{4})_", fp)
    if m:
        return m.group(1)
    m = re.search(
        r"\b(SOT-?\d+(?:-\d+)?|SO(?:IC)?-\d+|[TLD]?QFP-?\d+|[DQ]FN-?\d+|"
        r"BGA-?\d+|[TM]?S?SOP-?\d+|DIP-?\d+|PDIP-?\d+|TO-?\d+|SC-?\d+|"
        r"SOD-?\d+|SMA|SMB|SMC|DO-?\d+|WLCSP-?\d+|LGA-?\d+)\b",
        fp, re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()
    return fp.split("_")[0] if "_" in fp else fp


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
            part["description"], part["value"], part["part_number"],
            package=part.get("package"),
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
