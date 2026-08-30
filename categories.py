"""One place that decides what a category is called.

Before this module, a category name could arrive from four places — the offline
BOM rules, the online Mouser lookup, the import preview form, and whatever the
user typed on the edit page — and each could spell the same family differently.
That is how the inventory ended up with both an "ICs" tab and an "Ic" tab. Every
write now runs through :func:`normalize`, which folds case, punctuation, plurals
and synonyms ("IC", "ICs", "integrated circuit", "chip") onto ONE canonical
name, and every screen renders it through :func:`label`, so a family can only
ever appear once.

Adding a family: append one entry to ``CATEGORY_DEFS``. Give it a canonical
lowercase name, a display label, and every alias you can think of — an alias
costs nothing and buys a merge that would otherwise become a duplicate tab. If
the family should always have a tab (even when empty) also list it in
``PRIMARY``; otherwise its tab appears by itself as soon as a part lands there.
"""

import re

UNCATEGORIZED = "uncategorized"

# (canonical name, display label, aliases)
CATEGORY_DEFS = [
    # --- passives ---------------------------------------------------------- #
    ("resistor", "Resistors", [
        "res", "chip resistor", "smd resistor", "fixed resistor", "shunt",
        "shunt resistor", "current sense resistor", "resistor network",
        "resistor array", "trimmer resistor", "power resistor",
    ]),
    ("potentiometer", "Potentiometers", [
        "pot", "trimpot", "trim pot", "trimmer", "rheostat",
        "variable resistor", "rotary encoder", "encoder",
    ]),
    ("capacitor", "Capacitors", [
        "cap", "mlcc", "ceramic capacitor", "electrolytic",
        "electrolytic capacitor", "tantalum", "tantalum capacitor",
        "film capacitor", "supercapacitor", "supercap",
    ]),
    ("inductor", "Inductors", [
        "coil", "choke", "ferrite", "ferrite bead", "bead",
        "common mode choke", "emi filter", "power inductor",
    ]),
    ("transformer", "Transformers", [
        "balun", "isolation transformer", "flyback transformer",
    ]),
    ("crystal", "Crystals", [
        "xtal", "quartz", "quartz crystal", "resonator", "ceramic resonator",
        "oscillator", "tcxo", "vcxo", "mems oscillator", "clock oscillator",
    ]),
    ("varistor", "Varistors", ["mov", "metal oxide varistor", "surge suppressor"]),

    # --- discrete semiconductors ------------------------------------------- #
    ("diode", "Diodes", [
        "led", "light emitting diode", "zener", "zener diode", "schottky",
        "schottky diode", "rectifier", "bridge rectifier", "tvs", "tvs diode",
        "esd", "esd protection", "photodiode", "varactor", "diode array",
    ]),
    ("transistor", "Transistors", [
        "bjt", "npn", "pnp", "igbt", "darlington", "jfet",
        "bipolar transistor", "digital transistor", "transistor array",
    ]),
    ("mosfet", "MOSFETs", [
        "fet", "nmos", "pmos", "n-channel mosfet", "p-channel mosfet",
        "power mosfet", "gan fet", "sic mosfet",
    ]),
    ("thyristor", "Thyristors", [
        "scr", "triac", "diac", "silicon controlled rectifier",
    ]),

    # --- integrated circuits, by purpose ----------------------------------- #
    ("ic", "ICs", [
        "integrated circuit", "chip", "u", "misc ic", "analog ic",
        "mixed signal",
    ]),
    ("logic", "Logic ICs", [
        "logic ic", "logic gate", "gate", "flip flop", "flip-flop",
        "shift register", "counter", "buffer", "inverter", "level shifter",
        "level translator", "decoder", "latch",
    ]),
    ("op-amp", "Op-Amps", [
        "opamp", "op amp", "operational amplifier", "instrumentation amplifier",
        "instrumentation amp", "current sense amplifier", "difference amplifier",
        "transimpedance amplifier",
    ]),
    ("comparator", "Comparators", ["window comparator"]),
    ("timer", "Timers", ["timer ic", "watchdog", "watchdog timer", "555"]),
    ("voltage regulator", "Voltage Regulators", [
        "regulator", "ldo", "linear regulator", "switching regulator",
        "buck converter", "boost converter", "buck-boost", "dc-dc converter",
        "dcdc", "pmic", "power management", "charge pump", "battery charger",
        "load switch", "power supply",
    ]),
    ("voltage reference", "Voltage References", [
        "vref", "shunt reference", "precision reference",
    ]),
    ("optocoupler", "Optocouplers", [
        "optoisolator", "opto-isolator", "opto isolator", "photocoupler",
        "digital isolator", "isolator", "solid state relay",
    ]),
    ("adc", "ADCs", [
        "a/d converter", "analog to digital converter",
        "analog-to-digital converter",
    ]),
    ("dac", "DACs", [
        "d/a converter", "digital to analog converter",
        "digital-to-analog converter",
    ]),
    ("microcontroller", "Microcontrollers", [
        "mcu", "micro controller", "soc", "system on chip", "microprocessor",
        "cpu", "processor",
    ]),
    ("fpga", "FPGAs", ["cpld", "programmable logic"]),
    ("memory", "Memory", [
        "eeprom", "flash", "sram", "dram", "sdram", "fram", "nvram",
        "nor flash", "nand flash", "serial flash", "memory ic", "sd card",
    ]),
    ("sensor", "Sensors", [
        "thermistor", "ntc", "ptc thermistor", "accelerometer", "gyroscope",
        "imu", "magnetometer", "barometer", "humidity sensor",
        "temperature sensor", "pressure sensor", "hall effect sensor",
        "proximity sensor", "light sensor", "gas sensor", "current sensor",
        "phototransistor", "photoresistor", "ldr", "load cell",
    ]),
    ("rtc", "RTCs", ["real time clock", "real-time clock"]),
    ("interface", "Interface ICs", [
        "interface ic", "transceiver", "rs485", "rs-485", "rs232", "rs-232",
        "can transceiver", "usb transceiver", "usb to uart", "uart bridge",
        "ethernet phy", "phy", "line driver", "i2c expander", "io expander",
        "gpio expander", "port expander",
    ]),
    ("audio amplifier", "Audio Amplifiers", [
        "audio amp", "class d amplifier", "class-d amplifier",
        "power amplifier", "headphone amplifier", "audio codec", "codec",
    ]),
    ("rf", "RF", [
        "rf ic", "rf module", "transceiver module", "lna", "rf switch",
        "mixer", "bluetooth", "wifi", "lora",
    ]),
    ("display driver", "Display Drivers", [
        "lcd driver", "oled driver", "segment driver", "display controller",
    ]),
    ("analog switch", "Analog Switches", [
        "mux", "multiplexer", "demultiplexer", "analog mux",
        "analog multiplexer", "crosspoint switch",
    ]),
    ("led driver", "LED Drivers", [
        "led controller", "backlight driver", "constant current driver",
        "addressable led",
    ]),
    ("motor driver", "Motor Drivers", [
        "h-bridge", "h bridge", "hbridge", "half bridge", "stepper driver",
        "bldc driver", "brushless driver", "gate driver", "servo driver",
    ]),

    # --- electromechanical and everything physical ------------------------- #
    ("connector", "Connectors", [
        "header", "pin header", "socket", "receptacle", "jack", "plug",
        "terminal block", "screw terminal", "jst", "usb connector",
        "ribbon connector", "fpc connector", "ffc connector", "card slot",
        "banana jack", "barrel jack", "dc jack",
    ]),
    ("switch", "Switches", [
        "button", "push button", "pushbutton", "tactile switch", "tact switch",
        "slide switch", "toggle switch", "dip switch", "rocker switch",
        "rotary switch", "key switch", "limit switch", "reed switch",
    ]),
    ("relay", "Relays", ["electromechanical relay", "reed relay", "contactor"]),
    ("fuse", "Fuses", [
        "polyfuse", "resettable fuse", "ptc fuse", "fuse holder",
        "circuit breaker",
    ]),
    ("battery", "Batteries", [
        "cell", "coin cell", "battery holder", "cell holder", "lipo",
        "li-ion", "18650", "cr2032",
    ]),
    ("buzzer", "Buzzers", [
        "speaker", "piezo", "piezo buzzer", "sounder", "transducer",
        "microphone", "mic", "audio transducer",
    ]),
    ("motor", "Motors", [
        "servo", "servo motor", "stepper", "stepper motor", "dc motor",
        "brushless motor", "vibration motor", "fan", "solenoid",
    ]),
    ("display", "Displays", [
        "lcd", "oled", "tft", "e-ink", "epaper", "seven segment", "7 segment",
        "led matrix", "dot matrix", "screen",
    ]),
    ("antenna", "Antennas", ["chip antenna", "pcb antenna", "whip antenna"]),
    ("module", "Modules", [
        "breakout", "breakout board", "dev board", "development board",
        "daughterboard", "shield", "hat", "camera module",
    ]),
    ("heatsink", "Heatsinks", [
        "heat sink", "thermal pad", "thermal interface", "cooling",
    ]),
    ("hardware", "Hardware", [
        "mechanical", "screw", "nut", "washer", "standoff", "spacer",
        "bracket", "clip", "fastener",
    ]),
    ("test point", "Test Points", [
        "testpoint", "test pad", "probe point", "jumper", "shunt jumper",
    ]),
    ("cable", "Cables", ["wire", "ribbon cable", "harness", "jumper wire"]),
    ("pcb", "PCBs", ["printed circuit board", "board", "perfboard", "protoboard"]),
    ("enclosure", "Enclosures", ["case", "housing", "box", "chassis", "panel"]),
]

