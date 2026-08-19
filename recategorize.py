#!/usr/bin/env python3
"""One-time backfill: re-run categorization over parts already in the database.

Categorization normally happens only when a part is imported or added, so parts
saved before the smarter rules existed stay "uncategorized". This re-runs
guess_category over them and fixes the ones it can now place (e.g. an AO3407 that
was sitting uncategorized becomes "mosfet").

By default it ONLY touches rows that are currently uncategorized, so a category
you set by hand is never overwritten. Pass --all to re-evaluate every row.

Duplicate spellings of a category ("IC" vs "Ic") are a separate matter: those
are merged automatically every time the app starts, so this script only deals
with parts whose family the rules can now identify.

It is a DRY RUN unless you pass --apply, so you can see what it would do first.
When applied, it also refreshes each changed row's spec fields to match its new
category. Safe to re-run.

Run it inside the container, as the service user that owns the data:

    cd /opt/component-tracker
    sudo -u tracker ./venv/bin/python recategorize.py            # preview
    sudo -u tracker ./venv/bin/python recategorize.py --apply    # save changes
    sudo -u tracker ./venv/bin/python recategorize.py --all --apply   # re-do all
"""

import sys

import db
import bom
import specs

UNCATEGORIZED = {"", "uncategorized", None}


def main(argv):
    apply = "--apply" in argv
    do_all = "--all" in argv

    rows = db.list_components(sort="category")
    changes = []
    for r in rows:
        current = r.get("category")
        if not do_all and current not in UNCATEGORIZED:
            continue
        guess = bom.guess_category(
            r.get("notes"), r.get("value"), r.get("part_number"),
            r.get("manufacturer"),
            package=r.get("package"),
        )
        if guess == "uncategorized" or guess == current:
            continue
        changes.append((r, guess))

    if not changes:
        print("Nothing to recategorize — no parts the new rules can place.")
        return 0

    print(f"{'PART':32}{'FROM':18}-> TO")
    print("-" * 60)
    for r, guess in changes:
        ident = r.get("part_number") or r.get("value") or f"id {r['id']}"
        frm = r.get("category") or "uncategorized"
        print(f"{ident[:31]:32}{frm[:17]:18}-> {guess}")

    if not apply:
        print(f"\n{len(changes)} part(s) would change. "
              f"Re-run with --apply to save them.")
        return 0

    for r, guess in changes:
        db.update_component(r["id"], {"category": guess})
        spec_list = specs.extract_specs(guess, r.get("value"),
                                        r.get("notes"), r.get("package"))
        db.replace_specs(r["id"], spec_list)
    print(f"\nUpdated {len(changes)} part(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
