# -*- coding: utf-8 -*-
"""
Rebuild all HTML in one shot
============================
Regenerates, in order:
  * card_list.html     -- card list (generate_card_list.py)
  * deck_builder.html  -- deck builder (generate_deck_builder.py)
  * tactics_list.html  -- tactics (commands) list (generate_tactics_list.py)

After a data update, just run this script to refresh all pages:
    conda run -n localdb python localDB/build_all.py

It first syncs assets (full download the first time, deltas only afterwards) so the
pages work offline.
"""

import masterdata_sync
import assets_sync
import generate_card_list
import generate_deck_builder
import generate_tactics_list


def main():
    print("=== sync masterdata ===")
    masterdata_sync.sync()

    print("\n=== sync assets ===")
    data = generate_card_list.build_lookups()
    entries = generate_card_list.build_entries(*data)
    tactics_ids = {x["uniqueId"] for x in generate_tactics_list.load_tactics()}
    assets_sync.sync({e["uniqueId"] for e in entries}, tactics_ids)

    print("\n=== build card list ===")
    generate_card_list.main()
    print("\n=== build deck builder ===")
    generate_deck_builder.main()
    print("\n=== build tactics list ===")
    generate_tactics_list.main()
    print("\nAll done.")


if __name__ == "__main__":
    main()
