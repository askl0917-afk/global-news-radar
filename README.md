# Global News Radar V14

V14 is the stable investment-radar version.

## What changed

- Financial/company news no longer depends mainly on GDELT DOC API.
- Main no-key sources:
  - Google News RSS
  - Yahoo Finance RSS
- GDELT remains as a global geopolitical/event supplement.
- Removes the unreliable "try collapse sidebar" hack.
- Keeps last successful financial-news results when a source fails.
- Map popups are shortened to Top 3 items.
- Mobile-first card layout remains.
- Desktop table layout remains.

## Source strategy

- Google News RSS: broad news discovery, including financial sources.
- Yahoo Finance RSS: stock/ticker-oriented company news.
- GDELT Event Database: geopolitical/global event context.

## Important notes

- Google News RSS is a news aggregator. Source quality still needs review.
- Yahoo Finance RSS works best when a ticker can be inferred, such as NVIDIA -> NVDA.
- GDELT is not a financial terminal. It is kept for geopolitical/event context.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
