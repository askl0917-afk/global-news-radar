import io
import html
import time
import zipfile
from urllib.parse import urlparse

import folium
import networkx as nx
import pandas as pd
import requests
import streamlit as st
from folium.plugins import MarkerCluster
from pyvis.network import Network
from streamlit_folium import st_folium

MASTER_FILE_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

MYMEMORY_TRANSLATE_API = "https://api.mymemory.translated.net/get"

# Approximate country centroids for company-news source-country map.
# Note: this maps where the news source is based, not necessarily where the event happened.
COUNTRY_COORDS = {
    "United States": (39.8283, -98.5795), "US": (39.8283, -98.5795), "USA": (39.8283, -98.5795),
    "Taiwan": (23.6978, 120.9605), "China": (35.8617, 104.1954), "Hong Kong": (22.3193, 114.1694),
    "Japan": (36.2048, 138.2529), "South Korea": (35.9078, 127.7669), "Korea": (35.9078, 127.7669),
    "United Kingdom": (55.3781, -3.4360), "UK": (55.3781, -3.4360),
    "Germany": (51.1657, 10.4515), "France": (46.2276, 2.2137), "Netherlands": (52.1326, 5.2913),
    "Canada": (56.1304, -106.3468), "Australia": (-25.2744, 133.7751), "India": (20.5937, 78.9629),
    "Singapore": (1.3521, 103.8198), "Israel": (31.0461, 34.8516), "Russia": (61.5240, 105.3188),
    "Ukraine": (48.3794, 31.1656), "Italy": (41.8719, 12.5674), "Spain": (40.4637, -3.7492),
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



@st.cache_data(ttl=86400, show_spinner=False)
def translate_title_to_zh_tw(title: str) -> str:
    """Translate one headline into Traditional Chinese using a free translation endpoint.

    If the service is unavailable, return an empty string instead of breaking the app.
    """
    title = (title or "").strip()
    if not title:
        return ""

    try:
        params = {
            "q": title[:450],
            "langpair": "en|zh-TW",
        }
        r = requests.get(MYMEMORY_TRANSLATE_API, params=params, timeout=15)
        if r.status_code != 200:
            return ""
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        translated = html.unescape(str(translated)).strip()
        if translated.lower() == title.lower():
            return ""
        return translated
    except Exception:
        return ""


@st.cache_data(ttl=1800, show_spinner=False)
def search_company_news_cached(query: str, timespan: str = "24h", max_records: int = 30, translate_titles: bool = True) -> pd.DataFrame:
    """Search GDELT DOC API defensively.

    V4 changes:
    - Does not assume GDELT always returns JSON.
    - Handles 429 / empty / HTML responses gracefully.
    - Uses fewer default records to reduce API throttling risk.
    """
    query = (query or "").strip()
    if not query:
        return pd.DataFrame()

    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "hybridrel",
        "timespan": timespan,
    }

    headers = {
        "User-Agent": "GlobalNewsRadarV5/1.0"
    }

    try:
        r = requests.get(GDELT_DOC_API, params=params, headers=headers, timeout=30)

        if r.status_code == 429:
            st.warning("GDELT DOC API 暫時限流 429。請等 5～10 分鐘再查，或改用單一關鍵字，例如 NVIDIA。")
            return pd.DataFrame()

        if r.status_code != 200:
            st.warning(f"GDELT DOC API 回傳狀態碼 {r.status_code}。請稍後再試。")
            return pd.DataFrame()

        text = (r.text or "").strip()
        if not text:
            st.warning("GDELT DOC API 回傳空白內容。請稍後再試，或把時間範圍改成 3d / 7d。")
            return pd.DataFrame()

        try:
            data = r.json()
        except Exception:
            preview = text[:180].replace("\n", " ")
            st.warning(f"GDELT DOC API 回傳不是 JSON，可能是暫時限流或服務頁面。回傳開頭：{preview}")
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
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True)
        df = df.drop_duplicates(subset=["url"]).sort_values("time_utc", ascending=False)

        if translate_titles:
            df["title_zh"] = df["title"].apply(translate_title_to_zh_tw)
        else:
            df["title_zh"] = ""

    return df

