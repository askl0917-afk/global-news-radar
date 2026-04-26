
import io
import html
import zipfile
from urllib.parse import urlparse
from datetime import datetime

import folium
import networkx as nx
import pandas as pd
import requests
import streamlit as st
from deep_translator import GoogleTranslator
from folium.plugins import MarkerCluster
from pyvis.network import Network
from streamlit_folium import st_folium


# ------------------------------------------------------------
# Global News Radar V10
# Unified Feed:
# - GDELT DOC API: company / financial / general article search
# - GDELT Event Database: geopolitical / social / event database
# - Unified feed + unified map
# ------------------------------------------------------------

MASTER_FILE_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

PREFERRED_FINANCE_DOMAINS = [
    "reuters.com",
    "cnbc.com",
    "marketwatch.com",
    "finance.yahoo.com",
    "fool.com",
    "barrons.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "investing.com",
    "seekingalpha.com",
]

COUNTRY_COORDS = {
    "United States": (39.8283, -98.5795), "US": (39.8283, -98.5795), "USA": (39.8283, -98.5795),
    "Taiwan": (23.6978, 120.9605), "China": (35.8617, 104.1954), "Hong Kong": (22.3193, 114.1694),
    "Japan": (36.2048, 138.2529), "South Korea": (35.9078, 127.7669), "Korea": (35.9078, 127.7669),
    "United Kingdom": (55.3781, -3.4360), "UK": (55.3781, -3.4360),
    "Germany": (51.1657, 10.4515), "France": (46.2276, 2.2137), "Netherlands": (52.1326, 5.2913),
    "Canada": (56.1304, -106.3468), "Australia": (-25.2744, 133.7751), "India": (20.5937, 78.9629),
    "Singapore": (1.3521, 103.8198), "Israel": (31.0461, 34.8516), "Russia": (61.5240, 105.3188),
    "Ukraine": (48.3794, 31.1656), "Italy": (41.8719, 12.5679), "Spain": (40.4637, -3.7492),
    "Switzerland": (46.8182, 8.2275), "Ireland": (53.1424, -7.6921), "Sweden": (60.1282, 18.6435),
    "Norway": (60.4720, 8.4689), "Denmark": (56.2639, 9.5018), "Finland": (61.9241, 25.7482),
    "Belgium": (50.5039, 4.4699), "Austria": (47.5162, 14.5501), "Poland": (51.9194, 19.1451),
    "Malaysia": (4.2105, 101.9758), "Thailand": (15.8700, 100.9925), "Vietnam": (14.0583, 108.2772),
    "Indonesia": (-0.7893, 113.9213), "Philippines": (12.8797, 121.7740), "Mexico": (23.6345, -102.5528),
    "Brazil": (-14.2350, -51.9253), "United Arab Emirates": (23.4241, 53.8478), "Saudi Arabia": (23.8859, 45.0792),
    "Turkey": (38.9637, 35.2433),
}

GDELT_COLUMNS = [
    "GlobalEventID", "Day", "MonthYear", "Year", "FractionDate",
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
    "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
    "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
    "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
    "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code",
    "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode",
    "QuadClass", "GoldsteinScale", "NumMentions", "NumSources", "NumArticles",
    "AvgTone",
    "Actor1Geo_Type", "Actor1Geo_Fullname", "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code", "Actor1Geo_ADM2Code", "Actor1Geo_Lat",
    "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_Fullname", "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code", "Actor2Geo_ADM2Code", "Actor2Geo_Lat",
    "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_Fullname", "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code", "ActionGeo_ADM2Code", "ActionGeo_Lat",
    "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL"
]

ROOT_EVENT_LABELS = {
    "01": "公開聲明 / Statement",
    "02": "呼籲 / Appeal",
    "03": "表達合作意願 / Cooperate intent",
    "04": "諮詢 / Consult",
    "05": "外交合作 / Diplomatic cooperation",
    "06": "物質合作 / Material cooperation",
    "07": "提供援助 / Aid",
    "08": "讓步 / Yield",
    "09": "調查 / Investigate",
    "10": "要求 / Demand",
    "11": "不滿 / Disapprove",
    "12": "拒絕 / Reject",
    "13": "威脅 / Threaten",
    "14": "抗議 / Protest",
    "15": "展現軍力 / Military posture",
    "16": "減少關係 / Reduce relations",
    "17": "脅迫 / Coerce",
    "18": "攻擊 / Assault",
    "19": "戰鬥 / Fight",
    "20": "非常規暴力 / Unconventional violence",
}


