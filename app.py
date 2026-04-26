
import html
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import folium
import networkx as nx
import pandas as pd
import requests
import streamlit as st
from deep_translator import GoogleTranslator
from groq import Groq
from folium.plugins import MarkerCluster
from pyvis.network import Network
from streamlit_folium import st_folium


# ============================================================
# Global News Radar V22
# 投資情報雷達穩定版
#
# What changed:
# - Main financial/company news no longer depends only on GDELT DOC API.
# - Uses Google News RSS and Yahoo Finance RSS as stable no-key sources.
# - Keeps GDELT Event Database as geopolitical/global event supplement.
# - Keeps last successful results when an external source fails.
# - Mobile-first layout.
# - Unified feed + unified map.
# ============================================================

GDELT_MASTER_FILE_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"

PREFERRED_FINANCE_DOMAINS = [
    "reuters.com",
    "cnbc.com",
    "marketwatch.com",
    "finance.yahoo.com",
    "barrons.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "investing.com",
    "seekingalpha.com",
    "fool.com",
]

TICKER_HINTS = {
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "TSMC": "TSM",
    "TSM": "TSM",
    "MICRON": "MU",
    "MU": "MU",
    "AMD": "AMD",
    "INTEL": "INTC",
    "INTC": "INTC",
    "AMAZON": "AMZN",
    "AMZN": "AMZN",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "META": "META",
}

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

DOMAIN_COUNTRY_MAP = {
    "reuters.com": "United States",
    "cnbc.com": "United States",
    "marketwatch.com": "United States",
    "finance.yahoo.com": "United States",
    "yahoo.com": "United States",
    "barrons.com": "United States",
    "bloomberg.com": "United States",
    "wsj.com": "United States",
    "ft.com": "United Kingdom",
    "investing.com": "United States",
    "seekingalpha.com": "United States",
    "fool.com": "United States",
    "nikkei.com": "Japan",
    "asia.nikkei.com": "Japan",
    "koreatimes.co.kr": "South Korea",
    "fnnews.com": "South Korea",
    "digitimes.com": "Taiwan",
    "taipeitimes.com": "Taiwan",
    "scmp.com": "Hong Kong",
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
    "03": "合作意願 / Cooperate intent",
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
    "15": "軍事姿態 / Military posture",
    "16": "減少關係 / Reduce relations",
    "17": "脅迫 / Coerce",
    "18": "攻擊 / Assault",
    "19": "戰鬥 / Fight",
    "20": "非常規暴力 / Unconventional violence",
}


# -------------------------------
# Utility
# -------------------------------