def event_popup(row) -> str:
    source = safe_text(row.get("source"), "")
    source_html = (
        f'<a href="{html.escape(source)}" target="_blank">來源連結</a>'
        if source.startswith("http") else "無來源連結"
    )
    return f"""
    <div style="width:330px; font-size:13px;">
        <b>誰：</b>{html.escape(row.get("who", "未知"))}<br>
        <b>何時：</b>{row.get("event_time_utc")}<br>
        <b>何地：</b>{html.escape(row.get("where", "未知"))}<br>
        <b>何事：</b>{html.escape(row.get("what", "未知"))}<br>
        <b>聲量：</b>mentions={row.get("NumMentions", "")}, articles={row.get("NumArticles", "")}<br>
        <b>情緒：</b>AvgTone={row.get("AvgTone", "")}, Goldstein={row.get("GoldsteinScale", "")}<br>
        {source_html}
    </div>
    """


def build_map(df: pd.DataFrame):
    m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB positron")
    cluster = MarkerCluster(name="全球事件").add_to(m)

    for _, row in df.iterrows():
        lat = row["ActionGeo_Lat"]
        lon = row["ActionGeo_Long"]

        goldstein = row.get("GoldsteinScale")
        if pd.notna(goldstein) and goldstein <= -5:
            color = "red"
        elif pd.notna(goldstein) and goldstein < 0:
            color = "orange"
        elif pd.notna(goldstein) and goldstein > 3:
            color = "green"
        else:
            color = "blue"

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(event_popup(row), max_width=380),
            tooltip=f"{safe_text(row.get('where'))}｜{safe_text(row.get('root_label'))}",
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(cluster)

    folium.LayerControl().add_to(m)
    return m


def build_company_news_map(articles: pd.DataFrame):
    """Map company-news articles by source country.

    Important: GDELT DOC article list does not provide precise event coordinates.
    This map uses source_country as a practical first version.
    """
    m = folium.Map(location=[25, 0], zoom_start=2, tiles="CartoDB positron")
    cluster = MarkerCluster(name="公司新聞來源國家").add_to(m)

    if articles is None or articles.empty or "source_country" not in articles.columns:
        return m

    for country, group in articles.groupby("source_country", dropna=True):
        country_name = str(country).strip()
        if not country_name:
            continue

        coords = COUNTRY_COORDS.get(country_name)
        if coords is None:
            coords = COUNTRY_COORDS.get(country_name.title())
        if coords is None:
            continue

        items_html = []
        for _, row in group.head(6).iterrows():
            title = html.escape(str(row.get("title", "")))
            title_zh = html.escape(str(row.get("title_zh", "")))
            url = str(row.get("url", ""))
            time_utc = html.escape(str(row.get("time_utc", "")))
            domain = html.escape(str(row.get("domain", "")))

            title_part = f"<b>{title}</b>"
            if title_zh:
                title_part += f"<br><span style='color:#444;'>中文：{title_zh}</span>"

            if url.startswith("http"):
                title_part = f"<a href='{html.escape(url)}' target='_blank'>{title_part}</a>"

            items_html.append(f"<li>{title_part}<br><small>{time_utc}｜{domain}</small></li>")

        popup_html = f"""
        <div style="width:360px; font-size:13px;">
            <b>{html.escape(country_name)}</b><br>
            公司新聞篇數：{len(group)}<br>
            <small>定位方式：新聞來源國家，不等同事件發生地點。</small>
            <ol>{''.join(items_html)}</ol>
        </div>
        """

        folium.Marker(
            location=list(coords),
            popup=folium.Popup(popup_html, max_width=420),
            tooltip=f"{country_name}｜{len(group)} 篇公司新聞",
            icon=folium.Icon(color="purple", icon="info-sign")
        ).add_to(cluster)

    folium.LayerControl().add_to(m)
    return m