def safe_text(value, fallback="未知"):
    if pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value).strip()



def normalize_country_name(country: str) -> str:
    c = str(country or "").strip()
    aliases = {
        "United States of America": "United States",
        "U.S.": "United States",
        "U.S.A.": "United States",
        "USA": "United States",
        "US": "United States",
        "UK": "United Kingdom",
        "Republic of Korea": "South Korea",
        "Korea, Republic of": "South Korea",
        "Korea Republic": "South Korea",
    }
    return aliases.get(c, c)

def source_quality(domain: str) -> str:
    d = (domain or "").lower()
    if "reuters.com" in d:
        return "A+ Reuters"
    if any(x in d for x in ["bloomberg.com", "wsj.com", "ft.com", "barrons.com"]):
        return "A 財經專業媒體"
    if any(x in d for x in ["cnbc.com", "marketwatch.com", "finance.yahoo.com", "investing.com"]):
        return "B 主流財經媒體"
    if any(x in d for x in ["fool.com", "seekingalpha.com"]):
        return "C 投資觀點媒體"
    return "D 其他來源"


@st.cache_data(ttl=86400, show_spinner=False)
def translate_title_to_zh_tw(title: str, source_language: str = "") -> str:
    title = (title or "").strip()
    source_language = (source_language or "").strip().lower()

    if not title:
        return ""

    if "chinese" in source_language or source_language in {"zh", "zh-cn", "zh-tw"}:
        return title

    try:
        translated = GoogleTranslator(source="auto", target="zh-TW").translate(title[:450])
        translated = html.unescape(str(translated)).strip()
        if not translated or translated.lower() == title.lower():
            return ""
        return translated
    except Exception:
        return ""


