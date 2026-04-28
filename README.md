# Global News Radar V30

V30 adds freshness filtering to separate RSS push time from actual event freshness.

## Why

RSS / Google News timestamps often mean "recently pushed or aggregated",
not "the event just happened".

V30 adds an event freshness layer so the radar can classify news as:

- 真新事件
- 舊事件新包裝
- 重複推送
- 誤抓 / 垃圾訊號

## What changed

- Adds 新鮮度模式:
  - 熱度掃描
  - 新事件優先
  - 嚴格新事件
- Adds fields to news cards:
  - 新鮮度
  - 新鮮度理由
- Ranking now prioritizes:
  1. freshness_score
  2. heat_score
  3. importance
  4. source quality
  5. recency
- Markdown / CSV news bundle now includes freshness labels and reasons.
- Clear junk signals such as sitemap / old results / irrelevant pages are removed.
- Re-pushed old events are downgraded.
- Old-event new analysis can be retained but labeled.

## Notes

Freshness detection is rule-based and uses:
- article title
- URL date patterns
- source quality
- category
- market-moving keywords

It is not full article-body analysis.

## Recommended workflow

1. Use default "新事件優先".
2. Copy Markdown news bundle.
3. Paste into ChatGPT.
4. Ask ChatGPT to verify:
   - true new events
   - old-event new packaging
   - duplicate pushes
   - junk signals

## Recommended Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL_LIGHT = "llama-3.1-8b-instant"
GROQ_MODEL_HEAVY = "llama-3.3-70b-versatile"
```

## Deploy

Upload:

```text
app.py
requirements.txt
README.md
```

Recommended Python version:

```text
3.12
```
