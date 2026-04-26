# Global News Radar V12

V12 fixes two mobile usability issues.

## What changed

- Sidebar starts collapsed by default, so the map gets more screen space.
- Added a bottom shortcut area in the sidebar:
  - Update unified feed
  - Try to collapse sidebar
- World-map count badges are duplicated at lon±360.
  - This keeps markers visible when panning horizontally across wrapped map copies.
- Keeps V11 stable search behavior.
- Keeps V10 visible count badges and mobile world-map view.

## Notes

- The "Try to collapse sidebar" button uses a lightweight UI hack. On some iPhone Safari versions it may not work; the built-in top-left arrow always works.
- Company / financial news map uses source_country, not exact event location.
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