# Families that always get a tab, even at zero stock, so the core of the
# inventory stays put. Everything else earns a tab by having parts in it.
PRIMARY = [
    "resistor", "capacitor", "inductor", "diode", "transistor",
    "ic", "connector", "crystal", "switch",
]

ALL = [name for name, _label, _aliases in CATEGORY_DEFS]
_LABELS = {name: label_ for name, label_, _aliases in CATEGORY_DEFS}
_ORDER = {name: i for i, name in enumerate(ALL)}

# Spellings that all mean "we don't know what this is".
_UNKNOWN_KEYS = {"uncategorized", "uncategorised", "uncat", "unknown",
                 "other", "misc", "miscellaneous", "none", "na"}


def _key(text):
    """Fold a name to a comparison key: lowercase, letters and digits only, so
    "Op-Amp", "op amp" and "OPAMP" all become "opamp"."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


_BY_KEY = {}
for _name, _label, _aliases in CATEGORY_DEFS:
    for _text in [_name, _label] + list(_aliases):
        _BY_KEY.setdefault(_key(_text), _name)


def normalize(raw):
    """Fold any spelling of a category onto its canonical name.

    An unknown name is kept (the user may track something we've never heard of)
    but tidied to lowercase single-spaced text, so "Power Stuff" and
    "power  stuff" can't become two tabs either. Blank -> "uncategorized"."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return UNCATEGORIZED
    key = _key(text)
    if key in _UNKNOWN_KEYS:
        return UNCATEGORIZED
    if key in _BY_KEY:
        return _BY_KEY[key]
    # A plural of something we know: "resistors" -> "resistor", "ICs" -> "ic".
    if key.endswith("es") and key[:-2] in _BY_KEY:
        return _BY_KEY[key[:-2]]
    if key.endswith("s") and key[:-1] in _BY_KEY:
        return _BY_KEY[key[:-1]]
    return text.lower()


def label(category):
    """Display name for a category — canonical ones keep their proper casing
    ("ic" -> "ICs"), anything else is title-cased as before."""
    name = normalize(category)
    if name == UNCATEGORIZED:
        return "Uncategorized"
    return _LABELS.get(name) or name.title()


def sort_key(category):
    """Order tabs the way CATEGORY_DEFS lists them (passives, discretes, ICs,
    then physical parts), with unknown categories alphabetically at the end."""
    name = normalize(category)
    return (_ORDER.get(name, len(ALL)), name)


# ---------------------------------------------------------------------------- #
# Recognition: text -> category
# ---------------------------------------------------------------------------- #
# Checked top to bottom, FIRST match wins, so order matters: the specific
# purposes sit above the broad families, and any rule that could be swallowed by
# a broader one goes first ("LED driver" before "LED", "motor driver" before
# "motor", "display driver" before "display"). To teach the app a new part type,
# add a rule here and a matching entry in CATEGORY_DEFS — nothing else changes;
# a category with stock automatically gets its own tab.
CATEGORY_RULES = [
    # --- power ------------------------------------------------------------- #
    ("voltage regulator", [r"\bvoltage regulator", r"\bregulator\b", r"\bLDO\b",
                           r"\bbuck\b", r"\bboost\b", r"\bbuck-?boost\b",
                           r"\bdc[-/ ]?dc\b", r"\bswitching reg", r"\blinear reg",
                           r"\bpmic\b", r"\bpower management", r"\bcharge pump",
                           r"\bbattery charger", r"\bcharger ic", r"\bload switch",
                           r"\be-?fuse\b", r"\bpower module", r"\bstep[- ]?down",
                           r"\bstep[- ]?up"]),
    ("voltage reference", [r"\bvoltage reference", r"\bvref\b",
                           r"\bshunt reference", r"\bprecision reference",
                           r"\bbandgap reference"]),
    # --- isolation --------------------------------------------------------- #
    ("optocoupler", [r"\boptocoupler", r"\bopto-?isolator", r"\boptoisolator",
                     r"\bphotocoupler", r"\bdigital isolator",
                     r"\bsolid[- ]state relay", r"\bssr\b", r"\bopto\b"]),
    # --- signal chain ------------------------------------------------------ #
    ("dac", [r"\bdac\b", r"\bdigital.to.analog", r"\bd/?a converter",
             r"\baudio dac\b"]),
    ("adc", [r"\badc\b", r"\banalog.to.digital", r"\ba/?d converter",
             r"\bsigma.delta", r"\bdelta.sigma"]),
    ("op-amp", [r"\bop-?amp", r"\boperational amplifier", r"\binstrumentation amp",
                r"\bdifferential amp", r"\brail.to.rail", r"\bcmos amp",
                r"\btransimpedance", r"\bcurrent sense amp"]),
    ("comparator", [r"\bcomparator", r"\bwindow detector"]),
    ("audio amplifier", [r"\baudio amp", r"\bclass[- ]?d amp", r"\bclass[- ]?ab amp",
                         r"\bheadphone amp", r"\bspeaker amp", r"\baudio codec",
                         r"\bcodec\b", r"\bi2s amp"]),
    ("analog switch", [r"\banalog switch", r"\bmultiplexer\b", r"\bmux\b",
                       r"\bdemultiplexer", r"\bcrosspoint", r"\bbus switch"]),
    # --- digital ----------------------------------------------------------- #
    ("microcontroller", [r"\bmicro ?controller", r"\bmcu\b", r"\bsoc\b",
                         r"\bsystem on chip", r"\bmicroprocessor",
                         r"\bapplication processor"]),
    ("fpga", [r"\bfpga\b", r"\bcpld\b", r"\bprogrammable logic",
              r"\bgate array\b"]),
    ("memory", [r"\beeprom\b", r"\bflash\b(?!.*light)", r"\bsram\b", r"\bdram\b",
                r"\bsdram\b", r"\bfram\b", r"\bnvram\b", r"\bnand\b",
                r"\bnor flash", r"\bserial flash", r"\bmemory\b",
                r"\bsd card\b", r"\bmicrosd\b"]),
    ("rtc", [r"\breal.?time clock", r"\brtc\b"]),
    ("interface", [r"\btransceiver", r"\brs-?485\b", r"\brs-?232\b",
                   r"\brs-?422\b", r"\bcan bus\b", r"\bcan fd\b",
                   r"\busb.to.(uart|serial|ttl)", r"\buart bridge",
                   r"\bethernet phy", r"\bi/?o expander", r"\bgpio expander",
                   r"\bport expander", r"\blevel shift", r"\blevel translat",
                   r"\bline driver", r"\bisolated interface", r"\bhub controller",
                   r"\blin transceiver"]),
    ("logic", [r"\blogic gate", r"\bshift register", r"\bflip.?flop",
               r"\bnand gate", r"\bnor gate", r"\bxor gate", r"\band gate",
               r"\bor gate\b", r"\bschmitt trigger", r"\bhex inverter",
               r"\bdecade counter", r"\bbinary counter", r"\bd-?latch",
               r"\bbus buffer", r"\blogic ic\b", r"\b74[hl]?[cvs]?\d{2,3}\b",
               r"\bcd4\d{3}\b"]),
    # --- drivers ----------------------------------------------------------- #
    ("display driver", [r"\bdisplay driver", r"\blcd driver", r"\boled driver",
                        r"\bsegment driver", r"\bdisplay controller",
                        r"\blcd controller"]),
    ("led driver", [r"\bled driver", r"\bled controller", r"\bconstant current.*led",
                    r"\bbacklight driver", r"\baddressable led"]),
    ("motor driver", [r"\bmotor driver", r"\bmotor controller", r"\bh-?bridge",
                      r"\bhalf-?bridge", r"\bstepper driver", r"\bbrushless driver",
                      r"\bbldc driver", r"\bgate driver", r"\bservo driver"]),
    ("timer", [r"\btimer ic\b", r"\bwatchdog", r"\b555 timer", r"\bprogrammable timer",
               r"\bmonostable", r"\bastable"]),
    # --- discretes --------------------------------------------------------- #
    ("mosfet", [r"\bmosfet", r"\bn-?channel\b", r"\bp-?channel\b",
                r"\bnmos\b", r"\bpmos\b", r"\benhancement mode",
                r"\bpower fet\b", r"\bVds\b", r"\bRds", r"\bsignal fet",
                r"\bgan fet\b", r"\bsic mosfet"]),
    ("thyristor", [r"\bthyristor", r"\btriac\b", r"\bdiac\b", r"\bscr\b",
                   r"\bsilicon controlled rect"]),
    # --- sensing ----------------------------------------------------------- #
    ("sensor", [r"\bsensor\b", r"\bthermistor\b", r"\bntc\b", r"\baccelerometer\b",
                r"\bgyroscope\b", r"\bbarometer\b", r"\bhumidity\b",
                r"\btemperature sensor", r"\bIMU\b", r"\bproximity\b",
                r"\bhall effect\b", r"\bcurrent sense\b", r"\bphotodiode\b",
                r"\bphototransistor\b", r"\bphotoresistor\b", r"\bldr\b",
                r"\bload cell\b", r"\bmagnetometer\b", r"\bpressure sensor",
                r"\btime of flight", r"\bambient light", r"\bgas sensor",
                r"\bthermocouple\b", r"\bencoder wheel"]),
    # --- RF ---------------------------------------------------------------- #
    ("rf", [r"\brf\b", r"\bbluetooth\b", r"\bble\b", r"\bwi-?fi\b", r"\bzigbee\b",
            r"\blora\b", r"\bnrf24\b", r"\bsub-?ghz\b", r"\bmixer ic\b",
            r"\blow noise amp", r"\blna\b", r"\bsaw filter"]),
    ("antenna", [r"\bantenna\b", r"\bchip antenna", r"\bwhip antenna"]),
    # --- broad families ----------------------------------------------------- #
    ("potentiometer", [r"\bpotentiometer", r"\btrimpot", r"\btrimmer\b",
                       r"\bvariable resistor", r"\brheostat",
                       r"\brotary encoder"]),
    ("resistor", [r"\bresistor", r"\bres\b", r"\d+\s*k?ohm", r"\d+\s*k?Ω",
                  r"\bRC\d{3,4}", r"\bshunt resistor", r"\bresistor (network|array)"]),
    ("capacitor", [r"\bcapacitor", r"\bcap\b", r"\d+\s*[pnuµ]f\b", r"mlcc",
                   r"tantalum", r"\bsupercap", r"\belectrolytic\b"]),
    ("inductor", [r"\binductor", r"\bferrite", r"\d+\s*[pnuµm]h\b", r"\bbead\b",
                  r"\bchoke\b", r"\bcommon mode\b"]),
    ("transformer", [r"\btransformer", r"\bbalun\b"]),
    ("varistor", [r"\bvaristor", r"\bmov\b", r"\bmetal oxide varistor"]),
    ("diode", [r"\bdiode", r"\bzener", r"\bschottky", r"\bled\b", r"\brectifier",
               r"\btvs\b", r"\besd\b", r"\bvaractor\b",
               r"\blight[- ]emitting diode"]),
    ("transistor", [r"\btransistor", r"\bbjt\b", r"\bnpn\b", r"\bpnp\b",
                    r"\bigbt", r"\bjfet", r"\bdarlington"]),
    ("ic", [r"\bic\b", r"\bamplifier", r"\blogic\b", r"\bdriver\b",
            r"\bmultivibrator\b", r"\bintegrated circuit", r"\buart\b",
            r"\bspi\b", r"\bi2c\b"]),
    # --- physical parts ------------------------------------------------------ #
    ("relay", [r"\brelay\b", r"\bcontactor\b"]),
    ("connector", [r"\bconnector", r"\bheader", r"\bsocket", r"\bjack\b",
                   r"\bterminal", r"\busb\b", r"\bjst\b", r"\breceptacle",
                   r"\bplug\b", r"\bfpc\b", r"\bffc\b", r"\bcard slot",
                   r"\bmolex\b", r"\bpin strip", r"\bidc\b"]),
    ("crystal", [r"\bcrystal", r"\boscillator", r"\bresonator", r"\bMHz\b",
                 r"\bkHz\b", r"\btcxo\b", r"\bvcxo\b", r"\bxtal\b"]),
    ("switch", [r"\bswitch", r"\bbutton", r"\btactile", r"\bdip switch",
                r"\bpushbutton", r"\breed switch"]),
    ("fuse", [r"\bfuse", r"\bptc\b", r"\bpolyfuse", r"\bcircuit breaker"]),
    ("battery", [r"\bbattery", r"\bcoin cell", r"\bcell holder", r"\blipo\b",
                 r"\bli-?ion\b", r"\b18650\b", r"\bcr20\d{2}\b"]),
    ("buzzer", [r"\bbuzzer", r"\bpiezo", r"\bspeaker", r"\bsounder",
                r"\bmicrophone", r"\bmems mic"]),
    ("motor", [r"\bmotor\b", r"\bservo\b", r"\bstepper\b", r"\bsolenoid\b",
               r"\bfan\b", r"\bvibration motor"]),
    ("display", [r"\bdisplay\b", r"\blcd\b", r"\boled\b", r"\btft\b",
                 r"\be-?ink\b", r"\bepaper\b", r"\bseven segment",
                 r"\b7[- ]segment", r"\bled matrix", r"\bdot matrix"]),
    ("module", [r"\bmodule\b", r"\bbreakout", r"\bdev(elopment)? board",
                r"\bdaughter ?board", r"\bshield\b"]),
    ("heatsink", [r"\bheat ?sink", r"\bthermal pad", r"\bthermal interface"]),
    ("cable", [r"\bcable\b", r"\bwire\b", r"\bharness\b", r"\bjumper wire"]),
    ("test point", [r"\btest ?point", r"\btest pad", r"\bprobe point",
                    r"\bjumper\b"]),
    ("pcb", [r"\bpcb\b", r"\bprinted circuit", r"\bperfboard", r"\bprotoboard",
             r"\bstripboard"]),
    ("enclosure", [r"\benclosure", r"\bhousing\b", r"\bchassis\b",
                   r"\bproject box"]),
    ("hardware", [r"\bstandoff", r"\bspacer\b", r"\bscrew\b", r"\bnut\b",
                  r"\bwasher\b", r"\bbracket\b", r"\bfastener", r"\bhex bolt"]),
]

# Fallback when the description text matches nothing: many parts arrive as a bare
# manufacturer part number ("AO3407") with no descriptive words, so we map common
# part-number families to a category. Matched with re.match (anchored at the
# start) against the UPPERCASED part number. Add families freely — a wrong guess
# here is still one click to fix, while no guess means a part nobody can find.
PART_PREFIXES = [
    # --- signal chain ------------------------------------------------------ #
    ("dac", [r"MCP47\d", r"MCP48\d", r"DAC8\d", r"DAC7\d", r"AD56\d", r"AD53\d",
             r"AD55\d", r"PCM5\d", r"TLC56\d", r"TLV56\d", r"MAX54\d", r"MAX55\d",
             r"DAC12\d", r"DAC08\d", r"DAC1\d{3}", r"PT8211", r"CS43\d"]),
    ("adc", [r"ADS1\d{3}", r"ADS8\d", r"MCP3\d{3}", r"MCP3\d{2}[0-9]",
             r"AD7\d{3}", r"AD9\d{3}", r"MAX1\d{3}", r"MAX1\d{2}[0-9]",
             r"ADS7\d", r"HX711", r"NAU7802", r"CS5\d{3}", r"PCM18\d",
             r"LTC24\d", r"MCP342\d"]),
    ("comparator", [r"LM393", r"LM339", r"LM311", r"TLV3\d{3}", r"MAX9\d{3}",
                    r"TL331", r"LMV33\d", r"MCP654\d", r"NCS2\d{3}"]),
    ("op-amp", [r"OPA\d", r"OPT\d", r"MCP6\d{3}", r"MCP6\d{2}[0-9]", r"AD8\d{3}",
                r"AD8\d{2}[0-9]", r"LM358", r"LM324", r"LM741",
                r"LMV\d{3}", r"TL07\d", r"TL08\d", r"TL06\d", r"NE5532",
                r"NE5534", r"LMC\d{3}", r"TSV\d{3}", r"INA\d{3}", r"MAX4\d{3}",
                r"LT1\d{3}", r"ADA4\d", r"MCP60\d", r"TLV2\d{3}", r"TLC27\d"]),
    ("audio amplifier", [r"PAM8\d{3}", r"TPA3\d{3}", r"TPA6\d{3}", r"LM386",
                         r"LM4863", r"MAX98\d{3}", r"TDA2\d{3}", r"TDA7\d{3}",
                         r"PCM510\d", r"SSM2\d{3}", r"NS4\d{3}"]),
    ("analog switch", [r"CD405\d", r"74HC405\d", r"ADG\d{3}", r"TS5A\d",
                       r"MAX46\d{2}", r"TMUX\d", r"SN74CBT", r"DG4\d{2}"]),
    # --- power ------------------------------------------------------------- #
    ("voltage regulator", [r"LM78\d", r"LM79\d", r"LM317", r"LM337", r"LM1117",
                           r"AMS1117", r"LD1117", r"MIC5\d", r"MCP170\d", r"TPS\d",
                           r"LP29\d", r"XC6206", r"XC62\d", r"HT75\d", r"AOZ\d",
                           r"RT9\d{3}", r"ME6211", r"SY8\d{3}", r"AP21\d",
                           r"AP73\d", r"NCP\d{3}", r"LT30\d", r"MP\d{4}",
                           r"TLV7\d{2}", r"TLV6\d{2}", r"SPX\d", r"TC1\d{3}",
                           r"MIC29\d", r"L78\d{2}", r"L79\d{2}", r"LM259\d",
                           r"LM2596", r"LM2577", r"XL6009", r"XL4015",
                           r"TP4056", r"TP5100", r"BQ2\d{4}", r"MCP73\d",
                           r"IP5306", r"SGM2\d{3}", r"UA78\d", r"HT78\d"]),
    ("voltage reference", [r"TL431", r"LM4040", r"LM336", r"LM385", r"REF\d{2}",
                           r"ADR\d{3}", r"LT1009", r"MAX60\d", r"MCP1\d{3}R"]),
    # --- isolation --------------------------------------------------------- #
    ("optocoupler", [r"PC817", r"PC8\d", r"EL817", r"6N13\d", r"TLP\d", r"LTV\d",
                     r"FOD\d", r"HCPL\d", r"SFH\d", r"CNY\d", r"4N\d{2}",
                     r"ISO7\d{3}", r"ADUM\d", r"SI86\d", r"MOC3\d{3}"]),
    # --- digital ----------------------------------------------------------- #
    ("microcontroller", [r"ATMEGA", r"ATTINY", r"ATSAMD", r"ATSAM\w",
                         r"STM32", r"STM8",
                         r"ESP32", r"ESP8266", r"ESP12", r"ESP07",
                         r"PIC1\d", r"PIC1[268]", r"PIC24", r"PIC32",
                         r"RP2040", r"RP2350",
                         r"GD32", r"CH32", r"CH55[0-9]",
                         r"NRF5\d", r"EFM32", r"EFR32", r"MSP430",
                         r"CY8C", r"SAMD\d", r"SAME\d", r"LPC1\d", r"LPC8\d",
                         r"RA4M", r"RA6M", r"MK[LEV]\d", r"IMXRT", r"AT32F",
                         r"HT66", r"N76E", r"STC8", r"STC15", r"BL602",
                         r"W600", r"MM32"]),
    ("fpga", [r"XC[2367]\w", r"XC9\d", r"EP[1234]C", r"EPM\d", r"10M\d{2}",
              r"ICE40", r"LCMXO", r"MACHXO", r"ATF16V8", r"ATF22V10",
              r"GW1N", r"GW2A"]),
    ("memory", [r"AT24C", r"AT25\d", r"M24\d", r"M95\d", r"W25Q", r"W25N",
                r"IS25\w", r"MX25\w", r"S25FL", r"SST25", r"SST26",
                r"GD25", r"FM24\d", r"MB85", r"IS62\w", r"IS61\w",
                r"23K\d", r"23LC", r"24LC", r"24FC", r"93C\d{2}", r"AT45DB",
                r"N25Q", r"MT25Q", r"K4[AB]\d", r"MT41\w", r"AS4C"]),
    ("rtc", [r"DS13\d{2}", r"DS32\d{2}", r"DS16\d{2}", r"PCF85\d{2}",
             r"PCF21\d{2}", r"MCP794\d", r"RV-?\d{4}", r"RX8\d{3}",
             r"M41T\d", r"BQ32\d"]),
    ("interface", [r"MAX48[5-9]", r"MAX3232", r"MAX232", r"SN65\w", r"SN75\w",
                   r"MCP2515", r"MCP2551", r"MCP2562", r"TJA10\d{2}",
                   r"ISO1050", r"CH340", r"CH341", r"CH9102", r"CP210\d",
                   r"FT23\d", r"FT2232", r"PL2303", r"LAN8\d{3}", r"ENC28J60",
                   r"W5[15]00", r"KSZ8\d{3}", r"PCF857\d", r"MCP230\d{2}",
                   r"TCA95\d{2}", r"TCA98\d{2}", r"PCA954\d", r"SP3485",
                   r"SP3232", r"TXB0\d{3}", r"TXS0\d{3}", r"LSF0\d{3}",
                   r"USB2\d{3}", r"TUSB\d"]),
    ("logic", [r"SN74", r"74[HL]?[CVS]?\d{2,3}", r"CD40\d{2}", r"CD45\d{2}",
               r"CD74\w", r"HEF4\d{3}", r"MC14\d{3}", r"MM74\w", r"DM74\w",
               r"NC7S", r"SN54\w"]),
    ("timer", [r"NE555", r"NE556", r"LM555", r"TLC555", r"ICM75\d",
               r"CD4541", r"TPL5\d{3}", r"STWD100"]),
    # --- drivers ----------------------------------------------------------- #
    ("display driver", [r"SSD1\d{3}", r"SH110\d", r"ST77\d{2}", r"ILI9\d{3}",
                        r"MAX72\d{2}", r"TM16\d{2}", r"HT16K33", r"HD44780",
                        r"PCD8544", r"UC1701", r"NT35\d{3}", r"GC9A01"]),
    ("led driver", [r"TLC59\d", r"PCA96\d", r"IS31\w", r"WS28\d", r"SK68\d",
                    r"APA10\d", r"AP33\d", r"AL8\d", r"CAT4\d", r"LM3\d{3}",
                    r"MAX7\d{3}", r"STP16\w", r"LP55\d{2}", r"HT16C\d"]),
    ("motor driver", [r"DRV8\d", r"L293", r"L298", r"A4988", r"TMC\d{4}",
                      r"TB6\d{3}", r"ULN2\d", r"IR21\d", r"IRS\d",
                      r"BTS7\d", r"VNH\d", r"MP6\d{3}", r"UCC27\d",
                      r"MCP14\d{2}", r"FAN73\d", r"AT8236", r"MX1508",
                      r"MX1919", r"L9110"]),
    # --- discretes --------------------------------------------------------- #
    ("mosfet", [r"AO3\d{3}", r"AO\d{4}", r"AOD\d", r"AON\d", r"AOB\d",
                r"IRF\d", r"IRL\w*\d", r"IRFP?\d", r"IRFB?\d",
                r"BSS\d", r"BSS138", r"BSH\d", r"BSO\d", r"BSC\d", r"BSZ\d",
                r"2N7000", r"2N7002",
                r"SI\d{4}", r"SIS?\d{3}", r"SIA\d", r"SIR\d",
                r"2SK\d", r"2SJ\d",
                r"FQP\d", r"FQ[DP]\d", r"FD[SN]\d",
                r"DMN\d", r"DMP\d", r"DMG\d", r"DMC\d",
                r"NTR\d", r"NTS\d", r"NTD\d", r"NTMS\d", r"NVT\d",
                r"CJ\d{4}", r"CSD\d",
                r"PSMN\d", r"PMV\d", r"PHP\d", r"PHD\d",
                r"STP\d{1,2}N", r"STD\d", r"STB\d", r"STL\d",
                r"IPD\d", r"IPB\d", r"IPA\d", r"IPP\d", r"IPT\d",
                r"TSM\d", r"TPN\d", r"TPH\d", r"TK\d{2}[A-Z]",
                r"NCE\d", r"RU\d{2,3}", r"WPM\d", r"AP\d{4}G",
                r"EPC\d", r"ZXMN\d", r"ZXMP\d", r"GS66\d", r"SQ\d{4}"]),
    ("transistor", [r"2N\d", r"BC[0-9]", r"2SC\d", r"2SA\d", r"MMBT", r"S8050",
                    r"S8550", r"BD\d", r"TIP\d", r"BCP\d", r"BCX\d", r"BSR\d",
                    r"FMMT\d", r"KST\d", r"PMBT\d", r"PBSS\d", r"NSS\d",
                    r"MJE\d", r"MJ\d{4}", r"ZTX\d", r"MPSA\d", r"KSP\d",
                    r"DTC\d", r"DTA\d", r"UMH\d", r"IKW\d", r"IRG\d",
                    r"FGA\d", r"STGW\d"]),
    ("thyristor", [r"BT13\d", r"BT[AB]\d{2}", r"MAC9\d", r"MAC97", r"TIC1\d{2}",
                   r"2N50\d{2}", r"BRX\d", r"Z0\d{3}", r"MCR\d{3}"]),
    ("diode", [r"1N4\d", r"1N5\d", r"1N9\d", r"BAT\d", r"BAV\d", r"BAS\d",
               r"SS1\d", r"SS3\d", r"US1\w", r"SMBJ\d", r"SMAJ\d", r"SMF\d",
               r"PESD\d", r"TVS\d", r"BZX\d", r"BZT\d", r"MMSZ\d", r"MMBD\d",
               r"MBR\d", r"SB\d{3}", r"SK\d{2}", r"ES\d[A-Z]", r"FR\d{3}",
               r"UF\d{3}", r"RS\d[A-Z]", r"STPS\d", r"DB1\d{2}", r"KBP\d",
               r"MB6S", r"GBU\d", r"SR\d{3}", r"NUP\d", r"USBLC6"]),
    # --- sensing ----------------------------------------------------------- #
    ("sensor", [r"BME\d{3}", r"BMP\d{3}", r"BNO\d{3}", r"BMI\d{3}",
                r"MPU\d{4}", r"LSM\d{3}", r"ADXL\d", r"DHT\d", r"SHT\d",
                r"ACS7\d", r"AHT\d", r"LM35", r"TMP\d{2,3}", r"DS18B",
                r"MAX3\d{3}", r"MAX6\d{3}", r"HTU\d", r"SI7\d{3}",
                r"ICM\d{5}", r"VL53", r"TSL\d", r"BH17\d", r"MLX9\d{4}",
                r"HMC58\d", r"QMC5\d{3}", r"A311\d", r"SS49\d", r"DRV5\d{3}",
                r"INA2\d{2}", r"CCS811", r"SGP\d{2}", r"MQ-?\d", r"HC-?SR\d",
                r"APDS\d{4}", r"VEML\d", r"MAX301\d", r"NTC\d"]),
    # --- RF ---------------------------------------------------------------- #
    ("rf", [r"NRF24", r"CC1101", r"CC25\d{2}", r"SX12\d{2}", r"RFM9[567]",
            r"RFM69", r"SI4[47]\d{2}", r"A7105", r"E32-\w", r"HC-?0[56]",
            r"JDY-\d", r"BK4\d{3}"]),
    # --- generic ICs (checked last: only if nothing more specific matched) -- #
    ("ic", [r"MAX3\d{2}[0-9]", r"SP3\d{3}", r"ICL\d{4}", r"ADM\d{3}"]),
    ("crystal", [r"HC-49", r"ABM\d", r"ABLS\d", r"ECS-", r"FA-\d", r"TSX-\d",
                 r"NX32\d", r"7[MB]-\d", r"SG-?8\d{3}", r"CSTCE\d"]),
    # --- physical parts ----------------------------------------------------- #
    ("potentiometer", [r"RK09\d", r"3296\w", r"3362\w", r"PTV09", r"EC11",
                       r"PT10\w", r"RV09\d", r"P160\w"]),
    ("relay", [r"SRD-?\d{2}", r"HK4100", r"G5[VQNL]-\d", r"G6[KDS]-", r"JQC-?3F",
               r"HFD2", r"HF3FF", r"OMRON G", r"TQ2-\d", r"AQY\d"]),
    ("varistor", [r"S\d{2}K\d", r"V\d{2}E\d", r"TVR\d", r"CNR\d", r"MOV\d"]),
    ("fuse", [r"0451\d", r"0603L\d", r"1206L\d", r"MF-?MSMF", r"SMD\d{3}F",
              r"F\d{3}[HL]"]),
    ("connector", [r"SM\d{2}B-", r"B\d{1,2}B-", r"S\d{1,2}B-", r"BM\d{2}B",
                   r"PH2\.0", r"XH2\.54", r"53398", r"5045\d", r"DF13",
                   r"FH12", r"USB4\d{3}", r"UJ2-", r"TYPE-?C-31",
                   r"1054\d{2}", r"22-?27-?\d{3}"]),
    ("battery", [r"CR20\d{2}", r"LIR2\d{3}", r"BH-?\d{3}", r"18650", r"BK-?\d{4}"]),
    ("buzzer", [r"CMT-?\d{4}", r"PS12\d{2}", r"MLT-?\d{4}", r"AI-?\d{4}",
                r"SPU0410", r"ICS-?4\d{3}"]),
]


# ---------------------------------------------------------------------------- #
# Recognition: KiCad footprint -> category
# ---------------------------------------------------------------------------- #
# A KiCad footprint carries its library name ("Resistor_SMD:R_0603_1608Metric"),
# which is often the only clue a schematic-exported BOM gives for a part with no
# description. Keys are matched as prefixes of the library name, longest first,
# so "Connector_JST" wins over "Connector".
FOOTPRINT_LIBS = {
    "Resistor_SMD": "resistor", "Resistor_THT": "resistor",
    "Potentiometer": "potentiometer", "Potentiometer_SMD": "potentiometer",
    "Potentiometer_THT": "potentiometer", "Rotary_Encoder": "potentiometer",
    "Capacitor_SMD": "capacitor", "Capacitor_THT": "capacitor",
    "Capacitor_Tantalum_SMD": "capacitor", "Capacitor_Aluminum": "capacitor",
    "Inductor_SMD": "inductor", "Inductor_THT": "inductor",
    "Ferrite_THT": "inductor", "Choke": "inductor",
    "Transformer_SMD": "transformer", "Transformer_THT": "transformer",
    "Varistor": "varistor",
    "Crystal": "crystal", "Oscillator": "crystal",
    "Diode_SMD": "diode", "Diode_THT": "diode", "Diode_Bridge": "diode",
    "LED_SMD": "diode", "LED_THT": "diode", "LED": "diode",
    "OptoDevice": "optocoupler",
    "Button_Switch_SMD": "switch", "Button_Switch_THT": "switch",
    "Switch": "switch",
    "Relay_SMD": "relay", "Relay_THT": "relay",
    "Fuse": "fuse",
    "Battery": "battery",
    "Buzzer_Beeper": "buzzer",
    "Motors": "motor", "Fan": "motor",
    "Display_7Segment": "display", "Display": "display",
    "RF_Antenna": "antenna",
    "RF_Module": "module", "Module": "module", "RF_Shielding": "hardware",
    "RF_GPS": "module", "RF_GSM": "module", "RF_Bluetooth": "rf",
    "Heatsink": "heatsink",
    "MountingHole": "hardware", "Mounting_Hole": "hardware",
    "Fiducial": "hardware", "NetTie": "hardware", "Symbol": "hardware",
    "TestPoint": "test point", "Jumper": "test point",
    "Wire_Pads": "cable", "Wire_Connections": "cable",
    "TerminalBlock": "connector", "Terminal_Block": "connector",
    "Connector": "connector",
    "Sensor": "sensor",
    "Converter_ACDC": "voltage regulator", "Converter_DCDC": "voltage regulator",
    "Filter": "inductor", "Valve": "hardware",
    # Generic IC bodies: the library says only "this is a chip in a SOIC/QFN/DIP
    # package", which still beats leaving the part uncategorized.
    "Package_BGA": "ic", "Package_CSP": "ic", "Package_DFN_QFN": "ic",
    "Package_DIP": "ic", "Package_LCC": "ic", "Package_LGA": "ic",
    "Package_QFP": "ic", "Package_SIP": "ic", "Package_SON": "ic",
    "Package_SO": "ic", "Package_DirectFET": "mosfet",
    "Package_TO_SOT_SMD": "transistor", "Package_TO_SOT_THT": "transistor",
}

# Bare package names (no KiCad library in front), e.g. a BOM whose Package column
# just says "SOT-23" or "R_0805". Only unambiguous shapes are listed: an "0603"
# on its own could be a resistor, a capacitor, an inductor or an LED, so it is
# deliberately absent.
_PACKAGE_PATTERNS = [
    ("resistor", r"^R[_-]?\d{4}(?:_|$)"),
    ("capacitor", r"^C[_-]?\d{4}(?:_|$)|^CP[_-]|^Tantalum"),
    ("inductor", r"^L[_-]?\d{4}(?:_|$)"),
    ("diode", r"^D[_-]|^LED[_-]|^SOD-?\d|^DO-?\d{2}|^SMA\b|^SMB\b|^SMC\b"),
    ("transistor", r"^SOT-?\d|^TO-?\d{2,3}|^SC-?\d{2}"),
    ("ic", r"^SOIC|^SO-?\d|^[TM]?SSOP|^MSOP|^[TLV]?QFP|^[DQ]FN|^BGA|^LGA|"
           r"^WLCSP|^[PC]?DIP-?\d|^SOP-?\d"),
    ("connector", r"^PinHeader|^PinSocket|^JST|^Molex|^USB[_-]"),
    ("crystal", r"^HC-?49|^Crystal"),
]


def guess_category(*texts, package=None):
    """Best-effort category for a part, always a canonical name.

    Tries descriptive keywords first (most reliable when present), then
    part-number families, then the footprint/package, and finally gives up with
    "uncategorized" rather than guessing wildly."""
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
    return UNCATEGORIZED


def category_from_footprint(footprint):
    """Guess a category from a KiCad footprint ("Resistor_SMD:R_0603_1608Metric")
    or from a bare package name ("SOT-23"). Returns None when the shape alone
    doesn't say what the part is (an 0603 could be four different things)."""
    if not footprint:
        return None
    fp = footprint.strip()
    if ":" in fp:
        lib, name = fp.split(":", 1)
        # Longest prefix first so "Connector_JST" beats "Connector".
        for prefix in sorted(FOOTPRINT_LIBS, key=len, reverse=True):
            if lib.startswith(prefix):
                return FOOTPRINT_LIBS[prefix]
    else:
        name = fp
    for cat, pattern in _PACKAGE_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return cat
    return None
