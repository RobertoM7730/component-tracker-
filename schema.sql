-- Electrical Component Tracker schema. Applied by db.init_db(). Re-runnable.

CREATE TABLE IF NOT EXISTS components (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    part_number   TEXT,
    category      TEXT NOT NULL,
    value         TEXT,
    package       TEXT,
    quantity      INTEGER NOT NULL DEFAULT 0,
    min_quantity  INTEGER NOT NULL DEFAULT 0,
    location      TEXT,
    container     TEXT,             -- which physical container/bin the part lives in (free alphanumeric)
    manufacturer  TEXT,
    supplier      TEXT,
    supplier_pn   TEXT,
    unit_cost     REAL,
    mount         TEXT,              -- form factor mounting: "SMD" or "THT"
    datasheet_url TEXT,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_components_category    ON components(category);
CREATE INDEX IF NOT EXISTS idx_components_part_number ON components(part_number);

-- Electrical characteristics, one row per attribute. One-to-many because the
-- meaningful specs differ by part type. value_num is normalized to a base unit
-- (ohms, farads, henries, watts, volts, amps, %) for search and range filters.
CREATE TABLE IF NOT EXISTS component_specs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    value_text   TEXT,
    value_num    REAL,
    unit         TEXT
);

CREATE INDEX IF NOT EXISTS idx_specs_component ON component_specs(component_id);
CREATE INDEX IF NOT EXISTS idx_specs_name_num  ON component_specs(name, value_num);

-- A consumed PCB BOM. One row per "I built N boards" event, kept for history.
CREATE TABLE IF NOT EXISTS pcb_builds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    board_qty   INTEGER NOT NULL DEFAULT 1,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS build_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id      INTEGER NOT NULL REFERENCES pcb_builds(id) ON DELETE CASCADE,
    component_id  INTEGER REFERENCES components(id) ON DELETE SET NULL,
    part_number   TEXT,
    value         TEXT,
    designator    TEXT,
    qty_per_board INTEGER NOT NULL DEFAULT 1,
    qty_consumed  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_build_items_build ON build_items(build_id);