@st.cache_data(ttl=900, show_spinner=False)
def load_latest_events(num_files: int = 4, max_rows_per_file: int = 20000) -> pd.DataFrame:
    response = requests.get(MASTER_FILE_LIST, timeout=30)
    response.raise_for_status()

    urls = []
    for line in response.text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            url = parts[-1]
            if url.endswith(".export.CSV.zip"):
                urls.append(url)

    if not urls:
        return pd.DataFrame(columns=GDELT_COLUMNS)

    latest_urls = urls[-num_files:]
    frames = []

    for url in latest_urls:
        try:
            z_response = requests.get(url, timeout=40)
            z_response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(z_response.content)) as zf:
                csv_name = zf.namelist()[0]
                with zf.open(csv_name) as f:
                    df = pd.read_csv(
                        f,
                        sep="\t",
                        header=None,
                        names=GDELT_COLUMNS,
                        dtype=str,
                        nrows=max_rows_per_file,
                        on_bad_lines="skip",
                    )
                    frames.append(df)
        except Exception as exc:
            st.warning(f"讀取 GDELT event file 失敗：{url}；原因：{exc}")

    if not frames:
        return pd.DataFrame(columns=GDELT_COLUMNS)

    df = pd.concat(frames, ignore_index=True)

    numeric_cols = [
        "ActionGeo_Lat", "ActionGeo_Long", "GoldsteinScale",
        "NumMentions", "NumSources", "NumArticles", "AvgTone"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["event_time_utc"] = pd.to_datetime(
        df["DATEADDED"], format="%Y%m%d%H%M%S", errors="coerce", utc=True
    )

    df = df.dropna(subset=["ActionGeo_Lat", "ActionGeo_Long", "event_time_utc"])
    df = df[
        df["ActionGeo_Lat"].between(-90, 90)
        & df["ActionGeo_Long"].between(-180, 180)
    ]
    df = df[df["IsRootEvent"].fillna("") == "1"]

    df["actor1"] = df["Actor1Name"].apply(lambda x: safe_text(x, "未知角色A"))
    df["actor2"] = df["Actor2Name"].apply(lambda x: safe_text(x, "未知角色B"))
    df["who"] = df["actor1"] + " → " + df["actor2"]
    df["where"] = df["ActionGeo_Fullname"].apply(lambda x: safe_text(x, "未知地點"))
    df["root_label"] = df["EventRootCode"].map(ROOT_EVENT_LABELS).fillna("其他事件 / Other")
    df["what"] = df["root_label"] + "｜CAMEO " + df["EventCode"].fillna("")
    df["source"] = df["SOURCEURL"].apply(lambda x: safe_text(x, ""))

    df = df.drop_duplicates(
        subset=["GlobalEventID", "SOURCEURL", "ActionGeo_Lat", "ActionGeo_Long"],
        keep="last"
    )

    return df.sort_values("event_time_utc", ascending=False)


def gdelt_doc_request(query: str, timespan: str, max_records: int) -> pd.DataFrame:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "hybridrel",
        "timespan": timespan,
    }

    headers = {"User-Agent": "GlobalNewsRadarV10/1.0"}

    try:
        r = requests.get(GDELT_DOC_API, params=params, headers=headers, timeout=30)

        if r.status_code == 429:
            st.warning("GDELT DOC API 暫時限流 429。請等 5～10 分鐘再查，或降低篇數。")
            return pd.DataFrame()

        if r.status_code != 200:
            st.warning(f"GDELT DOC API 回傳狀態碼 {r.status_code}。請稍後再試。")
            return pd.DataFrame()

        text = (r.text or "").strip()
        if not text:
            st.warning("GDELT DOC API 回傳空白內容。請稍後再試。")
            return pd.DataFrame()

        try:
            data = r.json()
        except Exception:
            preview = text[:180].replace("\n", " ")
            st.warning(f"GDELT DOC API 回傳不是 JSON。回傳開頭：{preview}")
            return pd.DataFrame()

    except Exception as exc:
        st.warning(f"GDELT DOC API 查詢失敗：{exc}")
        return pd.DataFrame()

    articles = data.get("articles", [])
    rows = []

    for a in articles:
        url = a.get("url", "")
        domain = a.get("domain") or (urlparse(url).netloc if url else "")
        rows.append({
            "time_utc": a.get("seendate", ""),
            "title": a.get("title", ""),
            "domain": domain,
            "source_country": a.get("sourcecountry", ""),
            "language": a.get("language", ""),
            "url": url,
            "image": a.get("socialimage", ""),
            "source_query": query,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True)
        df = df.drop_duplicates(subset=["url"])
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def search_article_news(
    query: str,
    timespan: str = "24h",
    max_records: int = 30,
    translate_titles: bool = True,
    preferred_mode: bool = True,
    preferred_domains: tuple = (),
    per_domain_records: int = 5,
) -> pd.DataFrame:
    query = (query or "").strip()
    if not query:
        return pd.DataFrame()

    frames = []

    # Broad GDELT query
    frames.append(gdelt_doc_request(query=query, timespan=timespan, max_records=max_records))

    # Domain-enhanced queries for Reuters / major financial sites.
    # This still uses GDELT's index; it does not scrape Reuters directly.
    if preferred_mode and preferred_domains:
        for domain in preferred_domains:
            domain_q = f'{query} domain:{domain}'
            frames.append(gdelt_doc_request(query=domain_q, timespan=timespan, max_records=per_domain_records))

    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["url"])
    df["source_quality"] = df["domain"].apply(source_quality)
    df["data_type"] = "新聞文章"
    df["source_country"] = df["source_country"].apply(normalize_country_name)
    df["display_location"] = df["source_country"].fillna("")
    df["lat"] = df["source_country"].apply(lambda c: COUNTRY_COORDS.get(str(c).strip(), (None, None))[0])
    df["lon"] = df["source_country"].apply(lambda c: COUNTRY_COORDS.get(str(c).strip(), (None, None))[1])

    if translate_titles:
        df["title_zh"] = df.apply(
            lambda row: translate_title_to_zh_tw(row.get("title", ""), row.get("language", "")),
            axis=1
        )
    else:
        df["title_zh"] = ""

    return df.sort_values(["source_quality", "time_utc"], ascending=[True, False])


def filter_events(events: pd.DataFrame, keyword: str, root_filter, country_filter: str, min_mentions: int, max_events: int) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()

    df = events.copy()

    if root_filter:
        df = df[df["root_label"].isin(root_filter)]

    if country_filter.strip():
        q = country_filter.strip().lower()
        df = df[df["where"].str.lower().str.contains(q, na=False)]

    if keyword.strip():
        q = keyword.strip().lower()
        df = df[
            df["actor1"].str.lower().str.contains(q, na=False)
            | df["actor2"].str.lower().str.contains(q, na=False)
            | df["source"].str.lower().str.contains(q, na=False)
            | df["where"].str.lower().str.contains(q, na=False)
            | df["what"].str.lower().str.contains(q, na=False)
        ]

    df = df[df["NumMentions"].fillna(0) >= min_mentions]
    return df.head(max_events)


