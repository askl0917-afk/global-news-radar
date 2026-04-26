# Global News Radar V9

V9 improves the map opening experience.

## What changed

- Unified map now defaults to a world overview map.
- The initial map view stays as a global world map.
- Markers display visible counts directly on the map.
  - Purple badge: company / financial news count by source country.
  - Blue badge: global event count.
  - Red badge: negative / risk event count.
- Added map mode:
  - World overview: count badges
  - Detailed map: cluster / zoom mode
- Keeps unified news feed, preferred finance sources, translation, mobile cards, and desktop table.

## Important notes

- Company / financial news map still uses `source_country`, which means news source country, not exact event location.
- Global events use GDELT Event Database coordinates.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
