# Global News Radar V10

V10 fixes the mobile world overview map.

## What changed

- World overview map now starts at zoom=1 for mobile.
- Count badges use inline styles inside Folium, so they are visible inside the map iframe.
- Layer control is collapsed by default to avoid blocking the map on mobile.
- Unified map height is reduced for mobile readability.
- Source country names are normalized for common variants like US / USA / United States of America.

## Marker colors

- Purple count badge: company / financial news count by source country.
- Blue count badge: global event count.
- Red count badge: negative / risk event count.

## Important notes

- Company / financial news map uses `source_country`, which means news source country, not exact event location.
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
