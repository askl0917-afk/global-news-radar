# Global News Radar V6

V6 improves translation and mobile reading.

## What changed

- Keeps the original headline, regardless of language.
- Uses automatic language detection to translate headlines into Traditional Chinese.
- No need to manually maintain 100 language-pair rules.
- Adds a mobile card layout and a desktop table layout.
- Keeps the Company News Map tab.
- Company News Map uses `source_country` as approximate location.
  - This is the news source country, not necessarily the real event location.
- Event Map remains the original GDELT Event Database map for geopolitical/social events.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
