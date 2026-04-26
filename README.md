# Global News Radar V11

V11 improves search stability.

## What changed

- Default source mode changed to Fast Stable.
- Fast Stable only sends one GDELT DOC API request.
- Financial-source boost is optional and limited.
- API timeout is configurable.
- Timeout errors no longer block the whole app.
- Recommended mobile default:
  - Keyword: NVIDIA
  - Time range: 12h or 24h
  - Article count: 15
  - Source mode: Fast Stable

## Notes

- GDELT DOC API can be slow or rate-limited.
- Reuters / finance-source mode still uses GDELT's index; it does not scrape Reuters directly.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
