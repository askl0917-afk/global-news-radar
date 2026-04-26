# Global News Radar V8

V8 unifies company / financial news and GDELT global event data.

## What changed

- One unified search.
- One unified news feed.
- One unified map.
- Company / financial news from GDELT DOC API.
- Global event data from GDELT Event Database.
- Optional preferred financial-source mode:
  - Reuters
  - CNBC
  - MarketWatch
  - Yahoo Finance
  - Bloomberg
  - WSJ
  - Financial Times
  - Barron's
- Keeps original headlines and auto-translates into Traditional Chinese.
- Mobile card layout and desktop table layout.

## Important notes

- Preferred financial source mode still uses GDELT's index. It does not scrape Reuters or paid websites directly.
- The article map uses source country, not exact event location.
- The event map uses GDELT Event Database coordinates.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