def build_unified_feed(articles: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    article_rows = []
    if articles is not None and not articles.empty:
        for _, r in articles.iterrows():
            article_rows.append({
                "time_utc": r.get("time_utc"),
                "data_type": "公司/財經新聞",
                "title": r.get("title", ""),
                "title_zh": r.get("title_zh", ""),
                "domain": r.get("domain", ""),
                "source_quality": r.get("source_quality", ""),
                "location": r.get("source_country", ""),
                "language": r.get("language", ""),
                "url": r.get("url", ""),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "summary": "",
            })

    event_rows = []
    if events is not None and not events.empty:
        for _, r in events.iterrows():
            event_title = f"{r.get('who', '')}｜{r.get('where', '')}｜{r.get('what', '')}"
            event_rows.append({
                "time_utc": r.get("event_time_utc"),
                "data_type": "全球事件",
                "title": event_title,
                "title_zh": event_title,
                "domain": urlparse(str(r.get("source", ""))).netloc,
                "source_quality": "GDELT Event",
                "location": r.get("where", ""),
                "language": "",
                "url": r.get("source", ""),
                "lat": r.get("ActionGeo_Lat"),
                "lon": r.get("ActionGeo_Long"),
                "summary": f"mentions={r.get('NumMentions', '')}, tone={r.get('AvgTone', '')}, Goldstein={r.get('GoldsteinScale', '')}",
            })

    rows = article_rows + event_rows
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True)
    return df.sort_values("time_utc", ascending=False)


def marker_color_for_event(row) -> str:
    goldstein = row.get("GoldsteinScale")
    if pd.notna(goldstein) and goldstein <= -5:
        return "red"
    elif pd.notna(goldstein) and goldstein < 0:
        return "orange"
    elif pd.notna(goldstein) and goldstein > 3:
        return "green"
    return "blue"


def count_badge_html(count: int, badge_type: str = "news") -> str:
    """Inline-styled badge.

    Folium maps render inside an iframe, so Streamlit page CSS may not apply.
    V10 uses inline styles to make count markers visible on mobile.
    """
    color = "#7b2cbf"  # purple: company / finance news
    if badge_type == "event":
        color = "#1976d2"  # blue: general events
    elif badge_type == "risk":
        color = "#d62828"  # red: negative / risk events

    return (
        f'<div style="'
        f'width:36px;height:36px;border-radius:999px;'
        f'background:{color};color:white;'
        f'font-weight:900;font-size:15px;line-height:36px;text-align:center;'
        f'border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.45);'
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
        f'">{count}</div>'
    )


