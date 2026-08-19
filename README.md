# Electrical Component Tracker

A small self-hosted inventory app for your electronic parts. Import order BOMs
from LCSC / DigiKey to stock up, import a PCB BOM to check and consume parts for
a build, and adjust quantities live from any device.

Built to run on a Proxmox LXC container, but it runs anywhere Python does.

## What it does

- **Inventory** — add/edit/delete parts; live search; filter by category; sort.
- **Quantity steppers** — +/- on every row, saved instantly (no page reload).
- **Order BOM import** — upload a CSV/XLSX from LCSC or DigiKey. It auto-detects
  the supplier and columns, shows a preview, and either restocks matching parts
  or adds new ones with their specs filled in.
- **PCB BOM import** — upload the parts a board needs and a board count. It
  checks stock, flags shortages, then deducts the parts and records the build.
- **Low-stock view** — everything at or below its threshold, ready to reorder.
- **CSV export** — one-click backup of the whole inventory.
- **Auto-categorization** — every part is sorted into a family from its
  description, its part number, or its KiCad footprint, across ~50 part types
  (passives, discretes, ICs by purpose, and physical parts). Category names are
  normalized on the way in, so "IC", "ICs" and "Ic" are one family with one tab,
  never three.

## Categories

`categories.py` is the single source of truth: it lists every category, its
display label, its aliases, and the keyword / part-number / footprint rules used
to recognize it. To teach the app a new part type, add one entry to
`CATEGORY_DEFS` and a matching rule — the tab, the filter, the edit-form
suggestions and the importer all pick it up. Aliases are how families get merged:
anything listed as an alias is folded onto the canonical name on every write,
and old rows are folded on startup.

## Tech

Flask + SQLite (one file, `data/components.db`), server-rendered Jinja2 templates,
HTMX for the live bits, Gunicorn in production. The only third-party deps are
Flask, openpyxl (to read .xlsx BOMs), and gunicorn.

## Run it locally

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/flask --app app init-db      # creates data/components.db
./venv/bin/python app.py                # http://localhost:8000
```

## Run the tests

```bash
./venv/bin/pip install pytest
./venv/bin/python -m pytest -q
```

## Importing BOMs — supported columns

Column names don't have to match exactly; common variants are recognized:

| Field        | Recognized headers (examples)                                  |
|--------------|----------------------------------------------------------------|
| Quantity     | Quantity, Qty, Order Qty                                       |
| Mfr part #   | Manufacturer Part Number, MPN, Mfr Part #                      |
| Supplier PN  | LCSC Part Number, Customer NO., (DigiKey) Part Number, -ND code |
| Designator   | Designator, Reference, Customer Reference                      |
| Value/Desc   | Value, Description, Comment                                    |
| Package      | Package, Footprint, Case                                       |
| Unit price   | Unit Price, Price, Unit Cost                                   |

DigiKey order exports have both a "Part Number" (their order code) and a
"Manufacturer Part Number"; the importer keeps the MPN as the part identity and
stores the DigiKey code as the supplier PN.

## Deploying to Proxmox (LXC)

**Full step-by-step runbook: [`deploy/DEPLOY.md`](deploy/DEPLOY.md)** (creates the LXC, installs the systemd service, joins Tailscale, sets up nightly backups). Quick summary:

1. Create an unprivileged Debian/Ubuntu LXC (1 vCPU, 512MB-1GB RAM, a few GB disk).
2. Inside it: `apt update && apt install -y python3 python3-venv python3-pip git`
3. Put the code in `/opt/component-tracker`, create a venv, install requirements.
4. `flask --app app init-db` to create the database.
5. Run with Gunicorn: `gunicorn -b 0.0.0.0:8000 app:app`
6. Add a systemd service so it starts on boot and restarts on crash.
7. Back up `data/components.db` daily (the whole inventory is in that one file).

**Reaching it from your devices:** install Tailscale on the container and your
phone/laptop — they form a private network and nothing is exposed to the public
internet. (A public reverse proxy is possible too, but then you *must* put a
login in front of it.) See the deployment notes for the systemd unit and backup
cron job when you're ready to launch.

## Project layout

```
app.py          Flask routes (thin)
db.py           all SQLite access (parameterized queries)
bom.py          BOM parsing + supplier/column detection
schema.sql      tables
templates/      Jinja2 pages + HTMX partials
static/style.css
tests/          pytest suite + sample BOMs
data/           components.db lives here (gitignored)
```
