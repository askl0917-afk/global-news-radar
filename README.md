# Global News Radar V7

V7 improves the mobile map experience.

## What changed

- Prevents Streamlit reruns when dragging / zooming the Folium maps.
  - This should reduce the annoying dim / bright flicker.
- Enables Leaflet `worldCopyJump` to handle panning across the international date line.
  - This helps when starting near Taiwan and sliding toward the United States.
- Company News Map fits bounds to the available source-country markers.
- Keeps original headline and Traditional Chinese translation.
- Keeps mobile card view and desktop table view.

## Important note about the company-news map

The map uses `source_country` from GDELT DOC API.
That means it shows the news source country, not necessarily the exact event location.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
