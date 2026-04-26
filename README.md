# Global News Radar V17

V17 adds a selectable financial-news time range.

## What changed

- Added "財經新聞時間範圍":
  - 最近 1 小時
  - 最近 6 小時
  - 最近 12 小時
  - 最近 24 小時
  - 最近 3 天
  - 最近 7 天
  - 不限時間
- Google News RSS query gets a `when:` hint.
- Results are also locally filtered by timestamp.
- If a time range is selected, articles without timestamps are excluded.
- Keeps V16 multi-keyword logic:
  - 交集 AND
  - 聯集 OR
- Keeps importance-first sorting:
  - A → B → C → D
  - then source quality
  - then recency

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
