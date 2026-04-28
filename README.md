# Global News Radar V37

V37 fixes the A/B/C supply-chain views and makes verification automatic.

## What changed

- Scheme A: company names are high-contrast black text on white labels.
- Scheme B: now uses news-driven companies and relationships only; master background no longer dominates the view.
- Scheme C: company labels are always visible on the map, not only on hover/click.
- Real-time supply-chain verification runs automatically after search.
- Verification results are merged into A/B/C relation tables and map lines.
- The `即時驗證` tab remains for reviewing or manually re-running verification.

## Upload files

Upload:

- app.py
- requirements.txt
- README.md
- supply_chain_master.csv

Then commit and reboot Streamlit.
