"""Parse the search box into free-text terms and structured spec conditions.

Users can mix plain text with range expressions, e.g.

    10k 0805                      -> free text only
    resistance>=1k wattage>=0.25  -> two spec conditions
    voltage>=25 SMD               -> one condition + free text "SMD"

A spec condition is (canonical_name, operator, value_in_base_units). Values may
carry an engineering suffix (k, M, n, u/µ, m, p, G) which is converted to the
base unit so it can be compared against component_specs.value_num.
"""

import re

from specs import SI

# Accepted spelling -> canonical spec name.
ALIASES = {
    "resistance": "resistance", "res": "resistance", "ohms": "resistance",
    "ohm": "resistance",
    "capacitance": "capacitance", "cap": "capacitance", "farad": "capacitance",
    "farads": "capacitance",
    "inductance": "inductance", "ind": "inductance", "henry": "inductance",
    "wattage": "wattage", "watt": "wattage", "watts": "wattage", "power": "wattage",
    "voltage": "voltage", "volt": "voltage", "volts": "voltage",
    "current": "current", "amp": "current", "amps": "current", "amperes": "current",
    "tolerance": "tolerance", "tol": "tolerance",
    "frequency": "frequency", "freq": "frequency",
}

OPS = (">=", "<=", ">", "<", "=")

# name operator number optional-suffix
_TOKEN = re.compile(
    r"([a-zA-Z]+)\s*(>=|<=|>|<|=)\s*([0-9]*\.?[0-9]+)\s*([pnuµμmkKMG]?)"
)


def _to_base(num_str, suffix):
    num = float(num_str)
    if suffix:
        num *= SI.get(suffix, 1)
    return num


def parse_query(raw):
    """Return (free_text, conditions) where conditions is a list of
    (name, op, value_base). Unrecognized 'name op value' tokens are left in the
    free text untouched."""
    if not raw:
        return "", []
    conditions = []

    def repl(m):
        name = m.group(1).lower()
        op, val, suf = m.group(2), m.group(3), m.group(4)
        canon = ALIASES.get(name)
        if canon and op in OPS:
            conditions.append((canon, "=" if op == "==" else op,
                               _to_base(val, suf)))
            return " "
        return m.group(0)

    text = _TOKEN.sub(repl, raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text, conditions