def build_world_overview_map(articles: pd.DataFrame, events: pd.DataFrame, show_articles=True, show_events=True):
    """World overview map with count badges.

    This map intentionally starts from a full-world view instead of fitting to one region.
    """
    m = folium.Map(
        location=[15, 0],
        zoom_start=1,
        min_zoom=1,
        tiles="CartoDB positron",
        world_copy_jump=True,
        prefer_canvas=True,
        control_scale=True,
        max_bounds=False,
    )

    if show_articles and articles is not None and not articles.empty and "source_country" in articles.columns:
        article_layer = folium.FeatureGroup(name="公司/財經新聞數量", show=True).add_to(m)

        for country, group in articles.groupby("source_country", dropna=True):
            country_name = normalize_country_name(country)
            if not country_name:
                continue

            coords = COUNTRY_COORDS.get(country_name) or COUNTRY_COORDS.get(country_name.title())
            if not coords:
                continue

            items_html = []
            for _, row in group.head(8).iterrows():
                title = html.escape(str(row.get("title", "")))
                title_zh = html.escape(str(row.get("title_zh", "")))
                url = str(row.get("url", ""))
                domain = html.escape(str(row.get("domain", "")))
                q = html.escape(str(row.get("source_quality", "")))

                headline = title_zh or title
                line = f"<b>{headline}</b><br><small>原文：{title}</small><br><small>{domain}｜{q}</small>"
                if url.startswith("http"):
                    line = f"<a href='{html.escape(url)}' target='_blank'>{line}</a>"
                items_html.append(f"<li>{line}</li>")

            popup_html = f"""
            <div style="width:370px; font-size:13px;">
                <b>公司/財經新聞｜{html.escape(country_name)}</b><br>
                新聞數量：{len(group)}<br>
                <small>定位方式：新聞來源國家，不等同事件真實發生地。</small>
                <ol>{''.join(items_html)}</ol>
            </div>
            """

            folium.Marker(
                location=list(coords),
                popup=folium.Popup(popup_html, max_width=430),
                tooltip=f"公司/財經新聞｜{country_name}｜{len(group)} 篇",
                icon=folium.DivIcon(
                    html=count_badge_html(len(group), "news"),
                    icon_size=(34, 34),
                    icon_anchor=(17, 17),
                ),
            ).add_to(article_layer)

    if show_events and events is not None and not events.empty:
        event_layer = folium.FeatureGroup(name="全球事件數量", show=True).add_to(m)
        event_df = events.copy()
        event_df = event_df.dropna(subset=["ActionGeo_Lat", "ActionGeo_Long"])

        if not event_df.empty:
            event_df["lat_round"] = pd.to_numeric(event_df["ActionGeo_Lat"], errors="coerce").round(1)
            event_df["lon_round"] = pd.to_numeric(event_df["ActionGeo_Long"], errors="coerce").round(1)
            event_df["place_key"] = (
                event_df["where"].fillna("未知地點")
                + "|"
                + event_df["lat_round"].astype(str)
                + "|"
                + event_df["lon_round"].astype(str)
            )

            for _, group in event_df.groupby("place_key"):
                first = group.iloc[0]
                lat = float(first["lat_round"])
                lon = float(first["lon_round"])
                place = str(first.get("where", "未知地點"))

                min_goldstein = pd.to_numeric(group["GoldsteinScale"], errors="coerce").min()
                badge_type = "risk" if pd.notna(min_goldstein) and min_goldstein < 0 else "event"

                items_html = []
                for _, row in group.head(8).iterrows():
                    source = str(row.get("source", ""))
                    title = html.escape(str(row.get("what", "")))
                    who = html.escape(str(row.get("who", "")))
                    time_utc = html.escape(str(row.get("event_time_utc", "")))
                    line = f"<b>{title}</b><br><small>{who}</small><br><small>{time_utc}</small>"
                    if source.startswith("http"):
                        line = f"<a href='{html.escape(source)}' target='_blank'>{line}</a>"
                    items_html.append(f"<li>{line}</li>")

                popup_html = f"""
                <div style="width:360px; font-size:13px;">
                    <b>全球事件｜{html.escape(place)}</b><br>
                    事件數量：{len(group)}<br>
                    <ol>{''.join(items_html)}</ol>
                </div>
                """

                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=420),
                    tooltip=f"全球事件｜{place}｜{len(group)} 件",
                    icon=folium.DivIcon(
                        html=count_badge_html(len(group), badge_type),
                        icon_size=(34, 34),
                        icon_anchor=(17, 17),
                    ),
                ).add_to(event_layer)

    folium.LayerControl(collapsed=True).add_to(m)
    return m


