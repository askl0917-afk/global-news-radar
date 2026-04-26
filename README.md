# Global News Radar V15

V15 improves readability and removes noisy GDELT event cards from default finance searches.

## What changed

- GDELT global events are off by default.
- GDELT events must directly match the search keyword before entering the unified feed.
- GDELT event cards are rendered as structured event summaries, not fake translated headlines.
- Each finance news card adds a plain Chinese click hint:
  - Worth reading
  - Track only
  - Low priority
- Company / financial news remains based on Google News RSS and Yahoo Finance RSS.
- GDELT remains only as a background geopolitical/event supplement.

## Why

GDELT Event Database is useful for global event context, but its machine-coded event strings are not readable finance headlines.
V15 keeps the investment-radar workflow focused on readable finance news first.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
