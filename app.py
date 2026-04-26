import io
import html
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


@st.cache_data(ttl=900, show_spinner=False)
def search_company_news(query: str, timespan: str = "24h", max_records: int = 100) -> pd.DataFrame:
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

    try:
        r = requests.get(GDELT_DOC_API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
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


st.set_page_config(page_title="Global News Radar V2", layout="wide")
st.title("🌍 Global News Radar V2：全球事件地圖 + 公司新聞搜尋")

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
        value='NVIDIA OR NVDA OR "Jensen Huang"',
        help="查公司與財經新聞請用這個欄位，不要只用事件地圖的角色關鍵字。"
    )
    timespan = st.selectbox(
        "新聞時間範圍",
        options=["1h", "6h", "12h", "24h", "3d", "7d"],
        index=3
    )
    max_records = st.slider("最多新聞篇數", 10, 250, 100, step=10)

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

with st.spinner("正在搜尋公司 / 財經新聞..."):
    articles = search_company_news(company_query, timespan=timespan, max_records=max_records)

col1, col2, col3, col4 = st.columns(4)
col1.metric("事件數", f"{len(filtered):,}")
col2.metric("原始事件數", f"{len(events):,}")
col3.metric("公司新聞篇數", f"{len(articles):,}")
col4.metric("資料更新", "GDELT 15min")

tab_news, tab_map, tab_table, tab_graph = st.tabs(["公司新聞", "事件地圖", "事件表", "關係圖"])

with tab_news:
    st.subheader("公司 / 財經新聞搜尋")
    st.caption("這裡查 GDELT DOC API 文章清單，比事件地圖更適合 NVIDIA、NVDA、TSMC、Tesla 這類公司新聞。")

    if articles.empty:
        st.info("目前沒有查到公司新聞。可以放寬時間範圍，例如 24h → 3d，或改用 NVIDIA / NVDA / Jensen Huang 分別查。")
    else:
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
            url = str(row.get("url", ""))
            domain = html.escape(str(row.get("domain", "")))
            time_utc = row.get("time_utc", "")
            country = html.escape(str(row.get("source_country", "")))
            lang = html.escape(str(row.get("language", "")))

            if url.startswith("http"):
                st.markdown(f"**[{title}]({url})**")
            else:
                st.markdown(f"**{title}**")
            st.caption(f"{time_utc}｜{domain}｜{country}｜{lang}")
            st.divider()

        st.markdown("### 表格")
        st.dataframe(
            articles[["time_utc", "title", "domain", "source_country", "language", "url"]],
            use_container_width=True
        )

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
