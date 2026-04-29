# Global News Radar V42

V42 adds generic company product-structure discovery.

## Key change

The app no longer hardcodes Nan Ya's products or segment mix as the answer.

New flow:

1. Detect company / ticker.
2. Run generic company bootstrap queries:
   - annual report revenue breakdown
   - investor presentation revenue mix
   - business segments
   - product revenue mix
   - 產品別營收 / 營收比重 / 年報 / 法說
3. Send the retrieved titles / metadata to Groq.
4. Groq extracts only what appears in the evidence:
   - segments
   - products
   - revenue share if explicitly found
   - market focus
   - missing data
5. Generate second-stage news search queries from extracted evidence.

This is designed to work for any company, not only Nan Ya.

## Upload files

Upload:
- app.py
- requirements.txt
- README.md
- supply_chain_master.csv

Then commit and reboot Streamlit.