def build_unified_map(articles: pd.DataFrame, events: pd.DataFrame, show_articles=True, show_events=True):
    m = folium.Map(
        location=[25, 0],
        zoom_start=2,
        tiles="CartoDB positron",
        world_copy_jump=True,
        prefer_canvas=True,
    )

    coords_list = []

    if show_articles and articles is not None and not articles.empty:
        article_cluster = MarkerCluster(name="公司/財經新聞").add_to(m)

        for country, group in articles.groupby("source_country", dropna=True):
            country_name = normalize_country_name(country)
            if not country_name:
                continue

            coords = COUNTRY_COORDS.get(country_name) or COUNTRY_COORDS.get(country_name.title())
            if not coords:
                continue

            coords_list.append(coords)

            items_html = []
            for _, row in group.head(7).iterrows():
                title = html.escape(str(row.get("title", "")))
                title_zh = html.escape(str(row.get("title_zh", "")))
                url = str(row.get("url", ""))
                domain = html.escape(str(row.get("domain", "")))
                q = html.escape(str(row.get("source_quality", "")))

                line = f"<b>{title_zh or title}</b><br><small>原文：{title}</small><br><small>{domain}｜{q}</small>"
                if url.startswith("http"):
                    line = f"<a href='{html.escape(url)}' target='_blank'>{line}</a>"
                items_html.append(f"<li>{line}</li>")

            popup_html = f"""
            <div style="width:360px; font-size:13px;">
                <b>{html.escape(country_name)}</b><br>
                公司/財經新聞：{len(group)} 篇<br>
                <small>定位方式：新聞來源國家，不等同事件真實發生地。</small>
                <ol>{''.join(items_html)}</ol>
            </div>
            """
            folium.Marker(
                location=list(coords),
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=f"公司新聞｜{country_name}｜{len(group)} 篇",
                icon=folium.Icon(color="purple", icon="info-sign"),
            ).add_to(article_cluster)

    if show_events and events is not None and not events.empty:
        event_cluster = MarkerCluster(name="全球事件").add_to(m)

        for _, row in events.iterrows():
            lat = row.get("ActionGeo_Lat")
            lon = row.get("ActionGeo_Long")
            if pd.isna(lat) or pd.isna(lon):
                continue

            coords_list.append((float(lat), float(lon)))
            source = str(row.get("source", ""))
            source_html = f'<a href="{html.escape(source)}" target="_blank">來源連結</a>' if source.startswith("http") else "無來源連結"

            popup_html = f"""
            <div style="width:330px; font-size:13px;">
                <b>全球事件</b><br>
                <b>誰：</b>{html.escape(str(row.get("who", "未知")))}<br>
                <b>何時：</b>{row.get("event_time_utc")}<br>
                <b>何地：</b>{html.escape(str(row.get("where", "未知")))}<br>
                <b>何事：</b>{html.escape(str(row.get("what", "未知")))}<br>
                <b>聲量：</b>mentions={row.get("NumMentions", "")}, articles={row.get("NumArticles", "")}<br>
                {source_html}
            </div>
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=380),
                tooltip=f"事件｜{safe_text(row.get('where'))}｜{safe_text(row.get('root_label'))}",
                icon=folium.Icon(color=marker_color_for_event(row), icon="info-sign"),
            ).add_to(event_cluster)

    folium.LayerControl().add_to(m)

    if coords_list:
        if len(coords_list) == 1:
            m.location = list(coords_list[0])
            m.zoom_start = 4
        else:
            m.fit_bounds(coords_list, padding=(25, 25))

    return m


def build_relationship_graph(feed: pd.DataFrame) -> str:
    g = nx.Graph()

    if feed is None or feed.empty:
        html_path = "relationship_graph.html"
        Network(height="650px", width="100%").save_graph(html_path)
        return html_path

    sample = feed.head(80).copy()

    for i, row in sample.iterrows():
        item_id = f"I:{i}"
        dtype = str(row.get("data_type", ""))
        title = str(row.get("title_zh") or row.get("title") or "Untitled")
        domain = str(row.get("domain", ""))
        location = str(row.get("location", ""))
        url = str(row.get("url", ""))

        g.add_node(item_id, label=dtype, title=f"{title}<br>{url}", group="item")

        if domain:
            dnode = f"D:{domain}"
            g.add_node(dnode, label=domain, title="Source domain", group="domain")
            g.add_edge(item_id, dnode)

        if location:
            lnode = f"L:{location}"
            g.add_node(lnode, label=location, title="Location / source country", group="location")
            g.add_edge(item_id, lnode)

    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="#222222")
    net.from_nx(g)
    net.toggle_physics(True)
    html_path = "relationship_graph.html"
    net.save_graph(html_path)
    return html_path


st.set_page_config(page_title="Global News Radar V10", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-top: 1.1rem;
    padding-left: 1rem;
    padding-right: 1rem;
}
* { transition: none !important; }
div[data-testid="stStatusWidget"] { visibility: hidden !important; }
div[data-testid="stDecoration"] { display: none !important; }
.article-card {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 14px;
    padding: 14px 15px;
    margin: 12px 0 16px 0;
    background: rgba(128,128,128,0.08);
}
.article-type {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(128,128,128,0.18);
    font-size: 0.78rem;
    margin-bottom: 8px;
}
.article-original {
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.4;
}
.article-zh {
    font-size: 1.09rem;
    font-weight: 750;
    line-height: 1.52;
    margin-top: 8px;
}
.article-meta {
    font-size: 0.86rem;
    line-height: 1.45;
    opacity: 0.72;
    margin-top: 9px;
}
.article-source {
    font-size: 0.9rem;
    margin-top: 8px;
}
.map-badge {
    min-width: 34px;
    height: 34px;
    border-radius: 999px;
    color: white;
    font-weight: 800;
    font-size: 14px;
    line-height: 34px;
    text-align: center;
    border: 2px solid white;
    box-shadow: 0 1px 6px rgba(0,0,0,0.35);
}
.map-badge-news { background: #7b2cbf; }
.map-badge-event { background: #1976d2; }
.map-badge-risk { background: #d62828; }
@media (max-width: 768px) {
    h1 {
        font-size: 2.15rem !important;
        line-height: 1.18 !important;
        word-break: keep-all;
    }
    div[data-testid="stMetricValue"] { font-size: 2.1rem !important; }
    .article-card { padding: 13px 13px; border-radius: 13px; }
}
@media (min-width: 769px) {
    .block-container {
        max-width: 1200px;
        padding-left: 2.2rem;
        padding-right: 2.2rem;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("🌍 Global News Radar V10：統合新聞流 + 統合地圖")

with st.sidebar:
    st.header("統合搜尋")
    query = st.text_input("關鍵字 / 公司 / 人名", value="NVIDIA")
    timespan = st.selectbox("新聞時間範圍", options=["1h", "6h", "12h", "24h", "3d", "7d"], index=2)
    article_records = st.slider("一般新聞篇數", 5, 100, 20, step=5)
    translate_titles = st.checkbox("原文標題 + 智慧翻譯成繁中", value=True)

    st.divider()
    st.subheader("來源策略")
    source_mode = st.radio(
        "新聞來源",
        ["全球覆蓋", "主流財經來源優先"],
        index=1,
        help="主流財經來源優先會額外嘗試搜尋 Reuters / CNBC / MarketWatch / Yahoo Finance 等來源；仍然透過 GDELT 索引，不直接爬 Reuters。"
    )

    preferred_domains = []
    per_domain_records = 5
    if source_mode == "主流財經來源優先":
        preferred_domains = st.multiselect(
            "加強搜尋的財經來源",
            options=PREFERRED_FINANCE_DOMAINS,
            default=["reuters.com", "cnbc.com", "marketwatch.com", "finance.yahoo.com"],
        )
        per_domain_records = st.slider("每個財經來源最多篇數", 1, 10, 3)

    st.divider()
    st.subheader("全球事件設定")
    num_files = st.slider("最近幾個 15 分鐘事件檔", 1, 12, 4)
    max_rows = st.slider("每個事件檔最多列數", 1000, 50000, 20000, step=1000)
    root_filter = st.multiselect("事件大類", options=list(ROOT_EVENT_LABELS.values()), default=[])
    country_filter = st.text_input("事件地點關鍵字", value="")
    min_mentions = st.slider("事件最低提及次數", 0, 100, 0)
    max_event_items = st.slider("納入統合新聞流的事件數", 0, 100, 30)

    st.divider()
    st.subheader("顯示")
    display_mode = st.radio("閱讀版型", ["手機卡片", "電腦表格"], index=0)
    map_show_articles = st.checkbox("地圖顯示公司/財經新聞", value=True)
    map_show_events = st.checkbox("地圖顯示全球事件", value=True)
    map_mode = st.radio("地圖模式", ["世界總覽：數量標記", "詳細地圖：可分群縮放"], index=0)
    st.caption("V10：手機版世界總覽預設 zoom=1，數量標記使用地圖內嵌樣式，避免手機看不到。")

    search_button = st.button("更新統合新聞流", type="primary")

with st.spinner("正在抓取 GDELT 全球事件資料..."):
    events_all = load_latest_events(num_files=num_files, max_rows_per_file=max_rows)

if "articles" not in st.session_state:
    st.session_state["articles"] = pd.DataFrame()
if "last_query" not in st.session_state:
    st.session_state["last_query"] = ""

if search_button:
    with st.spinner("正在搜尋公司 / 財經新聞..."):
        st.session_state["articles"] = search_article_news(
            query=query,
            timespan=timespan,
            max_records=article_records,
            translate_titles=translate_titles,
            preferred_mode=(source_mode == "主流財經來源優先"),
            preferred_domains=tuple(preferred_domains),
            per_domain_records=per_domain_records,
        )
        st.session_state["last_query"] = query

articles = st.session_state["articles"]
events_filtered = filter_events(
    events_all,
    keyword=query,
    root_filter=root_filter,
    country_filter=country_filter,
    min_mentions=min_mentions,
    max_events=max_event_items
)

feed = build_unified_feed(articles, events_filtered)

col1, col2, col3, col4 = st.columns(4)
col1.metric("統合新聞流", f"{len(feed):,}")
col2.metric("公司/財經新聞", f"{len(articles):,}")
col3.metric("全球事件", f"{len(events_filtered):,}")
col4.metric("事件原始數", f"{len(events_all):,}")

tab_feed, tab_map, tab_graph, tab_raw = st.tabs(["統合新聞流", "統合地圖", "關係圖", "原始資料"])

with tab_feed:
    st.subheader("統合新聞流")
    st.caption("這裡把公司/財經新聞與全球事件統合在同一條時間流。公司新聞來自 GDELT DOC；全球事件來自 GDELT Event Database。")

    if feed.empty:
        st.info("尚未查到統合資料。請在左側設定關鍵字後按「更新統合新聞流」。")
    else:
        if display_mode == "手機卡片":
            for _, row in feed.head(100).iterrows():
                dtype = html.escape(str(row.get("data_type", "")))
                title = html.escape(str(row.get("title", "")))
                title_zh = html.escape(str(row.get("title_zh", "")))
                url = str(row.get("url", ""))
                url_safe = html.escape(url, quote=True)
                domain = html.escape(str(row.get("domain", "")))
                time_utc = html.escape(str(row.get("time_utc", "")))
                location = html.escape(str(row.get("location", "")))
                quality = html.escape(str(row.get("source_quality", "")))
                summary = html.escape(str(row.get("summary", "")))

                title_html = title
                if url.startswith("http"):
                    title_html = f"<a href='{url_safe}' target='_blank'>{title}</a>"

                zh_html = title_zh if title_zh else title

                st.markdown(
                    f"""
                    <div class="article-card">
                        <div class="article-type">{dtype}</div>
                        <div class="article-zh">中文：{zh_html}</div>
                        <div class="article-original">原文 / 原始描述：{title_html}</div>
                        <div class="article-meta">{time_utc}<br>{domain}｜{location}｜{quality}<br>{summary}</div>
                        <div class="article-source"><a href="{url_safe}" target="_blank">打開來源</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            table_cols = ["time_utc", "data_type", "title_zh", "title", "domain", "source_quality", "location", "language", "url"]
            st.dataframe(feed[[c for c in table_cols if c in feed.columns]], use_container_width=True)