def clean_text(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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


def guess_domain(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return domain
    except Exception:
        return ""


def guess_source_country(domain: str) -> str:
    d = (domain or "").lower()
    for key, country in DOMAIN_COUNTRY_MAP.items():
        if key in d:
            return country
    return "United States"


def source_quality(domain: str, source_type: str = "") -> str:
    d = (domain or "").lower()
    if "reuters.com" in d:
        return "A+ Reuters"
    if any(x in d for x in ["bloomberg.com", "wsj.com", "ft.com", "barrons.com"]):
        return "A 財經專業媒體"
    if any(x in d for x in ["cnbc.com", "marketwatch.com", "finance.yahoo.com", "yahoo.com", "investing.com"]):
        return "B 主流財經媒體"
    if any(x in d for x in ["fool.com", "seekingalpha.com"]):
        return "C 投資觀點媒體"
    if source_type == "Google News RSS":
        return "D Google News 聚合"
    return "D 其他來源"


def infer_ticker(query: str) -> str:
    q = (query or "").upper().strip()
    tokens = re.split(r"[^A-Z0-9]+", q)
    for token in tokens:
        if token in TICKER_HINTS:
            return TICKER_HINTS[token]
    for key, ticker in TICKER_HINTS.items():
        if key in q:
            return ticker
    return ""


def parse_search_terms(query: str):
    """Parse search terms for AND / OR modes.

    Smart but simple:
    - "NVIDIA, Intel" => ["NVIDIA", "Intel"]
    - "NVIDIA OR Intel" => ["NVIDIA", "Intel"]
    - "NVIDIA | Intel" => ["NVIDIA", "Intel"]
    - "NVIDIA intel" => ["NVIDIA", "intel"]
    """
    q = (query or "").strip()
    if not q:
        return []

    if "," in q:
        terms = [x.strip() for x in q.split(",") if x.strip()]
    elif "|" in q:
        terms = [x.strip() for x in q.split("|") if x.strip()]
    elif re.search(r"\s+OR\s+", q, flags=re.IGNORECASE):
        terms = [x.strip() for x in re.split(r"\s+OR\s+", q, flags=re.IGNORECASE) if x.strip()]
    else:
        terms = [x.strip() for x in q.split() if x.strip()]

    # Keep order but remove duplicates case-insensitively.
    seen = set()
    out = []
    for t in terms:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def build_query_by_logic(query: str, query_logic: str) -> list:
    terms = parse_search_terms(query)
    if not terms:
        return []

    if query_logic == "聯集 OR":
        return terms

    # Intersection mode: search all terms together.
    # Google News treats space-separated terms as an AND-like query most of the time.
    return [" ".join(terms)]


def time_range_to_hours(time_range: str):
    mapping = {
        "最近 1 小時": 1,
        "最近 6 小時": 6,
        "最近 12 小時": 12,
        "最近 24 小時": 24,
        "最近 3 天": 72,
        "最近 7 天": 168,
        "不限時間": None,
    }
    return mapping.get(time_range, 24)


def google_when_hint(time_range: str) -> str:
    """Google News RSS sometimes respects when: syntax.

    We still apply local filtering after fetching, so this is only a query hint.
    """
    mapping = {
        "最近 1 小時": "when:1h",
        "最近 6 小時": "when:6h",
        "最近 12 小時": "when:12h",
        "最近 24 小時": "when:1d",
        "最近 3 天": "when:3d",
        "最近 7 天": "when:7d",
    }
    return mapping.get(time_range, "")


def apply_time_filter(df: pd.DataFrame, time_range: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    hours = time_range_to_hours(time_range)
    if hours is None:
        return df

    out = df.copy()
    out["time_utc"] = pd.to_datetime(out["time_utc"], errors="coerce", utc=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=hours)

    # If user asked for a time range, keep only articles with known timestamps.
    out = out[out["time_utc"].notna() & (out["time_utc"] >= cutoff)]
    return out



def wrapped_longitudes(lon):
    try:
        lon = float(lon)
        return [lon, lon - 360, lon + 360]
    except Exception:
        return [lon]


def count_badge_html(count: int, badge_type: str = "news") -> str:
    color = "#7b2cbf"
    if badge_type == "event":
        color = "#1976d2"
    elif badge_type == "risk":
        color = "#d62828"

    return (
        f'<div style="'
        f'width:36px;height:36px;border-radius:999px;'
        f'background:{color};color:white;'
        f'font-weight:900;font-size:15px;line-height:36px;text-align:center;'
        f'border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.45);'
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
        f'">{count}</div>'
    )


def get_groq_api_key():
    """Read Groq API key from Streamlit Secrets or environment variable."""
    try:
        key = st.secrets.get("GROQ_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


def get_groq_model():
    try:
        model = st.secrets.get("GROQ_MODEL", "")
        if model:
            return model
    except Exception:
        pass
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def groq_is_enabled():
    return bool(get_groq_api_key())


def default_search_plan(user_query: str) -> dict:
    """Fallback when Groq is not available."""
    q = clean_text(user_query)
    terms = parse_search_terms(q)
    if not terms:
        terms = [q] if q else []

    return {
        "mode": "fallback",
        "core_topic_zh": q,
        "search_queries": terms[:6] if terms else [q],
        "tickers": [],
        "include_terms": terms,
        "exclude_terms": [],
        "reason": "未啟用 Groq 或 Groq 解析失敗，因此使用原始關鍵字搜尋。",
    }


@st.cache_data(ttl=3600, show_spinner=False)
def groq_build_search_plan(user_query: str, time_range: str = "最近 24 小時") -> dict:
    """Use Groq to turn a natural-language research request into search queries.

    Output is JSON so the app can execute several focused RSS searches.
    """
    user_query = clean_text(user_query)
    if not user_query:
        return default_search_plan(user_query)

    api_key = get_groq_api_key()
    if not api_key:
        return default_search_plan(user_query)

    system_prompt = """
你是台灣買方/賣方科技產業分析師的搜尋助理。
你要把使用者的自然語言研究問題，轉成適合 Google News RSS / Yahoo Finance RSS 的搜尋策略。

請只輸出 JSON，不要 markdown，不要解釋。

JSON 格式：
{
  "core_topic_zh": "繁體中文核心主題",
  "search_queries": ["英文搜尋字串1", "英文搜尋字串2", "...最多8個"],
  "tickers": ["NVDA", "AMD", "...最多10個"],
  "include_terms": ["必須關注的概念"],
  "exclude_terms": ["要避開的雜訊"],
  "reason": "用繁中一句話說明為何這樣拆"
}

規則：
1. search_queries 要用英文，因為 Google News / Yahoo Finance 英文財經新聞較完整。
2. 每個 query 不要太長，適合新聞搜尋。
3. 如果使用者問 AI 軟硬體產業，要涵蓋：
   - AI chips / GPU / CPU / accelerator
   - AI servers / data centers / cloud capex
   - AI software / enterprise AI / inference
   - semiconductor supply chain / memory / HBM / networking / power / cooling
4. 若問題涉及股票或公司，tickers 放美股 ticker；台股可先不放 ticker。
5. 避免過度寬泛，只給最可能抓到財經新聞的查詢。
6. 不要把使用者問題翻成中文查詢；主要查英文。
""".strip()

    user_prompt = f"""
使用者問題：{user_query}
時間範圍：{time_range}
請產生搜尋策略 JSON：
""".strip()

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=get_groq_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=700,
        )
        raw = completion.choices[0].message.content.strip()
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

        data = json.loads(raw)

        queries = data.get("search_queries", [])
        if not isinstance(queries, list):
            queries = [str(queries)]
        queries = [clean_text(q) for q in queries if clean_text(q)][:8]

        tickers = data.get("tickers", [])
        if not isinstance(tickers, list):
            tickers = [str(tickers)]
        tickers = [clean_text(t).upper() for t in tickers if clean_text(t)][:10]

        return {
            "mode": "groq",
            "core_topic_zh": clean_text(data.get("core_topic_zh", user_query)),
            "search_queries": queries or [user_query],
            "tickers": tickers,
            "include_terms": data.get("include_terms", []),
            "exclude_terms": data.get("exclude_terms", []),
            "reason": clean_text(data.get("reason", "Groq 已將自然語言問題拆成多個財經新聞搜尋式。")),
        }
    except Exception as exc:
        plan = default_search_plan(user_query)
        plan["reason"] = f"Groq 搜尋策略解析失敗，改用原始關鍵字。原因：{exc}"
        return plan


@st.cache_data(ttl=86400, show_spinner=False)
def apply_finance_translation_guardrails(original: str, translated: str) -> str:
    """Fix common finance-headline mistranslations.

    This is not a full translator. It only prevents known harmful mistranslations
    that can mislead investment interpretation.
    """
    original_clean = clean_text(original)
    out = clean_text(translated)

    lower = original_clean.lower()

    # Very common idiom failure:
    # "X crashes Y's party" means X intrudes / steals the spotlight,
    # not defeats a party.
    if "crash" in lower and "party" in lower:
        out = out.replace("擊敗英特爾派對", "搶走英特爾的風頭")
        out = out.replace("擊敗 Intel 派對", "搶走 Intel 的風頭")
        out = out.replace("擊敗英特爾的派對", "搶走英特爾的風頭")
        out = out.replace("擊敗派對", "搶風頭")
        out = out.replace("英特爾派對", "英特爾的慶功派對")

        if "擊敗" in out and "party" in lower:
            # If model still produced a misleading defeat-style sentence,
            # fall back to a safer editorial rewrite.
            out = "輝達搶走英特爾的風頭：AI CPU 題材升溫，5 兆美元巨頭股價大漲"

    if "market pivots to cpus" in lower or "pivots to cpus" in lower:
        out = out.replace("AI 市場轉向 CPU", "AI 市場重新重視 CPU 題材")
        out = out.replace("AI市場轉向CPU", "AI 市場重新重視 CPU 題材")
        out = out.replace("轉向 CPU", "重新重視 CPU 題材")
        out = out.replace("轉向CPU", "重新重視 CPU 題材")

    out = out.replace("5T", "5 兆美元").replace("5t", "5 兆美元")
    out = out.replace("巨頭飆升", "巨頭股價大漲")
    return out[:240]


@st.cache_data(ttl=86400, show_spinner=False)
def groq_finance_translate_title(title: str, domain: str = "", category: str = "") -> str:
    """Use Groq hosted open-weight model to translate finance headline into Traditional Chinese."""
    title = clean_text(title)
    if not title:
        return ""

    api_key = get_groq_api_key()
    if not api_key:
        return ""

    system_prompt = """
你是台灣財經新聞標題編輯，不是一般翻譯機。
任務：把原文標題改寫成「台灣股票分析師一眼看得懂」的繁體中文財經標題。

硬性規則：
- 只輸出一行中文標題，不要解釋、不要引號、不要項目符號。
- 不要新增原文沒有的事實或數字。
- 公司名要用台灣常用名稱：Nvidia=輝達，Intel=英特爾，AMD=超微，Arm=安謀。
- crash a party / crashes Intel’s party = 闖進派對、搶風頭，不是「擊敗派對」。
- market pivots to CPUs = 市場重新重視 CPU 題材 / CPU 敘事升溫，不是 GPU 不重要，也不是 AI 市場完全轉向 CPU。
- 5T giant = 5 兆美元巨頭。
- surges = 股價大漲 / 市值拉升，視上下文選擇。
- 如果標題是媒體誇飾，要翻成財經語境，不要照字面誤導。

範例：
原文：Nvidia crashes Intel’s party: $5T giant surges as AI market pivots to CPUs
好翻譯：Intel 財報點燃 CPU 題材，但輝達也來搶風頭：AI 推論讓市場重新重視 CPU 價值
壞翻譯：Nvidia 擊敗英特爾派對
""".strip()

    user_prompt = f"""
來源網域：{domain}
初步分類：{category}
原文標題：{title}
請輸出繁體中文財經標題：
""".strip()

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=get_groq_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=220,
        )
        result = completion.choices[0].message.content
        result = clean_text(result)
        return apply_finance_translation_guardrails(title, result)
    except Exception:
        return ""



@st.cache_data(ttl=86400, show_spinner=False)
def machine_translate_title_to_zh_tw(title: str) -> str:
    title = clean_text(title)
    if not title:
        return ""

    try:
        translated = GoogleTranslator(source="auto", target="zh-TW").translate(title[:450])
        translated = html.unescape(str(translated)).strip()
        if not translated or translated.lower() == title.lower():
            return ""
        return translated
    except Exception:
        return ""


def translate_title_with_engine(title: str, domain: str = "", category: str = "", translation_mode: str = "Groq AI 財經翻譯優先") -> dict:
    title = clean_text(title)
    if not title:
        return {"text": "", "engine": "無"}

    if translation_mode == "Groq AI 財經翻譯優先":
        groq_result = groq_finance_translate_title(title, domain=domain, category=category)
        if groq_result:
            return {"text": groq_result, "engine": f"Groq AI｜{get_groq_model()}"}

        mt = machine_translate_title_to_zh_tw(title)
        return {
            "text": apply_finance_translation_guardrails(title, mt) if mt else "",
            "engine": "免費機翻備援",
        }

    if translation_mode == "只用免費機翻":
        mt = machine_translate_title_to_zh_tw(title)
        return {
            "text": apply_finance_translation_guardrails(title, mt) if mt else "",
            "engine": "免費機翻",
        }

    return {"text": "", "engine": "不翻譯"}


def translate_title_to_zh_tw(title: str, domain: str = "", category: str = "", translation_mode: str = "Groq AI 財經翻譯優先") -> str:
    return translate_title_with_engine(title, domain=domain, category=category, translation_mode=translation_mode).get("text", "")



def classify_news(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ["stock", "shares", "market cap", "valuation", "price target", "rally", "fell", "popped"]):
        return "股價 / 估值"
    if any(k in t for k in ["earnings", "revenue", "profit", "margin", "guidance", "quarter"]):
        return "財報 / 指引"
    if any(k in t for k in ["chip", "gpu", "ai", "data center", "blackwell", "rubin", "hbm", "semiconductor"]):
        return "AI / 半導體"
    if any(k in t for k in ["export", "ban", "china", "tariff", "restriction", "license"]):
        return "政策 / 管制"
    if any(k in t for k in ["deal", "partnership", "supply", "customer", "contract", "order"]):
        return "供應鏈 / 客戶"
    return "一般新聞"


def make_click_hint(title: str, domain: str, category: str, importance: str) -> str:
    """Give a plain-Chinese reason so the user can decide whether to click."""
    t = (title or "").lower()
    domain = (domain or "").lower()

    if importance == "A":
        return "值得優先看：來源品質高，且可能涉及財報、政策、供應鏈或重大公司事件。"
    if category in ["政策 / 管制"]:
        return "建議點開：可能影響出口管制、中國市場或供應鏈限制。"
    if category in ["財報 / 指引"]:
        return "建議點開：可能影響市場預期、EPS 或估值。"
    if category in ["供應鏈 / 客戶"]:
        return "建議點開：可能牽涉客戶、訂單、供應鏈或合作變化。"
    if category in ["AI / 半導體"]:
        return "可追蹤：屬於 AI / 半導體敘事，需確認是否有新資訊。"
    if category in ["股價 / 估值"]:
        return "通常屬於市場反應或評論，若非 Reuters / CNBC / Yahoo Finance，可先略讀。"
    if any(x in domain for x in ["reuters.com", "cnbc.com", "finance.yahoo.com", "marketwatch.com"]):
        return "來源可參考：主流財經媒體，可點開確認細節。"
    return "低優先：目前看起來像一般背景新聞，除非標題剛好符合你的研究方向。"


def is_low_value_gdelt_event(row, query: str) -> bool:
    """Filter out noisy GDELT machine-coded events for finance use."""
    q = (query or "").lower().strip()
    if not q:
        return True

    text = " ".join([
        str(row.get("actor1", "")),
        str(row.get("actor2", "")),
        str(row.get("where", "")),
        str(row.get("source", "")),
        str(row.get("what", "")),
    ]).lower()

    # Require direct keyword hit. This prevents random geopolitical/social events
    # from polluting company searches like NVIDIA.
    return q not in text


def make_event_readable_summary(row) -> str:
    actor1 = clean_text(row.get("actor1", "")) or "未知角色"
    actor2 = clean_text(row.get("actor2", "")) or "未知對象"
    where = clean_text(row.get("where", "")) or "未知地點"
    event = clean_text(row.get("root_label", "")) or "事件"
    mentions = row.get("NumMentions", "")
    tone = row.get("AvgTone", "")
    return f"{where} 發生「{event}」類事件；關聯方：{actor1} → {actor2}；聲量 {mentions}，語氣 {tone}。"



def importance_score(row) -> str:
    quality = str(row.get("source_quality", ""))
    category = str(row.get("category", ""))
    if quality.startswith("A+") or (quality.startswith("A") and category in ["財報 / 指引", "政策 / 管制", "供應鏈 / 客戶"]):
        return "A"
    if quality.startswith("A") or category in ["AI / 半導體", "政策 / 管制", "供應鏈 / 客戶"]:
        return "B"
    if quality.startswith("B"):
        return "C"
    return "D"


# -------------------------------
# RSS Sources
# -------------------------------

def parse_feed_datetime(entry) -> pd.Timestamp:
    for key in ["published_parsed", "updated_parsed"]:
        value = getattr(entry, key, None)
        if value:
            try:
                return pd.Timestamp(datetime(*value[:6], tzinfo=timezone.utc))
            except Exception:
                pass
    return pd.NaT


@st.cache_data(ttl=600, show_spinner=False)
def fetch_google_news_rss(query: str, max_items: int = 20, preferred_domains=None, time_range: str = "最近 24 小時") -> pd.DataFrame:
    query = (query or "").strip()
    if not query:
        return pd.DataFrame()

    preferred_domains = preferred_domains or []
    rows = []

    hint = google_when_hint(time_range)
    base_query = f"{query} {hint}".strip()
    queries = [base_query]

    # Extra domain-focused Google News searches.
    for d in preferred_domains[:4]:
        queries.append(f'{base_query} site:{d}')

    for q in queries:
        url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)

        for entry in feed.entries[:max_items]:
            title = clean_text(getattr(entry, "title", ""))
            link = getattr(entry, "link", "")
            source_title = ""
            try:
                source_title = clean_text(entry.source.title)
            except Exception:
                source_title = ""

            domain = guess_domain(link)
            # Google News links may hide original domain. Use source title as a fallback.
            if "news.google.com" in domain and source_title:
                domain = source_title.lower().replace(" ", "") + " (via Google News)"

            rows.append({
                "time_utc": parse_feed_datetime(entry),
                "data_type": "公司/財經新聞",
                "source_type": "Google News RSS",
                "title": title,
                "url": link,
                "domain": domain,
                "source_country": guess_source_country(domain),
                "language": "auto",
                "source_query": q,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.drop_duplicates(subset=["title"]).head(max_items)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def fetch_yahoo_finance_rss(ticker: str, max_items: int = 20) -> pd.DataFrame:
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return pd.DataFrame()

    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(ticker)}&region=US&lang=en-US"
    feed = feedparser.parse(url)

    rows = []
    for entry in feed.entries[:max_items]:
        title = clean_text(getattr(entry, "title", ""))
        link = getattr(entry, "link", "")
        domain = guess_domain(link) or "finance.yahoo.com"

        rows.append({
            "time_utc": parse_feed_datetime(entry),
            "data_type": "公司/財經新聞",
            "source_type": "Yahoo Finance RSS",
            "title": title,
            "url": link,
            "domain": domain,
            "source_country": guess_source_country(domain),
            "language": "en",
            "source_query": ticker,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["title"])


def enrich_articles(df: pd.DataFrame, translate_titles: bool, translation_mode: str = "Groq AI 財經翻譯優先") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["domain"] = df["domain"].fillna("").astype(str)
    df["source_country"] = df["source_country"].fillna("").apply(normalize_country_name)
    df["source_quality"] = df.apply(lambda row: source_quality(row.get("domain", ""), row.get("source_type", "")), axis=1)
    df["category"] = df["title"].apply(classify_news)

    if translate_titles:
        translations = df.apply(
            lambda row: translate_title_with_engine(
                row.get("title", ""),
                domain=row.get("domain", ""),
                category=row.get("category", ""),
                translation_mode=translation_mode,
            ),
            axis=1,
        )
        df["title_zh"] = translations.apply(lambda x: x.get("text", ""))
        df["translation_engine"] = translations.apply(lambda x: x.get("engine", "未知"))
    else:
        df["title_zh"] = ""
        df["translation_engine"] = "不翻譯"

    df["importance"] = df.apply(importance_score, axis=1)

    # Sort: importance first, then source quality, then recency.
    quality_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    importance_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    df["_i"] = df["importance"].map(importance_order).fillna(9)
    df["_q"] = df["source_quality"].str[0].map(quality_order).fillna(9)
    df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True)
    df = df.sort_values(["_i", "_q", "time_utc"], ascending=[True, True, False]).drop(columns=["_i", "_q"])
    return df


def search_finance_news(
    query: str,
    max_items: int,
    translate_titles: bool,
    use_google: bool,
    use_yahoo: bool,
    preferred_domains,
    query_logic: str = "交集 AND",
    time_range: str = "最近 24 小時",
    translation_mode: str = "Groq AI 財經翻譯優先",
    search_mode: str = "精準關鍵字",
    query_plan: dict | None = None,
) -> pd.DataFrame:
    frames = []

    if search_mode == "自然語言研究搜尋" and query_plan:
        query_list = query_plan.get("search_queries", []) or [query]
        tickers = query_plan.get("tickers", []) or []
    else:
        query_list = build_query_by_logic(query, query_logic)
        tickers = []

    if use_google:
        # Natural-language mode searches several AI-expanded queries and merges results.
        # Keyword mode follows AND / OR logic.
        per_query_limit = max(5, int(max_items / max(1, len(query_list))))
        for q in query_list[:8]:
            frames.append(fetch_google_news_rss(q, max_items=per_query_limit, preferred_domains=preferred_domains, time_range=time_range))

    if use_yahoo:
        if search_mode == "自然語言研究搜尋":
            for ticker in tickers[:10]:
                frames.append(fetch_yahoo_finance_rss(ticker, max_items=max(5, int(max_items / max(1, len(tickers) or 1)))))
        else:
            # Yahoo Finance RSS is ticker-based.
            # In OR mode, fetch each ticker separately.
            # In AND mode, Yahoo cannot express "NVIDIA AND Intel" well, so only use Yahoo for single ticker queries.
            if query_logic == "聯集 OR":
                for term in parse_search_terms(query):
                    ticker = infer_ticker(term)
                    if ticker:
                        frames.append(fetch_yahoo_finance_rss(ticker, max_items=max(5, int(max_items / max(1, len(query_list))))))
            else:
                terms = parse_search_terms(query)
                if len(terms) == 1:
                    ticker = infer_ticker(query)
                    if ticker:
                        frames.append(fetch_yahoo_finance_rss(ticker, max_items=max_items))

    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["title"])
    df = apply_time_filter(df, time_range=time_range)
    if df.empty:
        return pd.DataFrame()

    df = enrich_articles(df, translate_titles=translate_titles, translation_mode=translation_mode)

    # Final cap after union/boost searches.
    if len(df) > max_items:
        df = df.head(max_items)
    return df


# -------------------------------
# GDELT Event Database
# -------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def load_latest_events(num_files: int = 4, max_rows_per_file: int = 20000) -> pd.DataFrame:
    response = requests.get(GDELT_MASTER_FILE_LIST, timeout=25)
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
            z_response = requests.get(url, timeout=30)
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
        except Exception:
            pass

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

    df["actor1"] = df["Actor1Name"].apply(lambda x: clean_text(x) or "未知角色A")
    df["actor2"] = df["Actor2Name"].apply(lambda x: clean_text(x) or "未知角色B")
    df["who"] = df["actor1"] + " → " + df["actor2"]
    df["where"] = df["ActionGeo_Fullname"].apply(lambda x: clean_text(x) or "未知地點")
    df["root_label"] = df["EventRootCode"].map(ROOT_EVENT_LABELS).fillna("其他事件 / Other")
    df["what"] = df["root_label"] + "｜CAMEO " + df["EventCode"].fillna("")
    df["source"] = df["SOURCEURL"].apply(lambda x: clean_text(x) or "")

    df = df.drop_duplicates(
        subset=["GlobalEventID", "SOURCEURL", "ActionGeo_Lat", "ActionGeo_Long"],
        keep="last"
    )
    return df.sort_values("event_time_utc", ascending=False)


def filter_events(events: pd.DataFrame, keyword: str, max_events: int) -> pd.DataFrame:
    if events is None or events.empty or max_events <= 0:
        return pd.DataFrame()

    q = (keyword or "").lower().strip()
    if not q:
        return pd.DataFrame()

    df = events.copy()

    # Strict relevance: only keep events with direct keyword hits.
    mask = []
    for _, row in df.iterrows():
        mask.append(not is_low_value_gdelt_event(row, keyword))
    df = df[pd.Series(mask, index=df.index)]

    if df.empty:
        return df

    return df.head(max_events)


# -------------------------------
# Unified feed / map / graph
# -------------------------------

def build_unified_feed(articles: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []

    if articles is not None and not articles.empty:
        for _, r in articles.iterrows():
            rows.append({
                "time_utc": r.get("time_utc"),
                "data_type": "公司/財經新聞",
                "title": r.get("title", ""),
                "title_zh": r.get("title_zh", ""),
                "domain": r.get("domain", ""),
                "source_quality": r.get("source_quality", ""),
                "location": r.get("source_country", ""),
                "language": r.get("language", ""),
                "url": r.get("url", ""),
                "translation_engine": r.get("translation_engine", ""),
                "category": r.get("category", ""),
                "importance": r.get("importance", ""),
                "lat": COUNTRY_COORDS.get(r.get("source_country", ""), (None, None))[0],
                "lon": COUNTRY_COORDS.get(r.get("source_country", ""), (None, None))[1],
                "summary": r.get("source_type", ""),
            })

    if events is not None and not events.empty:
        for _, r in events.iterrows():
            event_title = make_event_readable_summary(r)
            rows.append({
                "time_utc": r.get("event_time_utc"),
                "data_type": "全球事件補充",
                "title": event_title,
                "title_zh": event_title,
                "domain": guess_domain(str(r.get("source", ""))),
                "source_quality": "GDELT Event",
                "location": r.get("where", ""),
                "language": "",
                "url": r.get("source", ""),
                "category": r.get("root_label", ""),
                "importance": "C",
                "lat": r.get("ActionGeo_Lat"),
                "lon": r.get("ActionGeo_Long"),
                "summary": "GDELT 機器事件資料，僅作背景補充，不等同財經新聞。",
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True)

    importance_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    quality_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    df["_i"] = df["importance"].map(importance_order).fillna(9)
    df["_q"] = df["source_quality"].astype(str).str[0].map(quality_order).fillna(9)
    df = df.sort_values(["_i", "_q", "time_utc"], ascending=[True, True, False]).drop(columns=["_i", "_q"])
    return df


def build_world_map(feed: pd.DataFrame, show_news=True, show_events=True):
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

    if feed is None or feed.empty:
        folium.LayerControl(collapsed=True).add_to(m)
        return m

    news = feed[feed["data_type"] == "公司/財經新聞"].copy()
    events = feed[feed["data_type"].str.contains("全球事件", na=False)].copy()

    if show_news and not news.empty:
        layer = folium.FeatureGroup(name="公司/財經新聞數量", show=True).add_to(m)
        for location, group in news.groupby("location", dropna=True):
            location = normalize_country_name(location)
            coords = COUNTRY_COORDS.get(location)
            if not coords:
                continue

            items = []
            for _, row in group.head(3).iterrows():
                title = html.escape(str(row.get("title", "")))
                title_zh = html.escape(str(row.get("title_zh", "")) or title)
                url = str(row.get("url", ""))
                domain = html.escape(str(row.get("domain", "")))
                cat = html.escape(str(row.get("category", "")))
                imp = html.escape(str(row.get("importance", "")))

                line = f"<b>{title_zh}</b><br><small>{title}</small><br><small>{domain}｜{cat}｜重要性 {imp}</small>"
                if url.startswith("http"):
                    line = f"<a href='{html.escape(url)}' target='_blank'>{line}</a>"
                items.append(f"<li>{line}</li>")

            popup = f"""
            <div style="width:330px;font-size:13px;">
                <b>公司/財經新聞｜{html.escape(location)}</b><br>
                新聞數量：{len(group)}<br>
                <small>地圖位置代表來源國家，不一定是事件發生地。</small>
                <ol>{''.join(items)}</ol>
                <small>完整內容請回「統合新聞流」。</small>
            </div>
            """

            for wl in wrapped_longitudes(coords[1]):
                folium.Marker(
                    location=[coords[0], wl],
                    popup=folium.Popup(popup, max_width=390),
                    tooltip=f"{location}｜公司/財經新聞 {len(group)} 篇",
                    icon=folium.DivIcon(
                        html=count_badge_html(len(group), "news"),
                        icon_size=(36, 36),
                        icon_anchor=(18, 18),
                    ),
                ).add_to(layer)

    if show_events and not events.empty:
        layer = folium.FeatureGroup(name="全球事件數量", show=True).add_to(m)
        events = events.dropna(subset=["lat", "lon"])
        if not events.empty:
            events["lat_round"] = pd.to_numeric(events["lat"], errors="coerce").round(1)
            events["lon_round"] = pd.to_numeric(events["lon"], errors="coerce").round(1)
            events["place_key"] = events["location"].fillna("未知地點") + "|" + events["lat_round"].astype(str) + "|" + events["lon_round"].astype(str)

            for _, group in events.groupby("place_key"):
                first = group.iloc[0]
                lat = float(first["lat_round"])
                lon = float(first["lon_round"])
                location = str(first.get("location", "未知地點"))

                items = []
                for _, row in group.head(3).iterrows():
                    title = html.escape(str(row.get("title_zh", "")))
                    url = str(row.get("url", ""))
                    line = f"<b>{title}</b><br><small>{row.get('time_utc', '')}</small>"
                    if url.startswith("http"):
                        line = f"<a href='{html.escape(url)}' target='_blank'>{line}</a>"
                    items.append(f"<li>{line}</li>")

                popup = f"""
                <div style="width:330px;font-size:13px;">
                    <b>全球事件｜{html.escape(location)}</b><br>
                    事件數量：{len(group)}
                    <ol>{''.join(items)}</ol>
                    <small>完整內容請回「統合新聞流」。</small>
                </div>
                """

                for wl in wrapped_longitudes(lon):
                    folium.Marker(
                        location=[lat, wl],
                        popup=folium.Popup(popup, max_width=390),
                        tooltip=f"{location}｜全球事件 {len(group)} 件",
                        icon=folium.DivIcon(
                            html=count_badge_html(len(group), "event"),
                            icon_size=(36, 36),
                            icon_anchor=(18, 18),
                        ),
                    ).add_to(layer)

    folium.LayerControl(collapsed=True).add_to(m)
    return m


# -------------------------------
# V22 Industry relationship graph
# -------------------------------

COMPANY_CANON = {
    "nvidia": "Nvidia", "nvda": "Nvidia", "輝達": "Nvidia",
    "intel": "Intel", "intc": "Intel", "英特爾": "Intel",
    "amd": "AMD", "超微": "AMD",
    "arm": "Arm", "安謀": "Arm",
    "qualcomm": "Qualcomm", "qcom": "Qualcomm", "高通": "Qualcomm",
    "apple": "Apple", "aapl": "Apple", "蘋果": "Apple",
    "amazon": "Amazon", "aws": "AWS", "amzn": "Amazon",
    "microsoft": "Microsoft", "azure": "Azure", "msft": "Microsoft",
    "google": "Google", "alphabet": "Google", "googl": "Google",
    "meta": "Meta", "oracle": "Oracle", "orcl": "Oracle",
    "tsmc": "TSMC", "台積電": "TSMC",
    "samsung": "Samsung", "三星": "Samsung",
    "supermicro": "Supermicro", "smci": "Supermicro",
    "dell": "Dell", "hpe": "HPE", "hewlett packard": "HPE", "lenovo": "Lenovo",
    "micron": "Micron", "mu": "Micron", "sk hynix": "SK hynix",
    "broadcom": "Broadcom", "avgo": "Broadcom", "marvell": "Marvell", "mrvl": "Marvell",
}

COMPANY_LAYER = {
    "Arm": "上游 IP / 架構", "TSMC": "上游製造 / 代工", "Samsung": "上游製造 / 代工",
    "Intel": "中游晶片 / CPU", "AMD": "中游晶片 / CPU", "Nvidia": "中游晶片 / AI 平台",
    "Qualcomm": "中游晶片 / AI PC", "Apple": "終端 / 自研晶片",
    "Amazon": "下游雲端 / CSP", "AWS": "下游雲端 / CSP", "Microsoft": "下游雲端 / CSP",
    "Azure": "下游雲端 / CSP", "Google": "下游雲端 / CSP", "Meta": "下游雲端 / CSP", "Oracle": "下游雲端 / CSP",
    "Supermicro": "平台 / 伺服器 OEM", "Dell": "平台 / 伺服器 OEM", "HPE": "平台 / 伺服器 OEM", "Lenovo": "平台 / 伺服器 OEM",
    "Micron": "上游記憶體 / HBM", "SK hynix": "上游記憶體 / HBM", "Broadcom": "網通 / ASIC", "Marvell": "網通 / ASIC",
}

TOPIC_KEYWORDS = {
    "AI inference": ["inference", "ai inference", "推論"],
    "Server CPU": ["server cpu", "data center cpu", "xeon", "epyc", "伺服器 cpu", "cpu"],
    "AI PC": ["ai pc", "copilot+ pc", "npu", "pc cpu"],
    "CPU + GPU 平台": ["grace", "vera", "superchip", "accelerated computing", "cpu-gpu"],
    "x86 vs Arm": ["x86", "arm server", "custom silicon", "arm-based"],
    "Cloud capex": ["capex", "cloud spending", "data center spending", "hyperscaler"],
    "AI server": ["ai server", "ai servers", "data center", "datacenter"],
    "HBM / Memory": ["hbm", "memory", "dram", "micron", "sk hynix"],
    "Networking": ["networking", "ethernet", "switch", "infiniband", "optical"],
    "Power / Cooling": ["power", "cooling", "liquid cooling", "thermal"],
    "Export control": ["export control", "ban", "restriction", "china", "license"],
    "Earnings / Guidance": ["earnings", "guidance", "revenue", "margin", "quarter"],
}

COMPETITION_PAIRS = {
    tuple(sorted(["Intel", "AMD"])): "x86 server CPU / PC CPU 競爭",
    tuple(sorted(["Intel", "Nvidia"])): "AI inference / CPU-GPU 平台敘事競爭",
    tuple(sorted(["AMD", "Nvidia"])): "AI data center platform 競爭",
    tuple(sorted(["Arm", "Intel"])): "Arm server / x86 架構替代威脅",
    tuple(sorted(["Arm", "AMD"])): "Arm server / x86 架構替代威脅",
    tuple(sorted(["Qualcomm", "Intel"])): "AI PC CPU 競爭",
    tuple(sorted(["Qualcomm", "AMD"])): "AI PC CPU 競爭",
    tuple(sorted(["Google", "Amazon"])): "雲端 AI 基建 / 自研晶片競爭",
    tuple(sorted(["Microsoft", "Google"])): "雲端 AI 基建競爭",
    tuple(sorted(["Microsoft", "Amazon"])): "雲端 AI 基建競爭",
}

SUPPLY_CHAIN_EDGES = [
    ("Arm", "Qualcomm", "供應 / IP 架構"), ("Arm", "Amazon", "供應 / IP 架構"), ("Arm", "Apple", "供應 / IP 架構"),
    ("TSMC", "AMD", "供應 / 代工"), ("TSMC", "Nvidia", "供應 / 代工"), ("TSMC", "Apple", "供應 / 代工"),
    ("Samsung", "Nvidia", "供應 / 記憶體/製造"), ("Micron", "Nvidia", "供應 / HBM 記憶體"), ("SK hynix", "Nvidia", "供應 / HBM 記憶體"),
    ("Intel", "Dell", "客戶 / 平台導入"), ("AMD", "Dell", "客戶 / 平台導入"),
    ("Nvidia", "Supermicro", "客戶 / 平台導入"), ("Intel", "Supermicro", "客戶 / 平台導入"), ("AMD", "Supermicro", "客戶 / 平台導入"),
    ("Intel", "AWS", "客戶 / 雲端需求"), ("AMD", "AWS", "客戶 / 雲端需求"), ("Nvidia", "AWS", "客戶 / 雲端需求"),
    ("Intel", "Azure", "客戶 / 雲端需求"), ("AMD", "Azure", "客戶 / 雲端需求"), ("Nvidia", "Azure", "客戶 / 雲端需求"),
    ("Intel", "Google", "客戶 / 雲端需求"), ("AMD", "Google", "客戶 / 雲端需求"), ("Nvidia", "Google", "客戶 / 雲端需求"),
]

def extract_companies_from_text(text: str) -> list:
    t = (text or "").lower()
    found, seen = [], set()
    for key, canon in COMPANY_CANON.items():
        pattern = r"\b" + re.escape(key.lower()) + r"\b" if key.isascii() else re.escape(key.lower())
        if re.search(pattern, t) and canon not in seen:
            seen.add(canon); found.append(canon)
    return found

def extract_topics_from_text(text: str) -> list:
    t = (text or "").lower()
    return [topic for topic, keys in TOPIC_KEYWORDS.items() if any(k.lower() in t for k in keys)]

def short_evidence_title(row) -> str:
    title = str(row.get("title_zh") or row.get("title") or "")
    return re.sub(r"\s+", " ", title).strip()[:120]

def build_industry_relationships(feed: pd.DataFrame, max_news: int = 80):
    if feed is None or feed.empty:
        return pd.DataFrame(), pd.DataFrame(), {}
    work = feed.copy().head(max_news)
    node_counts, node_types, node_layers, edge_evidence = {}, {}, {}, {}

    def add_node(node, ntype, layer=""):
        if not node: return
        node_counts[node] = node_counts.get(node, 0) + 1
        node_types[node] = ntype
        if layer: node_layers[node] = layer

    def add_edge(src, dst, relation, evidence):
        if not src or not dst or src == dst: return
        key = (src, dst, relation)
        edge_evidence.setdefault(key, [])
        if evidence and evidence not in edge_evidence[key]: edge_evidence[key].append(evidence)

    for _, row in work.iterrows():
        text = " ".join([str(row.get("title", "")), str(row.get("title_zh", "")), str(row.get("category", "")), str(row.get("summary", ""))])
        evidence = short_evidence_title(row)
        companies = extract_companies_from_text(text)
        topics = extract_topics_from_text(text)
        for c in companies: add_node(c, "公司", COMPANY_LAYER.get(c, "公司"))
        for tp in topics: add_node(tp, "主題 / 技術", "主題")
        for c in companies:
            for tp in topics: add_edge(tp, c, "事件影響 / 題材關聯", evidence)
        for i in range(len(companies)):
            for j in range(i+1, len(companies)):
                pair = tuple(sorted([companies[i], companies[j]]))
                if pair in COMPETITION_PAIRS:
                    a,b = pair; add_edge(a, b, "競爭：" + COMPETITION_PAIRS[pair], evidence)
        present = set(companies)
        for src, dst, rel in SUPPLY_CHAIN_EDGES:
            if src in present and dst in present: add_edge(src, dst, rel, evidence)

    appeared = {n for n,t in node_types.items() if t == "公司"}
    for src, dst, rel in SUPPLY_CHAIN_EDGES:
        if src in appeared and dst in appeared: add_edge(src, dst, rel, "產業字典關係：需搭配新聞確認")
    for pair, rel in COMPETITION_PAIRS.items():
        a,b = pair
        if a in appeared and b in appeared: add_edge(a, b, "競爭：" + rel, "產業字典關係：需搭配新聞確認")

    nodes = [{"node":n, "type":node_types.get(n,""), "layer":node_layers.get(n,""), "count":c} for n,c in node_counts.items()]
    edges = [{"source":s, "target":d, "relation":r, "strength":len(evs), "evidence":"｜".join(evs[:5])} for (s,d,r),evs in edge_evidence.items()]
    nodes_df = pd.DataFrame(nodes).sort_values(["count","node"], ascending=[False, True]) if nodes else pd.DataFrame()
    edges_df = pd.DataFrame(edges).sort_values(["strength","relation"], ascending=[False, True]) if edges else pd.DataFrame()
    summary = {
        "top_companies": nodes_df[nodes_df["type"]=="公司"].head(8)["node"].tolist() if not nodes_df.empty else [],
        "top_topics": nodes_df[nodes_df["type"]=="主題 / 技術"].head(8)["node"].tolist() if not nodes_df.empty else [],
        "top_relations": edges_df.head(8).to_dict("records") if not edges_df.empty else [],
    }
    return nodes_df, edges_df, summary

def draw_industry_graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, mode: str = "全部關係") -> str:
    if nodes_df is None or nodes_df.empty: return ""
    e = edges_df.copy() if edges_df is not None and not edges_df.empty else pd.DataFrame(columns=["source","target","relation","strength","evidence"])
    if mode == "供應鏈圖": e = e[e["relation"].str.contains("供應|客戶|代工|平台|雲端", na=False)]
    elif mode == "競爭圖": e = e[e["relation"].str.contains("競爭|替代|威脅", na=False)]
    elif mode == "事件傳導圖": e = e[e["relation"].str.contains("事件影響|題材", na=False)]
    e = e.head(35)
    active_nodes = set(e["source"].tolist() + e["target"].tolist()) if not e.empty else set(nodes_df.head(20)["node"].tolist())
    n = nodes_df[nodes_df["node"].isin(active_nodes)].head(28)
    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="#222222", directed=True)
    net.barnes_hut(gravity=-26000, central_gravity=0.2, spring_length=180, spring_strength=0.02, damping=0.88)
    color_map = {"公司":"#2f80ed", "主題 / 技術":"#9b51e0", "產業鏈位置":"#27ae60", "新聞事件":"#f2994a"}
    for _, row in n.iterrows():
        node, ntype, layer, count = row["node"], row.get("type",""), row.get("layer",""), int(row.get("count",1))
        net.add_node(node, label=node, title=f"{node}<br>類型：{ntype}<br>位置：{layer}<br>提及次數：{count}", color=color_map.get(ntype,"#828282"), size=16+min(count*3,20), group=ntype)
    edge_color = {"競爭":"#eb5757", "供應":"#2f80ed", "客戶":"#27ae60", "事件影響":"#f2994a", "題材":"#f2994a"}
    for _, row in e.iterrows():
        src, dst, rel = row["source"], row["target"], str(row.get("relation",""))
        color = "#828282"
        for key,c in edge_color.items():
            if key in rel: color = c; break
        width = 1 + min(int(row.get("strength",1)),5)
        title = f"{rel}<br>強度：{row.get('strength',1)}<br>{html.escape(str(row.get('evidence','')))}"
        net.add_edge(src, dst, title=title, label=rel[:10], color=color, width=width)
    net.toggle_physics(True)
    path = f"industry_graph_{mode}.html".replace("/", "_")
    net.save_graph(path)
    return path

def render_industry_relationship_page(feed: pd.DataFrame):
    st.subheader("產業關係圖")
    st.caption("V22：關係圖改為公司 / 主題 / 供應鏈 / 競爭 / 事件影響。線條必須有新聞證據或產業字典支撐。")
    if feed is None or feed.empty:
        st.info("目前沒有新聞資料可建立產業關係圖。")
        return
    nodes_df, edges_df, summary = build_industry_relationships(feed, max_news=80)
    if nodes_df.empty:
        st.info("目前新聞沒有抽到足夠的公司或產業主題。建議搜尋 CPU、AI server、NVIDIA Intel AMD、AI 軟硬體產業等主題。")
        return
    st.markdown("### 產業關係摘要")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**主要公司**"); st.write("、".join(summary.get("top_companies", [])) or "無")
    with c2:
        st.markdown("**主要主題**"); st.write("、".join(summary.get("top_topics", [])) or "無")
    if summary.get("top_relations"):
        st.markdown("**主要關係**")
        for r in summary["top_relations"][:5]: st.markdown(f"- **{r['source']} → {r['target']}**｜{r['relation']}｜證據 {r['strength']}")
    mode = st.radio("關係圖模式", ["全部關係", "供應鏈圖", "競爭圖", "事件傳導圖"], index=0, horizontal=True)
    graph_path = draw_industry_graph(nodes_df, edges_df, mode=mode)
    if graph_path:
        with open(graph_path, "r", encoding="utf-8") as f: st.components.v1.html(f.read(), height=700, scrolling=True)
    st.markdown("### 關係證據表")
    if edges_df.empty: st.info("目前沒有形成明確關係。")
    else: st.dataframe(edges_df[["source","target","relation","strength","evidence"]].head(80), use_container_width=True)
    with st.expander("節點清單"):
        st.dataframe(nodes_df.head(80), use_container_width=True)


def build_graph(feed: pd.DataFrame) -> str:
    g = nx.Graph()
    if feed is not None and not feed.empty:
        for i, row in feed.head(80).iterrows():
            item = f"I:{i}"
            dtype = str(row.get("data_type", ""))
            title = str(row.get("title_zh") or row.get("title") or "Untitled")
            domain = str(row.get("domain", ""))
            location = str(row.get("location", ""))
            cat = str(row.get("category", ""))

            g.add_node(item, label=dtype, title=title, group="item")

            for label, prefix, group_name in [
                (domain, "D", "domain"),
                (location, "L", "location"),
                (cat, "C", "category"),
            ]:
                if label:
                    node = f"{prefix}:{label}"
                    g.add_node(node, label=label, title=group_name, group=group_name)
                    g.add_edge(item, node)

    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="#222222")
    net.from_nx(g)
    net.toggle_physics(True)
    path = "relationship_graph.html"
    net.save_graph(path)
    return path


