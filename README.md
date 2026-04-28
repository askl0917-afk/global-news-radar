# Global News Radar V36

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


# V34 notes

- Scheme A map labels use high-contrast black text on white labels.
- Scheme C map now shows company labels without clicking nodes.
- Scheme B is changed to a news-driven supply-chain layer view: only current-search companies/relations appear in the main view.
- Master database background nodes/edges are moved into a collapsed reference section so they are not mistaken for fresh supply-chain changes.


# V35 notes

V35 adds web-based candidate approval.

## New workflow

Search news -> candidates appear in 主檔候選 -> check 合併 -> click 合併勾選候選到主檔.

## Persistence

There are two modes:

1. Runtime-only update:
   - Works immediately inside the current Streamlit app runtime.
   - May reset after reboot/redeploy.

2. Permanent GitHub sync:
   Add these Streamlit Secrets:
   ```toml
   GITHUB_TOKEN = "your_github_token"
   GITHUB_REPO = "askl0917-afk/global-news-radar"
   GITHUB_BRANCH = "main"
   ```

When GitHub sync is configured, approved candidates are committed directly to `supply_chain_master.csv`.


# V36 notes

V36 adds a live supply-chain verification workflow.

## New behavior

- Extract candidate relationships from the current search result.
- Generate targeted verification queries such as `Nvidia SK hynix HBM supplier`.
- Search public RSS/news sources in real time.
- Show a verification evidence table with confidence labels.
- Does not write the verification result into the master file automatically.

## Why

This avoids over-maintaining a large supply-chain database. The master file becomes a small background guide, while live public evidence becomes the validation layer.

## Notes

- Verification is based on public news/RSS, not paid full-text sources.
- High-confidence evidence should still be clicked and checked manually before making investment conclusions.
- GitHub token/master update functions can remain as backup, but the recommended workflow is live verification first.
