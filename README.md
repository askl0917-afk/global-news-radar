# Global News Radar V33

V33 adds supply-chain master candidate growth and Delta Radar.

## What changed

- Adds `supply_chain_master.csv` as a lightweight seed supply-chain database.
- Each search records a compact snapshot.
- Adds Delta Radar to compare this search vs prior search.
- Adds candidate queue:
  - new_company candidates
  - new_relation candidates
- The official master is not automatically modified.
- Candidate queue is local at `.radar_candidates/supply_chain_candidates.csv`.
- Download the candidate CSV, review it, then manually merge high-quality rows into `supply_chain_master.csv`.

## Upload files

Upload all four files:

```text
app.py
requirements.txt
README.md
supply_chain_master.csv
```

## Recommended Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL_LIGHT = "llama-3.1-8b-instant"
GROQ_MODEL_HEAVY = "llama-3.3-70b-versatile"
```
