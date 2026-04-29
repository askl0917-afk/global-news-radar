# Global News Radar V43

V43 fixes the product-structure discovery failure mode.

## What changed

- Adds rule-based extraction before Groq:
  - detects `佔比/占比/比重`
  - detects `%` and `x成`
  - detects product phrases from title patterns such as `(BOPP)` and `Industry/Market`
  - detects market-focus clues such as 季增 / 年增 / 成長 / 需求 / 供應 / 報價 / 合作
- Groq is now only an enhancement layer.
- If Groq returns broken JSON, the app keeps rule extraction results instead of showing zero.
- Second-stage news queries are generated from extracted segments/products when available.
- The UI now shows that rule fallback is active when Groq fails.

## Upload files

Upload:
- app.py
- requirements.txt
- README.md
- supply_chain_master.csv

Then commit and reboot Streamlit.
