# Global News Radar V38

V38 fixes OpenAI-style model companies and map readability.

## What changed

- Added OpenAI, Anthropic, xAI, Perplexity, Mistral AI, Cohere, DeepSeek and other AI model / application companies.
- Company extraction is no longer only limited to `supply_chain_master.csv`; it uses aliases plus a lightweight organization-name fallback.
- Scheme A/B/C now include OpenAI when the current news mentions it.
- Map labels are compact, high-contrast, truncated with ellipsis, and offset when companies cluster around the same region.
- Clicking a node now opens a useful popup with role, location, status, news count, topics and top news links.
- Scheme C right panel also shows clickable news links.

## Upload files

Upload:

- app.py
- requirements.txt
- README.md
- supply_chain_master.csv

Then commit and reboot Streamlit.