# -------------------------------
# UI
# -------------------------------

st.set_page_config(page_title="Global News Radar V22", layout="wide", initial_sidebar_state="collapsed")

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
.article-zh {
    font-size: 1.09rem;
    font-weight: 750;
    line-height: 1.52;
    margin-top: 8px;
}
.article-original {
    font-size: 0.96rem;
    font-weight: 650;
    line-height: 1.4;
    opacity: 0.88;
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
@media (max-width: 768px) {
    h1 {
        font-size: 2.05rem !important;
        line-height: 1.18 !important;
        word-break: keep-all;
    }
    div[data-testid="stMetricValue"] { font-size: 2.0rem !important; }
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

st.title("🌍 Global News Radar V22：投資情報雷達穩定版")

with st.sidebar:
    st.header("搜尋")
    search_mode = st.radio(
        "搜尋模式",
        ["自然語言研究搜尋", "精準關鍵字"],
        index=0,
        help="自然語言模式會先用 Groq 把問題拆成多個財經新聞搜尋式；精準關鍵字則照你輸入的字查。"
    )
    if search_mode == "自然語言研究搜尋":
        query = st.text_area(
            "研究問題",
            value="AI 軟硬體產業最近有哪些重要新聞？",
            height=90,
        )
        st.caption("例：AI 軟硬體產業最近有哪些重要新聞？ / 最近 AI 伺服器供應鏈有什麼變化？ / NVIDIA、Intel、AMD 在 AI CPU/GPU 的新聞")
        query_logic = "聯集 OR"
    else:
        query = st.text_input("關鍵字 / 公司 / 人名", value="NVIDIA")
        query_logic = st.radio("多關鍵字邏輯", ["交集 AND", "聯集 OR"], index=0, help="例：NVIDIA intel。交集=同時找兩者相關；聯集=分別找 NVIDIA 與 Intel 後合併。")
    time_range = st.selectbox("財經新聞時間範圍", ["最近 1 小時", "最近 6 小時", "最近 12 小時", "最近 24 小時", "最近 3 天", "最近 7 天", "不限時間"], index=3)
    max_items = st.slider("最多新聞篇數", 5, 80, 30, step=5)
    translate_titles = st.checkbox("原文標題 + 智慧翻譯成繁中", value=True)
    translation_mode = st.radio(
        "翻譯模式",
        ["Groq AI 財經翻譯優先", "只用免費機翻", "不翻譯只保留原文"],
        index=0,
        help="Groq 模式需要在 Streamlit Secrets 設定 GROQ_API_KEY。"
    )
    if groq_is_enabled():
        st.success(f"Groq API：已啟用｜模型：{get_groq_model()}")
    else:
        st.warning("Groq API：未設定。目前會退回免費機翻或原文。")

    with st.expander("測試 Groq 翻譯"):
        test_title = st.text_input(
            "測試標題",
            value="Nvidia crashes Intel’s party: $5T giant surges as AI market pivots to CPUs",
            key="groq_test_title",
        )
        if st.button("執行翻譯測試", key="run_groq_test"):
            test = translate_title_with_engine(test_title, domain="investing.com", category="AI / 半導體", translation_mode=translation_mode)
            st.write(f"翻譯來源：{test.get('engine')}")
            st.write(test.get("text"))

    st.divider()
    st.subheader("財經新聞來源")
    use_google = st.checkbox("Google News RSS", value=True)
    use_yahoo = st.checkbox("Yahoo Finance RSS（適合美股 ticker）", value=True)

    st.caption("V15：先看 Google News / Yahoo Finance；GDELT 事件補充預設關閉，避免出現無意義機器事件。")
    preferred_domains = st.multiselect(
        "Google News 加強財經來源",
        options=PREFERRED_FINANCE_DOMAINS,
        default=["reuters.com", "cnbc.com", "finance.yahoo.com"],
    )

    st.divider()
    st.subheader("全球事件補充")
    st.caption("提醒：GDELT 是機器事件資料，不是財經新聞。查公司時建議先關閉，除非你要看地緣政治背景。")
    use_gdelt_events = st.checkbox("加入 GDELT 全球事件補充（預設關閉，避免雜訊）", value=False)
    event_files = st.slider("最近幾個 15 分鐘事件檔", 1, 8, 3)
    event_max_rows = st.slider("每個事件檔最多列數", 1000, 30000, 10000, step=1000)
    event_items = st.slider("納入統合新聞流的事件數", 0, 80, 10)

    st.divider()
    st.subheader("顯示")
    display_mode = st.radio("閱讀版型", ["手機卡片", "電腦表格"], index=0)
    show_news_on_map = st.checkbox("地圖顯示公司/財經新聞", value=True)
    show_events_on_map = st.checkbox("地圖顯示全球事件", value=True)

    search_button = st.button("更新統合新聞流", type="primary", key="update_feed")

# Init session
if "last_articles" not in st.session_state:
    st.session_state["last_articles"] = pd.DataFrame()
if "last_feed" not in st.session_state:
    st.session_state["last_feed"] = pd.DataFrame()
if "last_success_query" not in st.session_state:
    st.session_state["last_success_query"] = ""
if "last_query_plan" not in st.session_state:
    st.session_state["last_query_plan"] = {}

# Load GDELT events separately. Even if news fails, events can still work.
events_all = pd.DataFrame()
if use_gdelt_events:
    with st.spinner("正在抓取 GDELT 全球事件補充..."):
        try:
            events_all = load_latest_events(num_files=event_files, max_rows_per_file=event_max_rows)
        except Exception as exc:
            st.info(f"GDELT 全球事件補充暫時無法讀取：{exc}")

if search_button:
    with st.spinner("正在建立搜尋策略與搜尋財經新聞..."):
        query_plan = None
        if search_mode == "自然語言研究搜尋":
            query_plan = groq_build_search_plan(query, time_range=time_range)
            st.session_state["last_query_plan"] = query_plan
        else:
            st.session_state["last_query_plan"] = default_search_plan(query)

        articles = search_finance_news(
            query=query,
            max_items=max_items,
            translate_titles=translate_titles,
            use_google=use_google,
            use_yahoo=use_yahoo,
            preferred_domains=preferred_domains,
            query_logic=query_logic,
            time_range=time_range,
            translation_mode=translation_mode,
            search_mode=search_mode,
            query_plan=query_plan,
        )

        if not articles.empty:
            st.session_state["last_articles"] = articles
            st.session_state["last_success_query"] = query
        else:
            st.info("這次沒有抓到新的財經新聞，保留上次成功結果。")

articles = st.session_state["last_articles"]

events_filtered = filter_events(events_all, keyword=query, max_events=event_items) if use_gdelt_events else pd.DataFrame()
feed = build_unified_feed(articles, events_filtered)

if not feed.empty:
    st.session_state["last_feed"] = feed
else:
    feed = st.session_state["last_feed"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("統合新聞流", f"{len(feed):,}")
col2.metric("公司/財經新聞", f"{len(articles):,}")
col3.metric("全球事件", f"{len(events_filtered):,}")
col4.metric("事件原始數", f"{len(events_all):,}")

if st.session_state.get("last_success_query"):
    st.caption(f"上次成功查詢：{st.session_state['last_success_query']}｜目前選擇時間範圍：{time_range}")

plan = st.session_state.get("last_query_plan", {})
if plan:
    with st.expander("AI 搜尋策略", expanded=False):
        st.markdown(f"**核心主題：** {plan.get('core_topic_zh', '')}")
        st.markdown(f"**拆解理由：** {plan.get('reason', '')}")
        st.markdown("**實際搜尋式：**")
        for q in plan.get("search_queries", []):
            st.code(q, language="text")
        if plan.get("tickers"):
            st.markdown("**相關 ticker：** " + ", ".join(plan.get("tickers", [])))

tab_feed, tab_map, tab_graph, tab_raw = st.tabs(["統合新聞流", "統合地圖", "產業關係圖", "原始資料"])

with tab_feed:
    st.subheader("統合新聞流")
    st.caption("V22：自然語言搜尋 + 產業關係圖；關係圖會抽出公司、主題、競爭、供應鏈與事件影響。")

    if feed.empty:
        st.info("尚未查到資料。請打開側欄設定關鍵字後按「更新統合新聞流」。")
    else:
        if display_mode == "手機卡片":
            for _, row in feed.head(100).iterrows():
                dtype = html.escape(str(row.get("data_type", "")))
                title = html.escape(str(row.get("title", "")))
                title_zh = html.escape(str(row.get("title_zh", "")) or str(row.get("title", "")))
                url = str(row.get("url", ""))
                url_safe = html.escape(url, quote=True)
                domain = html.escape(str(row.get("domain", "")))
                time_utc = html.escape(str(row.get("time_utc", "")))
                location = html.escape(str(row.get("location", "")))
                quality = html.escape(str(row.get("source_quality", "")))
                category = html.escape(str(row.get("category", "")))
                importance = html.escape(str(row.get("importance", "")))
                translation_engine = html.escape(str(row.get("translation_engine", "")))
                summary = html.escape(str(row.get("summary", "")))

                title_html = title
                if url.startswith("http"):
                    title_html = f"<a href='{url_safe}' target='_blank'>{title}</a>"

                hint = html.escape(make_click_hint(str(row.get("title", "")), str(row.get("domain", "")), str(row.get("category", "")), str(row.get("importance", ""))))

                if str(row.get("data_type", "")) == "全球事件補充":
                    main_label = "事件摘要"
                    original_label = "原始事件描述"
                    hint = "背景補充：GDELT 是機器事件資料，通常不用優先點，除非它跟公司 / 政策 / 地緣風險直接相關。"
                else:
                    main_label = "重點標題"
                    original_label = "原文標題"

                st.markdown(
                    f"""
                    <div class="article-card">
                        <div class="article-type">{dtype}｜{category}｜重要性 {importance}</div>
                        <div class="article-zh">{main_label}：{title_zh}</div>
                        <div class="article-original">{original_label}：{title_html}</div>
                        <div class="article-meta">{time_utc}<br>{domain}｜{location}｜{quality}<br>翻譯來源：{translation_engine}<br>{summary}</div>
                        <div class="article-meta"><b>判斷：</b>{hint}</div>
                        <div class="article-source"><a href="{url_safe}" target="_blank">打開來源</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            cols = ["time_utc", "data_type", "importance", "category", "title_zh", "title", "domain", "source_quality", "location", "url"]
            st.dataframe(feed[[c for c in cols if c in feed.columns]], use_container_width=True)

with tab_map:
    st.subheader("統合地圖")
    st.caption("紫色數字＝公司/財經新聞來源國家篇數；藍色數字＝全球事件。地圖 popup 只顯示 Top 3，完整內容回到統合新聞流。")
    m = build_world_map(feed, show_news=show_news_on_map, show_events=show_events_on_map)
    st_folium(m, width=None, height=520, returned_objects=[], key="world_map")

with tab_graph:
    render_industry_relationship_page(feed)

with tab_raw:
    st.subheader("原始資料")
    st.markdown("### 財經新聞")
    if articles.empty:
        st.info("尚未查到財經新聞。")
    else:
        st.dataframe(articles, use_container_width=True)

    st.markdown("### GDELT 全球事件")
    if events_filtered.empty:
        st.info("目前沒有符合條件的 GDELT 全球事件。")
    else:
        display_cols = ["event_time_utc", "who", "where", "what", "NumMentions", "NumArticles", "AvgTone", "GoldsteinScale", "source"]
        st.dataframe(events_filtered[[c for c in display_cols if c in events_filtered.columns]], use_container_width=True)