def build_relationship_graph(df: pd.DataFrame, max_events: int = 80) -> str:
    g = nx.Graph()
    sample = df.head(max_events).copy()

    for _, row in sample.iterrows():
        event_id = f"E:{row['GlobalEventID']}"
        actor1 = f"A:{row['actor1']}"
        actor2 = f"A:{row['actor2']}"
        location = f"L:{row['where']}"

        event_title = f"{row['what']}<br>{row['event_time_utc']}<br>{row['source']}"

        g.add_node(event_id, label=f"{row['root_label']}", title=event_title, group="event")
        g.add_node(actor1, label=row["actor1"], title="Actor 1", group="actor")
        g.add_node(actor2, label=row["actor2"], title="Actor 2", group="actor")
        g.add_node(location, label=row["where"], title="Location", group="location")

        g.add_edge(actor1, event_id, title="Actor1 involved")
        g.add_edge(event_id, actor2, title="Actor2 involved")
        g.add_edge(event_id, location, title="Occurred at")

    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="#222222")
    net.from_nx(g)
    net.toggle_physics(True)

    html_path = "relationship_graph.html"
    net.save_graph(html_path)
    return html_path


st.set_page_config(page_title="Global News Radar V5", layout="wide")
st.title("🌍 Global News Radar V5：全球事件地圖 + 公司新聞搜尋")

with st.sidebar:
    st.header("A. 全球事件地圖")
    num_files = st.slider("抓取最近幾個 15 分鐘事件檔", 1, 12, 4)
    max_rows = st.slider("每個事件檔最多讀取列數", 1000, 50000, 20000, step=1000)

    root_filter = st.multiselect(
        "事件大類",
        options=list(ROOT_EVENT_LABELS.values()),
        default=[]
    )
    country_filter = st.text_input("事件地點關鍵字，例如 Taiwan / China / Israel")
    actor_filter = st.text_input("事件角色關鍵字，例如 Trump / China / Russia")
    min_mentions = st.slider("事件最低提及次數 NumMentions", 0, 100, 0)

    st.divider()
    st.header("B. 公司 / 財經新聞搜尋")
    company_query = st.text_input(
        "新聞關鍵字",
        value="NVIDIA",
        help="V5 建議先用單一關鍵字，例如 NVIDIA。會保留英文標題，並嘗試產生繁體中文翻譯。"
    )
    timespan = st.selectbox(
        "新聞時間範圍",
        options=["1h", "6h", "12h", "24h", "3d", "7d"],
        index=2
    )
    max_records = st.slider("最多新聞篇數", 5, 50, 10, step=5)
    translate_titles = st.checkbox("保留英文標題，並翻譯成中文", value=True)
    search_button = st.button("搜尋公司新聞", type="primary")

with st.spinner("正在抓取 GDELT 最新事件資料..."):
    events = load_latest_events(num_files=num_files, max_rows_per_file=max_rows)

filtered = events.copy()

if root_filter:
    filtered = filtered[filtered["root_label"].isin(root_filter)]

if country_filter.strip():
    q = country_filter.strip().lower()
    filtered = filtered[filtered["where"].str.lower().str.contains(q, na=False)]

if actor_filter.strip():
    q = actor_filter.strip().lower()
    filtered = filtered[
        filtered["actor1"].str.lower().str.contains(q, na=False)
        | filtered["actor2"].str.lower().str.contains(q, na=False)
        | filtered["source"].str.lower().str.contains(q, na=False)
    ]

filtered = filtered[filtered["NumMentions"].fillna(0) >= min_mentions]

if "articles" not in st.session_state:
    st.session_state["articles"] = pd.DataFrame()
if "last_company_query" not in st.session_state:
    st.session_state["last_company_query"] = ""

if search_button:
    with st.spinner("正在搜尋公司 / 財經新聞..."):
        st.session_state["articles"] = search_company_news_cached(
            company_query,
            timespan=timespan,
            max_records=max_records,
            translate_titles=translate_titles
        )
        st.session_state["last_company_query"] = company_query

