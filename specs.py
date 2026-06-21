"""Extract electrical characteristics (specs) from a part's text.

Different part types have different meaningful specs, so each category declares
which ones to look for. Every parser returns a display string plus the value
normalized to a base unit (ohms, farads, henries, watts, volts, amps, %), so
specs can be searched now and range-filtered later. Parsers tolerate
engineering shorthand ("4k7", "1k0", "100n"), unit suffixes ("10kΩ"), and
fraction wattages ("1/4W").
"""

import re

SPECS_BY_CATEGORY = {
    "resistor":   [("resistance", "Ω"), ("wattage", "W"), ("tolerance", "%")],
    "capacitor":  [("capacitance", "F"), ("voltage", "V"), ("tolerance", "%")],
    "inductor":   [("inductance", "H"), ("current", "A"), ("tolerance", "%")],
    "diode":      [("voltage", "V"), ("current", "A")],
    "transistor": [("voltage", "V"), ("current", "A")],
    "mosfet":     [("voltage", "V"), ("current", "A")],
    "voltage regulator": [("voltage", "V"), ("current", "A")],
    "voltage reference": [("voltage", "V"), ("tolerance", "%")],
    "optocoupler": [("voltage", "V"), ("current", "A")],
    "microcontroller": [("voltage", "V"), ("frequency", "Hz")],
    "fuse":       [("current", "A"), ("voltage", "V")],
    "crystal":    [("frequency", "Hz")],
}

ALL_SPEC_NAMES = ["resistance", "capacitance", "inductance", "wattage",
                  "voltage", "current", "tolerance", "frequency"]

UNIT_BY_NAME = {
    "resistance": "Ω", "capacitance": "F", "inductance": "H", "wattage": "W",
    "voltage": "V", "current": "A", "tolerance": "%", "frequency": "Hz",
}

LABEL_BY_NAME = {
    "resistance": "Resistance", "capacitance": "Capacitance",
    "inductance": "Inductance", "wattage": "Wattage / power",
    "voltage": "Voltage rating", "current": "Current rating",
    "tolerance": "Tolerance", "frequency": "Frequency",
}

SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
      "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}


def _fmt(num, unit):
    if num is None:
        return None
    prefixes = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""),
                (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")]
    for factor, pre in prefixes:
        if abs(num) >= factor or factor == 1e-12:
            v = num / factor
            s = (f"{v:.2f}".rstrip("0").rstrip(".")) if v % 1 else f"{int(v)}"
            return f"{s}{pre}{unit}"
    return f"{num}{unit}"


def _rkm(blob, letters, base_unit):
    pat = r"\b(\d+)([" + letters + r"])(\d+)\b"
    m = re.search(pat, blob)
    if not m:
        return None
    mult = SI.get(m.group(2), 1) if m.group(2) not in "Rr" else 1
    whole, frac = m.group(1), m.group(3)
    num = (float(whole) + float(frac) / (10 ** len(frac))) * mult
    return _fmt(num, base_unit), num


def _suffixed(blob, unit_words, multiplier_letters, base_unit):
    units = "|".join(re.escape(u) for u in unit_words)
    mult = "[" + multiplier_letters + "]?" if multiplier_letters else ""
    pat = r"(\d+(?:\.\d+)?)\s*(" + mult + r")\s*(?:" + units + r")\b"
    m = re.search(pat, blob, re.IGNORECASE)
    if not m:
        return None
    num = float(m.group(1)) * SI.get(m.group(2), 1)
    return _fmt(num, base_unit), num


def parse_resistance(blob):
    return (_rkm(blob, "RrkKM", "Ω")
            or _suffixed(blob, ["Ω", "ohms", "ohm", "R"], "kKMm", "Ω"))


def parse_capacitance(blob):
    return (_rkm(blob, "pnuµμmF", "F")
            or _suffixed(blob, ["F", "farad", "farads"], "pnuµμmkM", "F"))


def parse_inductance(blob):
    return _suffixed(blob, ["H", "henry", "henries"], "pnuµμmk", "H")


def parse_frequency(blob):
    return _suffixed(blob, ["Hz", "hz"], "kKMG", "Hz")


def parse_wattage(blob):
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*W\b", blob, re.IGNORECASE)
    if m:
        num = float(m.group(1)) / float(m.group(2))
        return _fmt(num, "W"), num
    return _suffixed(blob, ["W", "watt", "watts"], "mk", "W")


def parse_voltage(blob):
    return _suffixed(blob, ["V", "volts", "volt", "VDC", "Vdc"], "mk", "V")


def parse_current(blob):
    return _suffixed(blob, ["A", "amps", "amp"], "munµμ", "A")


def parse_tolerance(blob):
    m = re.search(r"±?\s*(\d+(?:\.\d+)?)\s*%", blob)
    if m:
        num = float(m.group(1))
        return f"±{m.group(1)}%", num
    return None


PARSERS = {
    "resistance": parse_resistance,
    "capacitance": parse_capacitance,
    "inductance": parse_inductance,
    "frequency": parse_frequency,
    "wattage": parse_wattage,
    "voltage": parse_voltage,
    "current": parse_current,
    "tolerance": parse_tolerance,
}

_SMD_HINTS = ["smd", "smt", "0201", "0402", "0603", "0805", "1206", "1210",
              "2010", "2512", "sot", "soic", "sod", "qfn", "qfp", "tqfp",
              "bga", "dfn", "tssop", "msop", "lga", "wlcsp", "chip"]
_THT_HINTS = ["tht", "through", "thru", "dip", "to-92", "to92", "to-220",
              "to220", "radial", "axial", "pdip", "sip", "2.54mm", "2.54"]


def guess_mount(package, description=""):
    blob = f"{package or ''} {description or ''}".lower()
    for h in _THT_HINTS:
        if h in blob:
            return "THT"
    for h in _SMD_HINTS:
        if h in blob:
            return "SMD"
    return ""


def extract_specs(category, value="", description="", package=""):
    """Return a list of spec dicts {name, value_text, value_num, unit} for the
    category from its text. Falls back to a generic set if category unknown."""
    blob = " ".join(t for t in (value, description) if t)
    wanted = SPECS_BY_CATEGORY.get(category)
    if wanted is None:
        wanted = [("voltage", "V"), ("current", "A")]
    specs = []
    for name, unit in wanted:
        parsed = PARSERS[name](blob)
        if parsed:
            text, num = parsed
            specs.append({"name": name, "value_text": text,
                          "value_num": num, "unit": unit})
    return specs


def specs_for_category(category):
    return [n for n, _ in SPECS_BY_CATEGORY.get(category, [("voltage", "V"),
                                                            ("current", "A")])]
