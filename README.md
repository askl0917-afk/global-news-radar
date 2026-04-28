# Global News Radar V36

V36 adds a real-time supply-chain verification tab.

## What changed

- Adds `即時驗證` tab.
- Extracts relationship candidates from the current news result.
- Uses free public Google News RSS queries to find supply-chain evidence.
- Shows verification status, trend signal, source title, domain, and URL.
- Keeps `supply_chain_master.csv` as a lightweight background file, not a giant database.

## Upload files

Upload these files to GitHub:

- app.py
- requirements.txt
- README.md
- supply_chain_master.csv

Then commit and reboot the Streamlit app.