articles = st.session_state["articles"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("事件數", f"{len(filtered):,}")
col2.metric("原始事件數", f"{len(events):,}")
col3.metric("公司新聞篇數", f"{len(articles):,}")
col4.metric("資料更新", "GDELT 15min")

tab_news, tab_company_map, tab_map, tab_table, tab_graph = st.tabs(["公司新聞", "公司新聞地圖", "事件地圖", "事件表", "關係圖"])

with tab_news:
    st.subheader("公司 / 財經新聞搜尋")
    st.caption("V5 版：公司新聞會保留英文標題並嘗試翻成中文；公司新聞地圖以新聞來源國家定位。")

    if articles.empty:
        st.info("尚未搜尋，或目前沒有查到公司新聞。若看到限流或非 JSON，請等 5～10 分鐘再查，先用單一關鍵字 NVIDIA。")
    else:
        st.success(f"查詢關鍵字：{st.session_state.get('last_company_query', '')}")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**來源網站 Top 10**")
            st.dataframe(
                articles["domain"].value_counts().head(10).reset_index().rename(
                    columns={"domain": "domain", "count": "articles"}
                ),
                use_container_width=True
            )

        with c2:
            st.markdown("**來源國家 Top 10**")
            st.dataframe(
                articles["source_country"].value_counts().head(10).reset_index().rename(
                    columns={"source_country": "source_country", "count": "articles"}
                ),
                use_container_width=True
            )

        st.markdown("### 最新文章")
        for _, row in articles.head(40).iterrows():
            title = html.escape(str(row.get("title", "")))
            title_zh = html.escape(str(row.get("title_zh", "")))
            url = str(row.get("url", ""))
            domain = html.escape(str(row.get("domain", "")))
            time_utc = row.get("time_utc", "")
            country = html.escape(str(row.get("source_country", "")))
            lang = html.escape(str(row.get("language", "")))

            if url.startswith("http"):
                st.markdown(f"**English：[{title}]({url})**")
            else:
                st.markdown(f"**English：{title}**")

            if title_zh:
                st.markdown(f"**中文：** {title_zh}")
            else:
                st.markdown("**中文：** 暫無翻譯或翻譯服務暫時不可用")

            st.caption(f"{time_utc}｜{domain}｜{country}｜{lang}")
            st.divider()

        st.markdown("### 表格")
        table_cols = ["time_utc", "title", "title_zh", "domain", "source_country", "language", "url"]
        st.dataframe(
            articles[[c for c in table_cols if c in articles.columns]],
            use_container_width=True
        )


with tab_company_map:
    st.subheader("公司新聞地圖")
    st.caption("這張地圖使用公司新聞的 source_country 定位，所以代表新聞來源國家，不一定是事件發生地點。")
    if articles.empty:
        st.info("請先到左側 B 區按「搜尋公司新聞」，查到文章後這裡才會出現公司新聞地圖。")
    else:
        company_map = build_company_news_map(articles)
        st_folium(company_map, width=None, height=680)

with tab_map:
    st.subheader("事件地圖")
    st.caption("這裡查的是 GDELT Event Database；比較適合戰爭、外交、抗議、攻擊、制裁，不一定會完整抓到公司財經新聞。")
    if filtered.empty:
        st.info("目前沒有符合條件的事件。若要查公司新聞，請切到「公司新聞」頁籤。")
    else:
        m = build_map(filtered.head(1000))
        st_folium(m, width=None, height=680)

with tab_table:
    st.subheader("事件明細")
    display_cols = [
        "event_time_utc", "who", "where", "what",
        "NumMentions", "NumArticles", "AvgTone", "GoldsteinScale", "source"
    ]
    if filtered.empty:
        st.info("目前沒有符合條件的事件。")
    else:
        st.dataframe(filtered[display_cols].head(1000), use_container_width=True)

with tab_graph:
    st.subheader("事件關係圖：人物 / 組織 ↔ 事件 ↔ 地點")
    if filtered.empty:
        st.info("目前沒有符合條件的事件。")
    else:
        graph_path = build_relationship_graph(filtered, max_events=80)
        with open(graph_path, "r", encoding="utf-8") as f:
            st.components.v1.html(f.read(), height=700, scrolling=True)
