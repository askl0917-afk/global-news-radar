import io
import html
import zipfile
from datetime import datetime, timezone

import folium
import networkx as nx
import pandas as pd
import requests
import streamlit as st
from folium.plugins import MarkerCluster
from pyvis.network import Network
from streamlit_folium import st_folium


# -----------------------------
# Global News Radar MVP
# Data source: GDELT 2.0 Event Database 15-minute export files
# Run:
#   pip install -r requirements.txt
#   streamlit run app.py
# -----------------------------

MASTER_FILE_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"

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

# CAMEO root event rough labels. You can replace this with the official CAMEO lookup table later.
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
    """Load latest GDELT 2.0 event export files.

    num_files=4 means roughly the latest hour because GDELT updates every 15 minutes.
    """
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
                    df["source_file"] = url.rsplit("/", 1)[-1]
                    frames.append(df)
        except Exception as exc:
            st.warning(f"讀取失敗：{url}；原因：{exc}")

    if not frames:
        return pd.DataFrame(columns=GDELT_COLUMNS)

    df = pd.concat(frames, ignore_index=True)

    # Numeric conversion
    numeric_cols = [
        "ActionGeo_Lat", "ActionGeo_Long", "GoldsteinScale",
        "NumMentions", "NumSources", "NumArticles", "AvgTone"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["event_time_utc"] = pd.to_datetime(
        df["DATEADDED"], format="%Y%m%d%H%M%S", errors="coerce", utc=True
    )

    # Keep geocoded, root events only to reduce noise
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

    # De-duplicate rough duplicates
    df = df.drop_duplicates(
        subset=["GlobalEventID", "SOURCEURL", "ActionGeo_Lat", "ActionGeo_Long"],
        keep="last"
    )

    return df.sort_values("event_time_utc", ascending=False)


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
    cluster = MarkerCluster(name="全球新聞事件").add_to(m)

    for _, row in df.iterrows():
        lat = row["ActionGeo_Lat"]
        lon = row["ActionGeo_Long"]

        # Negative Goldstein = more conflictual. Use marker color as quick visual hint.
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
    """Build a simple actor-event-location relationship graph.

    Nodes:
      actor, event, location
    Edges:
      actor -> event, event -> actor, event -> location
    """
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
    net.set_options("""
    var options = {
      "nodes": {
        "shape": "dot",
        "size": 14,
        "font": {"size": 14}
      },
      "edges": {
        "smooth": true
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -25000,
          "centralGravity": 0.2,
          "springLength": 120,
          "springConstant": 0.04
        },
        "minVelocity": 0.75
      }
    }
    """)

    html_path = "relationship_graph.html"
    net.save_graph(html_path)
    return html_path


st.set_page_config(page_title="Global News Radar MVP", layout="wide")
st.title("🌍 Global News Radar：全球即時事件地圖 MVP")

with st.sidebar:
    st.header("資料設定")
    num_files = st.slider("抓取最近幾個 15 分鐘檔案", 1, 12, 4)
    max_rows = st.slider("每個檔案最多讀取列數", 1000, 50000, 20000, step=1000)

    st.header("篩選")
    root_filter = st.multiselect(
        "事件大類",
        options=list(ROOT_EVENT_LABELS.values()),
        default=[]
    )
    country_filter = st.text_input("地點關鍵字，例如 Taiwan / Taipei / Israel")
    actor_filter = st.text_input("角色關鍵字，例如 Trump / China / NVIDIA")
    min_mentions = st.slider("最低提及次數 NumMentions", 0, 100, 0)

    st.caption("提示：紅色偏衝突，綠色偏合作；這只是 GDELT GoldsteinScale 的粗略視覺化。")

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
    ]

filtered = filtered[filtered["NumMentions"].fillna(0) >= min_mentions]

col1, col2, col3, col4 = st.columns(4)
col1.metric("事件數", f"{len(filtered):,}")
col2.metric("原始事件數", f"{len(events):,}")
col3.metric("最新時間 UTC", str(filtered["event_time_utc"].max()) if len(filtered) else "無")
col4.metric("資料更新", "GDELT 15min")

tab_map, tab_table, tab_graph = st.tabs(["地圖", "事件表", "關係圖"])

with tab_map:
    st.subheader("點擊地圖標記查看：誰、何時、何地、何事")
    if filtered.empty:
        st.info("目前沒有符合條件的事件。")
    else:
        m = build_map(filtered.head(1000))
        st_folium(m, width=None, height=680)

with tab_table:
    st.subheader("事件明細")
    display_cols = [
        "event_time_utc", "who", "where", "what",
        "NumMentions", "NumArticles", "AvgTone", "GoldsteinScale", "source"
    ]
    st.dataframe(filtered[display_cols].head(1000), use_container_width=True)

with tab_graph:
    st.subheader("事件關係圖：人物 / 組織 ↔ 事件 ↔ 地點")
    st.caption("第一版用 Actor1、Actor2、事件與地點建立關係。進階版可改用 LLM + GKG 做實體消歧與因果鏈。")
    if filtered.empty:
        st.info("目前沒有符合條件的事件。")
    else:
        graph_path = build_relationship_graph(filtered, max_events=80)
        with open(graph_path, "r", encoding="utf-8") as f:
            st.components.v1.html(f.read(), height=700, scrolling=True)