with tab_map:
    st.subheader("統合地圖")
    st.caption("世界總覽模式會固定以手機可看到的全球大地圖開場。紫色數字＝公司/財經新聞來源國家篇數；藍色數字＝全球事件；紅色數字＝偏負面/風險事件。")
    if map_mode == "世界總覽：數量標記":
        unified_map = build_world_overview_map(
            articles=articles,
            events=events_filtered,
            show_articles=map_show_articles,
            show_events=map_show_events,
        )
    else:
        unified_map = build_unified_map(
            articles=articles,
            events=events_filtered,
            show_articles=map_show_articles,
            show_events=map_show_events,
        )
    st_folium(unified_map, width=None, height=520, returned_objects=[], key="unified_map")

with tab_graph:
    st.subheader("統合關係圖")
    if feed.empty:
        st.info("目前沒有資料可繪製關係圖。")
    else:
        graph_path = build_relationship_graph(feed)
        with open(graph_path, "r", encoding="utf-8") as f:
            st.components.v1.html(f.read(), height=700, scrolling=True)

with tab_raw:
    st.subheader("原始資料")
    st.markdown("### 公司/財經新聞")
    if articles.empty:
        st.info("尚未查到公司/財經新聞。")
    else:
        st.dataframe(articles, use_container_width=True)

    st.markdown("### 全球事件")
    if events_filtered.empty:
        st.info("目前沒有符合條件的全球事件。")
    else:
        display_cols = [
            "event_time_utc", "who", "where", "what",
            "NumMentions", "NumArticles", "AvgTone", "GoldsteinScale", "source"
        ]
        st.dataframe(events_filtered[[c for c in display_cols if c in events_filtered.columns]], use_container_width=True)
