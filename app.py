
import html
import io
import json
import os
import re
import zipfile
from pathlib import Path
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
# Global News Radar V37
# 自動驗證供應鏈視圖修正版
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
        "最近 8 小時": 8,
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
        "最近 8 小時": "when:8h",
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


def get_groq_model_light():
    """Light model for query planning and bulk title translation."""
    try:
        model = st.secrets.get("GROQ_MODEL_LIGHT", "")
        if model:
            return model
    except Exception:
        pass
    return os.environ.get("GROQ_MODEL_LIGHT", "llama-3.1-8b-instant")


def get_groq_model_heavy():
    """Heavy model for event summary and high-value finance translation."""
    try:
        model = st.secrets.get("GROQ_MODEL_HEAVY", "")
        if model:
            return model
    except Exception:
        pass

    # Backward compatible with older Secrets.
    try:
        model = st.secrets.get("GROQ_MODEL", "")
        if model:
            return model
    except Exception:
        pass
    return os.environ.get("GROQ_MODEL_HEAVY", os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))


def get_groq_model():
    """Backward-compatible default model."""
    return get_groq_model_heavy()


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
            model=get_groq_model_light(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=650,
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
def groq_finance_translate_title(title: str, domain: str = "", category: str = "", model_tier: str = "light") -> str:
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
""".strip()

    user_prompt = f"""
來源網域：{domain}
初步分類：{category}
原文標題：{title}
請輸出繁體中文財經標題：
""".strip()

    try:
        client = Groq(api_key=api_key)
        model_name = get_groq_model_heavy() if model_tier == "heavy" else get_groq_model_light()
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=220 if model_tier == "heavy" else 170,
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


def translate_title_with_engine(
    title: str,
    domain: str = "",
    category: str = "",
    translation_mode: str = "Groq AI 財經翻譯優先",
    model_tier: str = "light",
) -> dict:
    title = clean_text(title)
    if not title:
        return {"text": "", "engine": "無"}

    if translation_mode == "Groq AI 財經翻譯優先":
        groq_result = groq_finance_translate_title(
            title,
            domain=domain,
            category=category,
            model_tier=model_tier,
        )
        if groq_result:
            model_name = get_groq_model_heavy() if model_tier == "heavy" else get_groq_model_light()
            return {"text": groq_result, "engine": f"Groq {model_tier}｜{model_name}"}

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


def translate_title_to_zh_tw(
    title: str,
    domain: str = "",
    category: str = "",
    translation_mode: str = "Groq AI 財經翻譯優先",
    model_tier: str = "light",
) -> str:
    return translate_title_with_engine(
        title,
        domain=domain,
        category=category,
        translation_mode=translation_mode,
        model_tier=model_tier,
    ).get("text", "")



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


def heat_score(row) -> int:
    """Approximate discussion heat for RSS-based news. It is not true social volume."""
    title = str(row.get("title", "") or "").lower()
    category = str(row.get("category", "") or "")
    quality = str(row.get("source_quality", "") or "")
    score = 0

    if quality.startswith("A+"):
        score += 35
    elif quality.startswith("A"):
        score += 28
    elif quality.startswith("B"):
        score += 20
    elif quality.startswith("C"):
        score += 10

    hot_terms = [
        "ai", "artificial intelligence", "semiconductor", "chip", "chips",
        "gpu", "cpu", "accelerator", "data center", "datacenter",
        "server", "hbm", "memory", "tsmc", "nvidia", "amd", "intel",
        "broadcom", "marvell", "micron", "sk hynix", "samsung",
        "blackwell", "rubin", "grace", "vera", "epyc", "xeon",
        "inference", "capex", "cloud", "hyperscaler", "asic",
        "networking", "ethernet", "switch", "cooling", "power"
    ]
    score += min(sum(1 for k in hot_terms if k in title) * 6, 42)

    market_terms = [
        "earnings", "guidance", "revenue", "margin", "forecast",
        "surge", "rally", "plunge", "falls", "jumps", "record",
        "price target", "upgrade", "downgrade", "ban", "export",
        "restriction", "tariff", "deal", "partnership", "order", "demand",
        "shortage", "capex", "investment"
    ]
    score += min(sum(1 for k in market_terms if k in title) * 7, 35)

    if category in ["財報 / 指引", "政策 / 管制", "供應鏈 / 客戶"]:
        score += 25
    elif category in ["AI / 半導體"]:
        score += 22
    elif category in ["股價 / 估值"]:
        score += 12

    t = pd.to_datetime(row.get("time_utc"), errors="coerce", utc=True)
    if pd.notna(t):
        hours = (pd.Timestamp.now(tz="UTC") - t).total_seconds() / 3600
        if hours <= 1:
            score += 25
        elif hours <= 3:
            score += 18
        elif hours <= 8:
            score += 12
        elif hours <= 24:
            score += 5
    return int(score)



def time_range_to_hours_safe(time_range: str) -> int | None:
    mapping = {
        "最近 1 小時": 1,
        "最近 6 小時": 6,
        "最近 8 小時": 8,
        "最近 12 小時": 12,
        "最近 24 小時": 24,
        "最近 3 天": 72,
        "最近 7 天": 168,
        "不限時間": None,
    }
    return mapping.get(time_range, 24)


def extract_event_date_from_text(text: str):
    """Best-effort event date extraction from URL/title.

    RSS time is push/publish time. Event date often appears in URLs like:
    /2026/04/22/ or -2026-04-22
    """
    text = str(text or "")

    patterns = [
        r"(20\d{2})[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])",
        r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])",
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return pd.Timestamp(year=y, month=mo, day=d, tz="UTC")
            except Exception:
                pass

    # Month-name dates common in snippets/titles.
    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2,
        "mar": 3, "march": 3, "apr": 4, "april": 4,
        "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    m = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+([0-3]?\d),?\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        try:
            mo = month_map[m.group(1).lower().strip(".")]
            d = int(m.group(2))
            y = int(m.group(3))
            return pd.Timestamp(year=y, month=mo, day=d, tz="UTC")
        except Exception:
            pass

    return pd.NaT


def classify_freshness(row, time_range: str = "最近 8 小時") -> tuple[str, str, int]:
    """Classify event freshness.

    Labels:
    - 真新事件
    - 舊事件新包裝
    - 重複推送
    - 誤抓 / 垃圾訊號
    """
    title = str(row.get("title", "") or "")
    url = str(row.get("url", "") or "")
    domain = str(row.get("domain", "") or "")
    category = str(row.get("category", "") or "")
    quality = str(row.get("source_quality", "") or "")
    source_type = str(row.get("source_type", "") or "")
    text = f"{title} {url} {domain} {source_type}".lower()

    garbage_terms = [
        "sitemap", "site map", "robots.txt", "rss feed",
        "2009 results", "2010 results", "2009/10", "2009-10",
        "baseball bat", "ai bat", "bat review", "james chai",
        "newsletter signup", "subscribe", "privacy policy",
        "advertise with us", "contact us", "stock quote page",
    ]
    if any(term in text for term in garbage_terms):
        return "誤抓 / 垃圾訊號", "標題或 URL 命中 sitemap、舊財報、非投資主線或低品質頁面等誤抓規則。", -999

    low_value_terms = [
        "how to use", "what is", "best ai tools", "resume", "job interview",
        "career advice", "prompt examples", "student", "homework",
        "lottery", "celebrity", "movie", "music", "sports",
    ]
    if any(term in text for term in low_value_terms) and category == "一般新聞":
        return "誤抓 / 垃圾訊號", "標題偏教學、職涯、娛樂或泛 AI 內容，缺少財經/供應鏈投資訊號。", -999

    event_date = extract_event_date_from_text(f"{title} {url}")
    now = pd.Timestamp.now(tz="UTC")
    hours = time_range_to_hours_safe(time_range)

    analysis_terms = [
        "analysis", "analyst", "why", "what it means", "what this means",
        "could", "may", "after", "as", "amid", "signals", "warns",
        "forecast", "raises", "cuts", "upgrade", "downgrade", "report",
        "says", "sees", "expects", "outlook", "takeaways",
        "goldman", "citi", "morgan stanley", "jpmorgan", "ubs",
        "regulator", "regulatory", "probe", "investigation",
    ]

    if pd.notna(event_date):
        event_age_hours = (now.normalize() - event_date.normalize()).total_seconds() / 3600
        # If the embedded date is clearly older than the selected time window, it is not a true new event.
        # Add a small buffer because URL date usually has day-level precision.
        threshold = (hours or 24) + 24
        if event_age_hours > threshold:
            if any(term in text for term in analysis_terms):
                return "舊事件新包裝", f"URL / 標題日期約為 {event_date.date()}，事件本身較早；但文章可能提供今日分析、後續或量化角度。", 20
            return "重複推送", f"URL / 標題日期約為 {event_date.date()}，早於目前搜尋時間窗，較像舊事件被 RSS 重新推送。", -30

    # If no old event date is found, classify by news nature.
    fresh_terms = [
        "breaking", "exclusive", "today", "latest", "new", "launches", "unveils",
        "reports", "reported", "agrees", "deal", "acquires", "buy", "sells",
        "earnings", "guidance", "revenue", "raises", "cuts", "ban", "export",
        "restriction", "tariff", "probe", "regulator", "orders", "asks",
    ]

    if any(term in text for term in fresh_terms) or category in ["財報 / 指引", "政策 / 管制", "供應鏈 / 客戶"]:
        return "真新事件", "標題含新發生、財報/指引、政策/管制、交易或供應鏈變化訊號；可優先當今日催化檢查。", 50

    if any(term in text for term in analysis_terms):
        return "舊事件新包裝", "較像今日分析稿、券商/媒體解讀或舊事件的新角度；保留但不等同全新事件。", 20

    if quality.startswith("A") or quality.startswith("B"):
        return "真新事件", "來源品質較高且沒有明顯舊事件日期或誤抓訊號，暫列為可追蹤的新報導。", 40

    return "舊事件新包裝", "沒有明顯事件日期與重大新催化字眼，暫列為背景/討論熱度訊號。", 10


def apply_freshness_filter(df: pd.DataFrame, freshness_mode: str = "新事件優先") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if "freshness_label" not in out.columns:
        out["freshness_label"] = "未判斷"
    if "freshness_score" not in out.columns:
        out["freshness_score"] = 0

    if freshness_mode == "熱度掃描":
        # Only remove clear junk.
        out = out[out["freshness_label"] != "誤抓 / 垃圾訊號"]
    elif freshness_mode == "嚴格新事件":
        out = out[out["freshness_label"] == "真新事件"]
    else:
        # Default: keep new events and useful re-analysis, remove clear junk,
        # keep repeated pushes but push them down if user wants to inspect.
        out = out[out["freshness_label"] != "誤抓 / 垃圾訊號"]

    return out


def apply_heat_ranking(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["heat_score"] = out.apply(heat_score, axis=1)

    if "freshness_score" not in out.columns:
        out["freshness_score"] = 0

    importance_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    quality_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    out["_i"] = out["importance"].map(importance_order).fillna(9)
    out["_q"] = out["source_quality"].astype(str).str[0].map(quality_order).fillna(9)
    out["time_utc"] = pd.to_datetime(out["time_utc"], errors="coerce", utc=True)
    return out.sort_values(
        ["freshness_score", "heat_score", "_i", "_q", "time_utc"],
        ascending=[False, False, True, True, False],
    ).drop(columns=["_i", "_q"])



def make_download_filename(prefix: str, ext: str) -> str:
    ts = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y%m%d_%H%M")
    return f"{prefix}_{ts}.{ext}"


def clean_for_markdown(value) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_news_bundle_markdown(feed: pd.DataFrame, ai_summary: str = "", query: str = "", time_range: str = "", plan: dict | None = None) -> str:
    """Create a Markdown research bundle that can be uploaded back to ChatGPT."""
    lines = []
    now = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y-%m-%d %H:%M:%S %Z")

    lines.append("# Global News Radar 新聞包")
    lines.append("")
    lines.append(f"- 匯出時間：{now}")
    lines.append(f"- 查詢問題：{clean_for_markdown(query)}")
    lines.append(f"- 時間範圍：{clean_for_markdown(time_range)}")
    lines.append(f"- 新聞筆數：{0 if feed is None else len(feed)}")
    lines.append("")

    if plan:
        lines.append("## AI 搜尋策略")
        lines.append("")
        lines.append(f"- 核心主題：{clean_for_markdown(plan.get('core_topic_zh', ''))}")
        lines.append(f"- 拆解理由：{clean_for_markdown(plan.get('reason', ''))}")
        queries = plan.get("search_queries", []) or []
        if queries:
            lines.append("- 實際搜尋式：")
            for q in queries:
                lines.append(f"  - {clean_for_markdown(q)}")
        tickers = plan.get("tickers", []) or []
        if tickers:
            lines.append(f"- 相關 ticker：{', '.join([clean_for_markdown(t) for t in tickers])}")
        lines.append("")

    if ai_summary:
        lines.append("## App 內 AI 事件總結")
        lines.append("")
        lines.append(str(ai_summary).strip())
        lines.append("")

    lines.append("## 全部新聞")
    lines.append("")

    if feed is None or feed.empty:
        lines.append("目前沒有新聞資料。")
        return "\n".join(lines)

    df = feed.copy().reset_index(drop=True)

    for i, row in df.iterrows():
        title_zh = clean_for_markdown(row.get("title_zh", ""))
        title = clean_for_markdown(row.get("title", ""))
        url = clean_for_markdown(row.get("url", ""))
        domain = clean_for_markdown(row.get("domain", ""))
        time_utc = clean_for_markdown(row.get("time_utc", ""))
        data_type = clean_for_markdown(row.get("data_type", ""))
        category = clean_for_markdown(row.get("category", ""))
        importance = clean_for_markdown(row.get("importance", ""))
        quality = clean_for_markdown(row.get("source_quality", ""))
        heat_score = clean_for_markdown(row.get("heat_score", ""))
        freshness_label = clean_for_markdown(row.get("freshness_label", ""))
        freshness_reason = clean_for_markdown(row.get("freshness_reason", ""))
        location = clean_for_markdown(row.get("location_name", row.get("source_country", row.get("location", ""))))
        translation_engine = clean_for_markdown(row.get("translation_engine", ""))

        display_title = title_zh or title or "(無標題)"
        lines.append(f"### {i + 1}. {display_title}")
        lines.append("")
        if title and title != title_zh:
            lines.append(f"- 原文標題：{title}")
        lines.append(f"- 時間 UTC：{time_utc}")
        lines.append(f"- 來源：{domain}")
        lines.append(f"- 地點 / 國家：{location}")
        lines.append(f"- 類型：{data_type}")
        lines.append(f"- 類別：{category}")
        lines.append(f"- 重要性：{importance}")
        lines.append(f"- 來源品質：{quality}")
        lines.append(f"- 新鮮度：{freshness_label}")
        lines.append(f"- 新鮮度理由：{freshness_reason}")
        lines.append(f"- 熱度分數：{heat_score}")
        if translation_engine:
            lines.append(f"- 翻譯來源：{translation_engine}")
        if url:
            lines.append(f"- 連結：{url}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 給 ChatGPT 的建議提示詞")
    lines.append("")
    lines.append("請閱讀這份 Global News Radar 新聞包，幫我整理：")
    lines.append("1. 這批事件代表什麼？")
    lines.append("2. 對 AI / 半導體 / 科技股的可能影響是什麼？")
    lines.append("3. 哪些是事實、哪些只是市場敘事？")
    lines.append("4. 哪些公司或供應鏈最值得追蹤？")
    lines.append("5. 請先按新鮮度分成：真新事件 / 舊事件新包裝 / 重複推送 / 誤抓剔除。")
    lines.append("6. 幫我用分析師口吻產出結論、影響矩陣與後續追蹤清單。")

    return "\n".join(lines)


def build_news_bundle_csv(feed: pd.DataFrame) -> bytes:
    """CSV export for spreadsheet review."""
    if feed is None or feed.empty:
        return "no,data\n".encode("utf-8-sig")

    keep_cols = [
        "time_utc", "title_zh", "title", "url", "domain", "source_country",
        "location_name", "data_type", "category", "importance", "source_quality",
        "heat_score", "freshness_label", "freshness_reason", "freshness_score", "translation_engine", "language"
    ]
    df = feed.copy()
    cols = [c for c in keep_cols if c in df.columns]
    if cols:
        df = df[cols]
    return df.to_csv(index=False).encode("utf-8-sig")


def render_clipboard_button(text: str, button_label: str = "一鍵複製 Markdown 新聞包"):
    """Render a browser-side copy-to-clipboard button.

    This avoids downloading a file when the user wants to paste directly into ChatGPT.
    Includes a fallback using document.execCommand for stricter mobile browsers.
    """
    if not text:
        st.info("目前沒有可複製的新聞包。")
        return

    payload_json = json.dumps(text, ensure_ascii=False)
    hidden_textarea = html.escape(text)

    component_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
      <button id="copy-news-bundle"
        style="
          width: 100%;
          padding: 14px 16px;
          border: 0;
          border-radius: 12px;
          background: #ff4b4b;
          color: white;
          font-weight: 700;
          font-size: 16px;
          cursor: pointer;
        ">
        {html.escape(button_label)}
      </button>
      <div id="copy-status"
        style="margin-top: 10px; color: #8b949e; font-size: 14px; line-height: 1.4;">
        按下後會複製完整 Markdown 新聞包，然後回 ChatGPT 直接貼上。
      </div>
      <textarea id="copy-fallback-text"
        style="position: absolute; left: -9999px; top: -9999px;">{hidden_textarea}</textarea>

      <script>
        const newsBundleText = {payload_json};
        const btn = document.getElementById("copy-news-bundle");
        const status = document.getElementById("copy-status");
        const fallback = document.getElementById("copy-fallback-text");

        async function copyNewsBundle() {{
          try {{
            if (navigator.clipboard && window.isSecureContext) {{
              await navigator.clipboard.writeText(newsBundleText);
              status.innerText = "已複製到剪貼簿。現在可以回 ChatGPT 直接貼上。";
              status.style.color = "#3fb950";
              return;
            }}
            throw new Error("Clipboard API unavailable");
          }} catch (err) {{
            try {{
              fallback.style.position = "fixed";
              fallback.style.left = "0";
              fallback.style.top = "0";
              fallback.style.width = "1px";
              fallback.style.height = "1px";
              fallback.focus();
              fallback.select();
              fallback.setSelectionRange(0, fallback.value.length);
              const ok = document.execCommand("copy");
              fallback.style.position = "absolute";
              fallback.style.left = "-9999px";
              fallback.style.top = "-9999px";

              if (ok) {{
                status.innerText = "已複製到剪貼簿。現在可以回 ChatGPT 直接貼上。";
                status.style.color = "#3fb950";
              }} else {{
                throw new Error("execCommand copy failed");
              }}
            }} catch (err2) {{
              status.innerText = "瀏覽器阻擋自動複製。請用下方「手動複製備用區」全選複製。";
              status.style.color = "#f2cc60";
            }}
          }}
        }}

        btn.addEventListener("click", copyNewsBundle);
      </script>
    </div>
    """

    st.components.v1.html(component_html, height=105)



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


def enrich_articles(
    df: pd.DataFrame,
    translate_titles: bool,
    translation_mode: str = "Groq AI 財經翻譯優先",
    groq_translate_top_n: int = 10,
    heavy_translate_top_n: int = 3,
    freshness_mode: str = "新事件優先",
    time_range: str = "最近 8 小時",
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["domain"] = df["domain"].fillna("").astype(str)
    df["source_country"] = df["source_country"].fillna("").apply(normalize_country_name)
    df["source_quality"] = df.apply(lambda row: source_quality(row.get("domain", ""), row.get("source_type", "")), axis=1)
    df["category"] = df["title"].apply(classify_news)
    df["importance"] = df.apply(importance_score, axis=1)

    freshness = df.apply(lambda row: classify_freshness(row, time_range=time_range), axis=1)
    df["freshness_label"] = freshness.apply(lambda x: x[0])
    df["freshness_reason"] = freshness.apply(lambda x: x[1])
    df["freshness_score"] = freshness.apply(lambda x: x[2])

    df = apply_freshness_filter(df, freshness_mode=freshness_mode)

    if df.empty:
        return pd.DataFrame()

    # First rank without translation, so Groq is only spent on the most useful rows.
    df = apply_heat_ranking(df)

    if translate_titles:
        df["title_zh"] = ""
        df["translation_engine"] = "未翻譯｜省 token"

        top_n = int(groq_translate_top_n or 0)
        heavy_n = int(heavy_translate_top_n or 0)

        if translation_mode == "不翻譯只保留原文":
            df["translation_engine"] = "不翻譯"
        elif translation_mode == "只用免費機翻":
            for idx in list(df.head(top_n).index):
                row = df.loc[idx]
                trans = translate_title_with_engine(
                    row.get("title", ""),
                    domain=row.get("domain", ""),
                    category=row.get("category", ""),
                    translation_mode=translation_mode,
                    model_tier="light",
                )
                df.at[idx, "title_zh"] = trans.get("text", "")
                df.at[idx, "translation_engine"] = trans.get("engine", "免費機翻")
        else:
            for rank, idx in enumerate(list(df.head(top_n).index), 1):
                row = df.loc[idx]
                tier = "heavy" if rank <= heavy_n else "light"
                trans = translate_title_with_engine(
                    row.get("title", ""),
                    domain=row.get("domain", ""),
                    category=row.get("category", ""),
                    translation_mode=translation_mode,
                    model_tier=tier,
                )
                df.at[idx, "title_zh"] = trans.get("text", "")
                df.at[idx, "translation_engine"] = trans.get("engine", "未知")
    else:
        df["title_zh"] = ""
        df["translation_engine"] = "不翻譯"

    df = apply_heat_ranking(df)
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
    groq_translate_top_n: int = 10,
    heavy_translate_top_n: int = 3,
    freshness_mode: str = "新事件優先",
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

    df = enrich_articles(df, translate_titles=translate_titles, translation_mode=translation_mode, groq_translate_top_n=groq_translate_top_n, heavy_translate_top_n=heavy_translate_top_n, freshness_mode=freshness_mode, time_range=time_range)

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
                "heat_score": r.get("heat_score", 0),
                "freshness_label": r.get("freshness_label", ""),
                "freshness_reason": r.get("freshness_reason", ""),
                "freshness_score": r.get("freshness_score", 0),
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
                "heat_score": 0,
                "freshness_label": "全球事件補充",
                "freshness_reason": "GDELT 事件資料，與財經 RSS 新鮮度分開判斷。",
                "freshness_score": 0,
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
    if "heat_score" not in df.columns:
        df["heat_score"] = 0
    if "freshness_score" not in df.columns:
        df["freshness_score"] = 0
    df = df.sort_values(["freshness_score", "heat_score", "_i", "_q", "time_utc"], ascending=[False, False, True, True, False]).drop(columns=["_i", "_q"])
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
    "quanta": "Quanta", "廣達": "Quanta",
    "wiwynn": "Wiwynn", "緯穎": "Wiwynn",
    "wistron": "Wistron", "緯創": "Wistron",
    "inventec": "Inventec", "英業達": "Inventec",
    "foxconn": "Foxconn", "hon hai": "Foxconn", "鴻海": "Foxconn",
    "delta": "Delta Electronics", "台達電": "Delta Electronics",
    "accton": "Accton", "智邦": "Accton",
    "ase": "ASE", "ase technology": "ASE", "日月光": "ASE",
    "globalwafers": "GlobalWafers", "環球晶": "GlobalWafers",
    "mediatek": "MediaTek", "聯發科": "MediaTek",
    "aspeed": "ASPEED", "信驊": "ASPEED",
    "guc": "GUC", "創意": "GUC",
    "alchip": "Alchip", "世芯": "Alchip",
    "unimicron": "Unimicron", "欣興": "Unimicron",
    "nanya": "Nanya Tech", "南亞科": "Nanya Tech",
    "coreweave": "CoreWeave", "crwv": "CoreWeave",
    "astera labs": "Astera Labs", "alab": "Astera Labs",
    "arista": "Arista", "anet": "Arista",
    "vertiv": "Vertiv", "vrt": "Vertiv",
    "celestica": "Celestica", "cls": "Celestica",
    "coherent": "Coherent", "cohr": "Coherent",
    "lumentum": "Lumentum", "lite": "Lumentum",
    "fabrinet": "Fabrinet", "fn": "Fabrinet",
    "asml": "ASML",
    "lam research": "Lam Research", "lrcx": "Lam Research",
    "applied materials": "Applied Materials", "amat": "Applied Materials",
    "kla": "KLA", "klac": "KLA",
    "synopsys": "Synopsys", "snps": "Synopsys",
    "cadence": "Cadence", "cdns": "Cadence",
    "monolithic power": "Monolithic Power", "mpwr": "Monolithic Power",
    "teradyne": "Teradyne", "ter": "Teradyne",
    "amkor": "Amkor", "amkr": "Amkor",
}

COMPANY_LAYER = {
    "Arm": "上游 IP / 架構", "TSMC": "上游製造 / 代工", "Samsung": "上游製造 / 代工",
    "Intel": "中游晶片 / CPU", "AMD": "中游晶片 / CPU", "Nvidia": "中游晶片 / AI 平台",
    "Qualcomm": "中游晶片 / AI PC", "Apple": "終端 / 自研晶片",
    "Amazon": "下游雲端 / CSP", "AWS": "下游雲端 / CSP", "Microsoft": "下游雲端 / CSP",
    "Azure": "下游雲端 / CSP", "Google": "下游雲端 / CSP", "Meta": "下游雲端 / CSP", "Oracle": "下游雲端 / CSP",
    "Supermicro": "平台 / 伺服器 OEM", "Dell": "平台 / 伺服器 OEM", "HPE": "平台 / 伺服器 OEM", "Lenovo": "平台 / 伺服器 OEM",
    "Micron": "上游記憶體 / HBM", "SK hynix": "上游記憶體 / HBM", "Broadcom": "網通 / ASIC", "Marvell": "網通 / ASIC",
    "Quanta": "平台 / 伺服器 ODM", "Wiwynn": "平台 / 伺服器 ODM", "Wistron": "平台 / 伺服器 ODM",
    "Inventec": "平台 / 伺服器 ODM", "Foxconn": "平台 / 伺服器 ODM",
    "Delta Electronics": "電源 / 散熱", "Accton": "網通 / 交換器", "ASE": "封裝測試 / OSAT",
    "GlobalWafers": "上游矽晶圓", "MediaTek": "中游晶片 / SoC", "ASPEED": "伺服器管理晶片",
    "GUC": "ASIC 設計服務", "Alchip": "ASIC 設計服務", "Unimicron": "ABF / 載板", "Nanya Tech": "上游記憶體 / DRAM",
    "CoreWeave": "下游雲端 / AI Cloud", "Astera Labs": "連接 / Retimer", "Arista": "網通 / 交換器",
    "Vertiv": "電源 / 散熱", "Celestica": "平台 / 伺服器 ODM", "Coherent": "光通訊",
    "Lumentum": "光通訊", "Fabrinet": "光通訊 / 代工", "ASML": "半導體設備",
    "Lam Research": "半導體設備", "Applied Materials": "半導體設備", "KLA": "半導體設備",
    "Synopsys": "EDA / IP", "Cadence": "EDA / IP", "Monolithic Power": "電源 IC",
    "Teradyne": "半導體測試", "Amkor": "封裝測試 / OSAT",
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

COMPANY_GEO = {
    "Nvidia": {"lat": 37.3875, "lon": -121.9630, "country": "United States", "city": "Santa Clara"},
    "Intel": {"lat": 37.3875, "lon": -121.9630, "country": "United States", "city": "Santa Clara"},
    "AMD": {"lat": 37.4020, "lon": -121.9770, "country": "United States", "city": "Santa Clara"},
    "Arm": {"lat": 52.2053, "lon": 0.1218, "country": "United Kingdom", "city": "Cambridge"},
    "Qualcomm": {"lat": 32.7157, "lon": -117.1611, "country": "United States", "city": "San Diego"},
    "Apple": {"lat": 37.3349, "lon": -122.0090, "country": "United States", "city": "Cupertino"},
    "Amazon": {"lat": 47.6062, "lon": -122.3321, "country": "United States", "city": "Seattle"},
    "AWS": {"lat": 47.6062, "lon": -122.3321, "country": "United States", "city": "Seattle"},
    "Microsoft": {"lat": 47.6740, "lon": -122.1215, "country": "United States", "city": "Redmond"},
    "Azure": {"lat": 47.6740, "lon": -122.1215, "country": "United States", "city": "Redmond"},
    "Google": {"lat": 37.4220, "lon": -122.0841, "country": "United States", "city": "Mountain View"},
    "Meta": {"lat": 37.4847, "lon": -122.1484, "country": "United States", "city": "Menlo Park"},
    "Oracle": {"lat": 30.2672, "lon": -97.7431, "country": "United States", "city": "Austin"},
    "TSMC": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "Samsung": {"lat": 37.5665, "lon": 126.9780, "country": "South Korea", "city": "Seoul"},
    "Micron": {"lat": 43.6150, "lon": -116.2023, "country": "United States", "city": "Boise"},
    "SK hynix": {"lat": 37.2796, "lon": 127.4425, "country": "South Korea", "city": "Icheon"},
    "Broadcom": {"lat": 37.2638, "lon": -121.9630, "country": "United States", "city": "San Jose"},
    "Marvell": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "Santa Clara"},
    "Supermicro": {"lat": 37.3541, "lon": -121.9552, "country": "United States", "city": "San Jose"},
    "Dell": {"lat": 30.2672, "lon": -97.7431, "country": "United States", "city": "Austin"},
    "HPE": {"lat": 29.7604, "lon": -95.3698, "country": "United States", "city": "Houston"},
    "Lenovo": {"lat": 39.9042, "lon": 116.4074, "country": "China", "city": "Beijing"},
    "Quanta": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Wiwynn": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Wistron": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Inventec": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Foxconn": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "New Taipei"},
    "Delta Electronics": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Accton": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "ASE": {"lat": 22.6273, "lon": 120.3014, "country": "Taiwan", "city": "Kaohsiung"},
    "GlobalWafers": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "MediaTek": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "ASPEED": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "GUC": {"lat": 24.8138, "lon": 120.9686, "country": "Taiwan", "city": "Hsinchu"},
    "Alchip": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "Unimicron": {"lat": 24.9937, "lon": 121.3010, "country": "Taiwan", "city": "Taoyuan"},
    "Nanya Tech": {"lat": 25.0330, "lon": 121.5654, "country": "Taiwan", "city": "Taipei"},
    "CoreWeave": {"lat": 40.7128, "lon": -74.0060, "country": "United States", "city": "New York"},
    "Astera Labs": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "Santa Clara"},
    "Arista": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "Santa Clara"},
    "Vertiv": {"lat": 40.4173, "lon": -82.9071, "country": "United States", "city": "Ohio"},
    "Celestica": {"lat": 43.6532, "lon": -79.3832, "country": "Canada", "city": "Toronto"},
    "Coherent": {"lat": 40.4406, "lon": -79.9959, "country": "United States", "city": "Pittsburgh"},
    "Lumentum": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "San Jose"},
    "Fabrinet": {"lat": 13.7563, "lon": 100.5018, "country": "Thailand", "city": "Bangkok"},
    "ASML": {"lat": 51.4416, "lon": 5.4697, "country": "Netherlands", "city": "Veldhoven"},
    "Lam Research": {"lat": 37.5485, "lon": -121.9886, "country": "United States", "city": "Fremont"},
    "Applied Materials": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "Santa Clara"},
    "KLA": {"lat": 37.4323, "lon": -121.8996, "country": "United States", "city": "Milpitas"},
    "Synopsys": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "Sunnyvale"},
    "Cadence": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "San Jose"},
    "Monolithic Power": {"lat": 37.3688, "lon": -122.0363, "country": "United States", "city": "San Jose"},
    "Teradyne": {"lat": 42.3601, "lon": -71.0589, "country": "United States", "city": "Boston"},
    "Amkor": {"lat": 33.4484, "lon": -112.0740, "country": "United States", "city": "Tempe"},
}

LAYER_BUCKETS = {
    "上游": ["上游"],
    "中游": ["中游"],
    "平台/OEM": ["平台"],
    "下游": ["下游", "終端"],
    "其他": [],
}

POSITIVE_HINTS = ["surge", "gain", "beat", "raise", "bullish", "strong", "grow", "record", "上修", "受惠", "成長", "強勁", "創新高", "利多"]
NEGATIVE_HINTS = ["fall", "drop", "cut", "risk", "probe", "ban", "delay", "weak", "down", "miss", "下跌", "下修", "風險", "壓力", "禁令", "衝擊", "利空"]

def classify_company_status(texts: list) -> str:
    joined = ' '.join([str(x or '') for x in texts]).lower()
    pos = sum(1 for k in POSITIVE_HINTS if k.lower() in joined)
    neg = sum(1 for k in NEGATIVE_HINTS if k.lower() in joined)
    if pos >= neg + 2:
        return '正向'
    if neg >= pos + 2:
        return '負向'
    return '中性/觀察'


def layer_bucket(layer_text: str) -> str:
    layer_text = str(layer_text or '')
    for bucket, keys in LAYER_BUCKETS.items():
        if any(k in layer_text for k in keys):
            return bucket
    return '其他'



SNAPSHOT_DIR = Path(".radar_snapshots")
SUPPLY_CHAIN_MASTER_PATH = Path("supply_chain_master.csv")
CANDIDATE_PATH = Path(".radar_candidates/supply_chain_candidates.csv")


def candidate_columns():
    return ["candidate_type", "source_company", "target_company", "relation_type", "source_layer", "target_layer", "confidence", "status", "trend", "share_change", "change_reason", "evidence", "evidence_url", "first_seen", "last_seen", "seen_count", "review_status"]


@st.cache_data(ttl=3600, show_spinner=False)
def load_supply_chain_master() -> pd.DataFrame:
    cols = ["source_company", "target_company", "relation_type", "source_layer", "target_layer", "confidence", "status", "trend", "share_change", "change_reason", "evidence", "evidence_url", "valid_from", "valid_to", "last_checked"]
    if SUPPLY_CHAIN_MASTER_PATH.exists():
        try:
            df = pd.read_csv(SUPPLY_CHAIN_MASTER_PATH)
        except Exception:
            df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols].fillna("")


def load_supply_chain_candidates() -> pd.DataFrame:
    cols = candidate_columns()
    if CANDIDATE_PATH.exists():
        try:
            df = pd.read_csv(CANDIDATE_PATH)
        except Exception:
            df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["seen_count"] = pd.to_numeric(df["seen_count"], errors="coerce").fillna(0).astype(int)
    return df[cols].fillna("")


def save_supply_chain_candidates(df: pd.DataFrame):
    CANDIDATE_PATH.parent.mkdir(exist_ok=True)
    cols = candidate_columns()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df[cols].to_csv(CANDIDATE_PATH, index=False, encoding="utf-8-sig")


def infer_relation_confidence(row) -> str:
    evidence = str(row.get("evidence", "") or "").lower()
    relation = str(row.get("relation", "") or "").lower()
    if "產業字典關係" in evidence or "供應鏈主檔" in evidence:
        return "低｜背景"
    explicit_terms = ["supplier", "supply", "customer", "contract", "deal", "selected", "wins", "partnership", "adopts", "order", "qualified", "供應", "客戶", "合約", "合作", "採用", "導入", "訂單", "認證"]
    if any(t in evidence for t in explicit_terms) or any(t in relation for t in explicit_terms):
        return "高｜新聞明確線索"
    if evidence.strip():
        return "中｜共現 / 題材關聯"
    return "低｜待確認"


def infer_supply_chain_status(row) -> str:
    text = " ".join([str(row.get("relation", "") or ""), str(row.get("evidence", "") or "")]).lower()
    exit_terms = ["terminate", "cancel", "drop", "loses", "lost", "exit", "withdraw", "ban", "restriction", "blocked", "delay", "halt", "解約", "取消", "中止", "退出", "禁令", "限制", "延後", "轉單"]
    add_terms = ["new supplier", "selected", "wins", "signs", "deal", "partnership", "adopts", "order", "ramp", "expands", "qualified", "新增", "入選", "合作", "採用", "導入", "訂單", "擴大", "放量", "認證", "打入"]
    if any(t in text for t in exit_terms):
        return "退出 / 中斷風險"
    if any(t in text for t in add_terms):
        return "新加入 / 擴大合作候選"
    if "供應鏈主檔" in text or "產業字典關係" in text:
        return "既有關係背景"
    return "待確認"


def infer_relationship_trend(row) -> str:
    text = " ".join([str(row.get("relation", "") or ""), str(row.get("evidence", "") or ""), str(row.get("supply_chain_status", "") or "")]).lower()
    up_terms = ["expand", "increase", "gain", "wins", "order", "ramp", "qualified", "share gain", "擴大", "增加", "提升", "放量", "訂單", "認證", "打入"]
    down_terms = ["reduce", "decrease", "loss", "lost", "cut", "cancel", "delay", "ban", "restriction", "share loss", "減少", "下降", "轉單", "取消", "延後", "禁令", "限制"]
    if any(t in text for t in up_terms):
        return "份額/合作上升候選"
    if any(t in text for t in down_terms):
        return "份額/合作下降風險"
    return "未偵測明確變化"


def master_confidence_label(conf: str) -> str:
    c = str(conf or "").lower()
    if c in ["confirmed", "official", "high"]:
        return "高｜主檔確認"
    if c in ["likely", "medium"]:
        return "中｜主檔 likely"
    if c in ["rumor", "low"]:
        return "低｜主檔待確認"
    return "低｜主檔背景"


def infer_master_edge_group(relation_type: str) -> str:
    r = str(relation_type or "").lower()
    if any(x in r for x in ["competitor", "competition", "競爭"]):
        return "競爭"
    if any(x in r for x in ["theme", "impact", "topic", "事件"]):
        return "事件傳導"
    return "供應鏈"


def normalize_master_status(status: str, trend: str = "", share_change: str = "") -> str:
    txt = " ".join([str(status or ""), str(trend or ""), str(share_change or "")]).lower()
    if any(x in txt for x in ["exit", "exited", "reduced", "decrease", "down", "lost", "退出", "減少", "降低", "轉單"]):
        return "退出 / 份額下降"
    if any(x in txt for x in ["new", "expanded", "increase", "up", "gain", "新增", "擴大", "增加", "提升"]):
        return "新加入 / 份額上升"
    if "active" in txt or "confirmed" in txt:
        return "既有關係背景"
    return "待確認"


def overlay_master_supply_chain(companies: pd.DataFrame, edges: pd.DataFrame, master: pd.DataFrame):
    if edges is None or edges.empty:
        edges = pd.DataFrame(columns=["source", "target", "relation", "strength", "evidence", "edge_group", "confidence", "supply_chain_status", "trend_signal"])
    if companies is None or companies.empty or master is None or master.empty:
        return companies, edges
    companies = companies.copy(); edges = edges.copy()
    appeared = set(companies["node"].tolist())
    existing_nodes = set(companies["node"].tolist())
    add_nodes = []; add_edges = []
    for _, row in master.iterrows():
        src = str(row.get("source_company", "")).strip(); dst = str(row.get("target_company", "")).strip()
        if not src or not dst or not (src in appeared or dst in appeared):
            continue
        for comp, layer_col in [(src, "source_layer"), (dst, "target_layer")]:
            if comp not in existing_nodes:
                layer = row.get(layer_col, COMPANY_LAYER.get(comp, "公司"))
                add_nodes.append({"node": comp, "type": "公司", "layer": layer, "count": 0, "layer_bucket": layer_bucket(layer), "country": COMPANY_GEO.get(comp, {}).get("country", ""), "city": COMPANY_GEO.get(comp, {}).get("city", ""), "lat": COMPANY_GEO.get(comp, {}).get("lat"), "lon": COMPANY_GEO.get(comp, {}).get("lon"), "news_hits": 0, "status": "主檔背景", "top_news": "", "top_categories": "供應鏈主檔"})
                existing_nodes.add(comp)
        rel_type = str(row.get("relation_type", "") or "master relation")
        status = normalize_master_status(row.get("status", ""), row.get("trend", ""), row.get("share_change", ""))
        reason = str(row.get("change_reason", "") or row.get("evidence", "") or "固定供應鏈主檔背景")
        add_edges.append({"source": src, "target": dst, "relation": f"主檔：{rel_type}", "strength": 1, "evidence": f"供應鏈主檔｜{reason}", "edge_group": infer_master_edge_group(rel_type), "confidence": master_confidence_label(row.get("confidence", "")), "supply_chain_status": status, "trend_signal": status, "master_status": row.get("status", ""), "master_confidence": row.get("confidence", ""), "change_reason": row.get("change_reason", ""), "evidence_url": row.get("evidence_url", "")})
    if add_nodes:
        companies = pd.concat([companies, pd.DataFrame(add_nodes)], ignore_index=True).drop_duplicates(subset=["node"], keep="first")
    if add_edges:
        edges = pd.concat([edges, pd.DataFrame(add_edges)], ignore_index=True).drop_duplicates(subset=["source", "target", "relation"], keep="first")
    return companies, edges


def build_master_candidate_rows(companies: pd.DataFrame, edges: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    rows = []; now = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y-%m-%d %H:%M:%S")
    master_companies = set(); master_edges = set()
    if master is not None and not master.empty:
        master_companies.update(master["source_company"].dropna().astype(str).str.strip().tolist())
        master_companies.update(master["target_company"].dropna().astype(str).str.strip().tolist())
        master_edges = set((master["source_company"].astype(str).str.strip() + "→" + master["target_company"].astype(str).str.strip() + "｜" + master["relation_type"].astype(str).str.strip()).tolist())
    if companies is not None and not companies.empty:
        for _, c in companies.iterrows():
            comp = str(c.get("node", "")).strip()
            if not comp or comp in master_companies or int(c.get("news_hits", 0) or 0) <= 0:
                continue
            rows.append({"candidate_type": "new_company", "source_company": comp, "target_company": "", "relation_type": "company_node", "source_layer": c.get("layer", ""), "target_layer": "", "confidence": "pending", "status": "pending_review", "trend": "", "share_change": "", "change_reason": "搜尋結果出現主檔尚未收錄的公司節點", "evidence": c.get("top_news", ""), "evidence_url": "", "first_seen": now, "last_seen": now, "seen_count": 1, "review_status": "pending"})
    if edges is not None and not edges.empty:
        for _, e in edges.iterrows():
            src = str(e.get("source", "")).strip(); dst = str(e.get("target", "")).strip(); rel = str(e.get("relation", "")).strip()
            if not src or not dst or not rel or rel.startswith("主檔"):
                continue
            key = f"{src}→{dst}｜{rel}"
            if key in master_edges:
                continue
            conf = str(e.get("confidence", "")); evidence = str(e.get("evidence", ""))
            if conf.startswith("低") and ("產業字典" in evidence or "主檔" in evidence):
                continue
            rows.append({"candidate_type": "new_relation", "source_company": src, "target_company": dst, "relation_type": rel, "source_layer": COMPANY_LAYER.get(src, ""), "target_layer": COMPANY_LAYER.get(dst, ""), "confidence": conf or "pending", "status": e.get("supply_chain_status", "待確認"), "trend": e.get("trend_signal", ""), "share_change": "待確認", "change_reason": e.get("supply_chain_status", "待確認"), "evidence": evidence, "evidence_url": "", "first_seen": now, "last_seen": now, "seen_count": 1, "review_status": "pending"})
    return pd.DataFrame(rows, columns=candidate_columns())


def merge_candidates(new_candidates: pd.DataFrame) -> pd.DataFrame:
    old = load_supply_chain_candidates()
    if new_candidates is None or new_candidates.empty:
        return old
    combined = old.copy(); now = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y-%m-%d %H:%M:%S")
    def key_of(row):
        if row.get("candidate_type") == "new_company":
            return f"company::{row.get('source_company','')}"
        return f"relation::{row.get('source_company','')}→{row.get('target_company','')}｜{row.get('relation_type','')}"
    combined["_key"] = combined.apply(key_of, axis=1) if not combined.empty else []
    for _, row in new_candidates.iterrows():
        key = key_of(row)
        if not combined.empty and key in set(combined["_key"]):
            idx = combined.index[combined["_key"] == key][0]
            combined.at[idx, "last_seen"] = now
            combined.at[idx, "seen_count"] = int(combined.at[idx, "seen_count"] or 0) + 1
            if len(str(row.get("evidence", ""))) > len(str(combined.at[idx, "evidence"])):
                combined.at[idx, "evidence"] = row.get("evidence", "")
        else:
            d = row.to_dict(); d["first_seen"] = d.get("first_seen") or now; d["last_seen"] = now; d["seen_count"] = int(d.get("seen_count") or 1); d["review_status"] = d.get("review_status") or "pending"; d["_key"] = key
            combined = pd.concat([combined, pd.DataFrame([d])], ignore_index=True)
    combined = combined.drop(columns=["_key"], errors="ignore")
    save_supply_chain_candidates(combined)
    return combined


def minimal_snapshot_payload(feed: pd.DataFrame, companies: pd.DataFrame, edges: pd.DataFrame, query: str, time_range: str, freshness_mode: str) -> dict:
    def safe_records(df, cols, limit):
        if df is None or df.empty:
            return []
        keep = [c for c in cols if c in df.columns]
        return df[keep].head(limit).astype(str).to_dict("records")
    return {"created_at": pd.Timestamp.now(tz="Asia/Taipei").isoformat(), "query": query, "time_range": time_range, "freshness_mode": freshness_mode, "news": safe_records(feed, ["time_utc", "title_zh", "title", "url", "domain", "category", "importance", "heat_score", "freshness_label"], 80), "companies": safe_records(companies, ["node", "layer", "layer_bucket", "status", "news_hits", "top_categories"], 80), "edges": safe_records(edges, ["source", "target", "relation", "edge_group", "confidence", "supply_chain_status", "trend_signal", "strength", "evidence"], 120)}


def cleanup_snapshots(max_files: int = 30, max_days: int = 14):
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").timestamp()
    for p in sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if (now - p.stat().st_mtime) / 86400 > max_days:
            try: p.unlink()
            except Exception: pass
    files = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    for p in files[max_files:]:
        try: p.unlink()
        except Exception: pass


def save_snapshot(payload: dict, max_files: int = 30, max_days: int = 14) -> str:
    SNAPSHOT_DIR.mkdir(exist_ok=True); cleanup_snapshots(max_files, max_days)
    path = SNAPSHOT_DIR / f"snapshot_{pd.Timestamp.now(tz='Asia/Taipei').strftime('%Y%m%d_%H%M%S')}.json"
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"); cleanup_snapshots(max_files, max_days); return str(path)
    except Exception:
        return ""


def load_snapshots(limit: int = 12) -> list:
    SNAPSHOT_DIR.mkdir(exist_ok=True); out = []
    for p in sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try: out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception: pass
    return out


def compare_snapshots(current: dict, previous: dict) -> dict:
    def edge_key(e): return f"{e.get('source','')}→{e.get('target','')}｜{e.get('relation','')}"
    curr = {edge_key(e): e for e in current.get("edges", [])}; prev = {edge_key(e): e for e in previous.get("edges", [])} if previous else {}
    changed = []
    for k in curr.keys() & prev.keys():
        c, p = curr[k], prev[k]
        if c.get("supply_chain_status") != p.get("supply_chain_status") or c.get("trend_signal") != p.get("trend_signal"):
            changed.append({"key": k, "before": p, "after": c})
    curr_c = {c.get("node", ""): c for c in current.get("companies", [])}; prev_c = {c.get("node", ""): c for c in previous.get("companies", [])} if previous else {}
    return {"added_edges": [curr[k] for k in curr.keys() - prev.keys()][:30], "removed_edges": [prev[k] for k in prev.keys() - curr.keys()][:30], "changed_edges": changed[:30], "added_companies": [curr_c[k] for k in curr_c.keys() - prev_c.keys()][:30], "removed_companies": [prev_c[k] for k in prev_c.keys() - curr_c.keys()][:30]}


def render_delta_radar(current_payload: dict | None = None):
    st.subheader("Delta Radar｜前後版本比較")
    snapshots = load_snapshots(12)
    if not snapshots:
        st.info("目前還沒有 snapshot。請先搜尋一次。")
        return
    if current_payload is None:
        current_payload = snapshots[0]; previous = snapshots[1] if len(snapshots) > 1 else {}
    else:
        previous = snapshots[0] if snapshots else {}
    st.markdown(f"**目前快照：** {current_payload.get('created_at','')}")
    if not previous:
        st.info("只有一份 snapshot，暫時無法比較前後差異。")
        return
    st.markdown(f"**比較基準：** {previous.get('created_at','')}")
    delta = compare_snapshots(current_payload, previous)
    c1, c2, c3 = st.columns(3); c1.metric("新增關係", len(delta["added_edges"])); c2.metric("狀態變化", len(delta["changed_edges"])); c3.metric("消失 / 降溫關係", len(delta["removed_edges"]))
    with st.expander("新增公司節點", expanded=False): st.dataframe(pd.DataFrame(delta["added_companies"]), use_container_width=True)
    with st.expander("新增關係", expanded=True): st.dataframe(pd.DataFrame(delta["added_edges"]), use_container_width=True)
    with st.expander("關係狀態變化", expanded=True):
        if delta["changed_edges"]:
            rows = [{"key": x["key"], "before_status": x["before"].get("supply_chain_status"), "after_status": x["after"].get("supply_chain_status"), "before_trend": x["before"].get("trend_signal"), "after_trend": x["after"].get("trend_signal"), "evidence": x["after"].get("evidence")} for x in delta["changed_edges"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else: st.info("沒有偵測到狀態變化。")
    with st.expander("消失 / 降溫關係", expanded=False): st.dataframe(pd.DataFrame(delta["removed_edges"]), use_container_width=True)
    with st.expander("Snapshot 管理"):
        st.write(f"目前本機 snapshot 數：{len(snapshots)}")
        if st.button("清空本機 snapshots"):
            for p in SNAPSHOT_DIR.glob("snapshot_*.json"):
                try: p.unlink()
                except Exception: pass
            st.success("已清空。請重新整理畫面。")


def render_master_candidate_queue():
    st.subheader("主檔候選增補")
    st.caption("搜尋只會把新公司 / 新關係放到候選清單，不會直接污染正式 supply_chain_master.csv。確認後再手動合併。")
    cand = load_supply_chain_candidates()
    if cand.empty:
        st.info("目前沒有候選資料。搜尋幾次後，如果出現主檔沒有的新公司或新關係，會自動出現在這裡。")
        return
    pending = cand[cand["review_status"].astype(str).str.lower().eq("pending")]
    c1, c2, c3 = st.columns(3); c1.metric("候選總數", len(cand)); c2.metric("待審核", len(pending)); c3.metric("高頻候選", int((cand["seen_count"].astype(int) >= 2).sum()))
    st.dataframe(cand.sort_values(["seen_count", "last_seen"], ascending=[False, False]), use_container_width=True)
    st.download_button("下載候選清單 CSV", data=cand.to_csv(index=False).encode("utf-8-sig"), file_name="supply_chain_candidates.csv", mime="text/csv", use_container_width=True)
    st.caption("建議：seen_count >= 2 且 confidence 不是低信心者，優先人工確認後再加入 supply_chain_master.csv。")
    if st.button("清空候選清單"):
        try:
            if CANDIDATE_PATH.exists(): CANDIDATE_PATH.unlink()
            st.success("已清空候選清單。")
        except Exception as exc:
            st.error(f"清空失敗：{exc}")

def build_company_supply_chain_snapshot(feed: pd.DataFrame, max_news: int = 80):
    nodes_df, edges_df, summary = build_industry_relationships(feed, max_news=max_news)
    if nodes_df is None or nodes_df.empty:
        return pd.DataFrame(), pd.DataFrame(), summary

    companies = nodes_df[nodes_df['type'] == '公司'].copy()
    if companies.empty:
        return pd.DataFrame(), pd.DataFrame(), summary

    companies['layer_bucket'] = companies['layer'].apply(layer_bucket)
    companies['country'] = companies['node'].map(lambda x: COMPANY_GEO.get(x, {}).get('country', ''))
    companies['city'] = companies['node'].map(lambda x: COMPANY_GEO.get(x, {}).get('city', ''))
    companies['lat'] = companies['node'].map(lambda x: COMPANY_GEO.get(x, {}).get('lat'))
    companies['lon'] = companies['node'].map(lambda x: COMPANY_GEO.get(x, {}).get('lon'))

    article_rows = []
    if feed is not None and not feed.empty:
        news = feed[feed['data_type'] == '公司/財經新聞'].copy()
        for _, row in news.iterrows():
            text = ' '.join([str(row.get('title', '')), str(row.get('title_zh', '')), str(row.get('summary', '')), str(row.get('category', ''))])
            comps = extract_companies_from_text(text)
            for comp in comps:
                article_rows.append({'company': comp, 'title_zh': row.get('title_zh') or row.get('title') or '', 'category': row.get('category', ''), 'importance': row.get('importance', ''), 'freshness_label': row.get('freshness_label', ''), 'text': text, 'url': row.get('url', '')})
    article_df = pd.DataFrame(article_rows)

    if not article_df.empty:
        grouped = article_df.groupby('company')
        companies['news_hits'] = companies['node'].map(grouped.size()).fillna(0).astype(int)
        companies['status'] = companies['node'].map(lambda x: classify_company_status(grouped.get_group(x)['text'].tolist()) if x in grouped.groups else '中性/觀察')
        companies['top_news'] = companies['node'].map(lambda x: '｜'.join(grouped.get_group(x)['title_zh'].head(3).tolist()) if x in grouped.groups else '')
        companies['top_categories'] = companies['node'].map(lambda x: '、'.join(pd.Series(grouped.get_group(x)['category']).dropna().astype(str).value_counts().head(3).index.tolist()) if x in grouped.groups else '')
    else:
        companies['news_hits'] = companies['count']; companies['status'] = '中性/觀察'; companies['top_news'] = ''; companies['top_categories'] = ''

    if edges_df is None or edges_df.empty:
        edges = pd.DataFrame(columns=['source','target','relation','strength','evidence','edge_group','confidence','supply_chain_status','trend_signal'])
    else:
        edges = edges_df.copy(); edges['edge_group'] = '其他'
        edges.loc[edges['relation'].str.contains('供應|客戶|代工|平台|雲端', na=False), 'edge_group'] = '供應鏈'
        edges.loc[edges['relation'].str.contains('競爭|替代|威脅', na=False), 'edge_group'] = '競爭'
        edges.loc[edges['relation'].str.contains('事件影響|題材', na=False), 'edge_group'] = '事件傳導'
        edges['confidence'] = edges.apply(infer_relation_confidence, axis=1)
        edges['supply_chain_status'] = edges.apply(infer_supply_chain_status, axis=1)
        edges['trend_signal'] = edges.apply(infer_relationship_trend, axis=1)
        edges['master_status'] = ''; edges['master_confidence'] = ''; edges['change_reason'] = ''; edges['evidence_url'] = ''

    companies, edges = overlay_master_supply_chain(companies, edges, load_supply_chain_master())
    return companies.sort_values(['news_hits', 'count', 'node'], ascending=[False, False, True]), edges, summary


def render_company_cards(df: pd.DataFrame, title: str):
    st.markdown(f"#### {title}")
    if df is None or df.empty:
        st.info('目前無資料')
        return
    for _, row in df.iterrows():
        company = row.get('node', '')
        layer = row.get('layer', '')
        status = row.get('status', '中性/觀察')
        hits = int(row.get('news_hits', row.get('count', 0) or 0))
        categories = row.get('top_categories', '')
        top_news = row.get('top_news', '')
        color = '#16a34a' if status == '正向' else ('#dc2626' if status == '負向' else '#f59e0b')
        st.markdown(
            f"""
            <div style="border:1px solid rgba(128,128,128,0.25);border-radius:12px;padding:10px 12px;margin:8px 0;background:rgba(128,128,128,0.06);">
                <div style="font-weight:800;font-size:1rem;">{company}</div>
                <div style="font-size:0.86rem;opacity:0.8;">{layer}</div>
                <div style="margin-top:6px;font-size:0.9rem;">
                    <span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{color};color:white;font-size:0.78rem;">{status}</span>
                    <span style="margin-left:8px;">提及 {hits} 次</span>
                </div>
                <div style="margin-top:6px;font-size:0.84rem;opacity:0.85;">主題：{categories or '—'}</div>
                <div style="margin-top:6px;font-size:0.82rem;opacity:0.72;">{(top_news or '暫無摘要')[:120]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )



def company_label_html(name: str, selected: bool = False) -> str:
    """High-contrast permanent map label."""
    bg = "rgba(255,255,255,0.96)"
    border = "#111827" if selected else "#334155"
    color = "#111827"
    size = "13px" if selected else "12px"
    weight = "900" if selected else "800"
    safe = html.escape(str(name or ""))
    return (
        f"<div style='"
        f"font-size:{size};font-weight:{weight};color:{color} !important;"
        f"white-space:nowrap;background:{bg};padding:3px 7px;border-radius:8px;"
        f"border:1.5px solid {border};box-shadow:0 2px 7px rgba(0,0,0,0.32);"
        f"line-height:1.15;letter-spacing:0.1px;transform:translate(10px,-8px);"
        f"z-index:9999;position:relative;'>"
        f"{safe}</div>"
    )


def is_master_background_edge(row) -> bool:
    rel = str(row.get("relation", ""))
    ev = str(row.get("evidence", ""))
    return rel.startswith("主檔") or ("供應鏈主檔" in ev)


def apply_realtime_verification_to_edges(edges_df: pd.DataFrame, verified_df: pd.DataFrame) -> pd.DataFrame:
    if edges_df is None:
        edges_df = pd.DataFrame()
    if edges_df.empty:
        return edges_df
    out = edges_df.copy()
    for col in ["verified_status", "verified_trend", "verified_title", "verified_domain", "verified_url"]:
        if col not in out.columns:
            out[col] = ""

    if verified_df is None or verified_df.empty:
        return out

    # First evidence per pair. Match both directions because relationship extraction can be non-directional.
    records = {}
    for _, v in verified_df.iterrows():
        src = str(v.get("source_company", "")).strip()
        dst = str(v.get("target_company", "")).strip()
        if not src or not dst:
            continue
        payload = {
            "verified_status": v.get("verification_status", ""),
            "verified_trend": v.get("trend_signal", ""),
            "verified_title": v.get("evidence_title", ""),
            "verified_domain": v.get("domain", ""),
            "verified_url": v.get("url", ""),
        }
        records.setdefault((src, dst), payload)
        records.setdefault((dst, src), payload)

    for i, row in out.iterrows():
        key = (str(row.get("source", "")).strip(), str(row.get("target", "")).strip())
        if key in records:
            for k, val in records[key].items():
                out.at[i, k] = val
            # Use verification to refine relation status, but keep original fields too.
            if records[key].get("verified_status"):
                out.at[i, "confidence"] = records[key]["verified_status"]
            if records[key].get("verified_trend"):
                out.at[i, "trend_signal"] = records[key]["verified_trend"]

    return out


def get_news_driven_supply_chain_view(companies_df: pd.DataFrame, edges_df: pd.DataFrame, verified_df: pd.DataFrame | None = None):
    """Return a news-driven view for schemes A/B/C.

    Master background is removed from the main view. It can still exist as context elsewhere,
    but schemes A/B/C should reflect this search's news and auto-verification results.
    """
    if companies_df is None:
        companies_df = pd.DataFrame()
    if edges_df is None:
        edges_df = pd.DataFrame()

    companies = companies_df.copy()
    edges = edges_df.copy()

    if not edges.empty:
        edges = edges[~edges.apply(is_master_background_edge, axis=1)].copy()
        edges = apply_realtime_verification_to_edges(edges, verified_df)

    # Keep companies actually mentioned in this search, plus endpoints of news-driven edges and verified pairs.
    keep_nodes = set()
    if not companies.empty and "news_hits" in companies.columns:
        keep_nodes.update(companies[companies["news_hits"].fillna(0).astype(int) > 0]["node"].astype(str).tolist())
    if not edges.empty:
        keep_nodes.update(edges["source"].dropna().astype(str).tolist())
        keep_nodes.update(edges["target"].dropna().astype(str).tolist())
    if verified_df is not None and not verified_df.empty:
        keep_nodes.update(verified_df["source_company"].dropna().astype(str).tolist())
        keep_nodes.update(verified_df["target_company"].dropna().astype(str).tolist())

    if keep_nodes and not companies.empty:
        companies = companies[companies["node"].astype(str).isin(keep_nodes)].copy()
    elif not companies.empty and "news_hits" in companies.columns:
        companies = companies[companies["news_hits"].fillna(0).astype(int) > 0].copy()

    return companies, edges


def draw_supply_chain_geo_map(companies_df: pd.DataFrame, edges_df: pd.DataFrame):
    m = folium.Map(location=[22, 10], zoom_start=2, min_zoom=1, tiles='CartoDB positron', control_scale=True, world_copy_jump=True)
    if companies_df is None or companies_df.empty:
        return m

    supply_fg = folium.FeatureGroup(name='供應鏈連線', show=True).add_to(m)
    compete_fg = folium.FeatureGroup(name='競爭連線', show=False).add_to(m)
    event_fg = folium.FeatureGroup(name='事件傳導', show=False).add_to(m)
    node_fg = folium.FeatureGroup(name='公司節點', show=True).add_to(m)

    company_lookup = companies_df.set_index('node').to_dict('index')

    if edges_df is not None and not edges_df.empty:
        for _, row in edges_df.iterrows():
            src = row.get('source')
            dst = row.get('target')
            if src not in company_lookup or dst not in company_lookup:
                continue
            s = company_lookup[src]
            d = company_lookup[dst]
            if pd.isna(s.get('lat')) or pd.isna(d.get('lat')):
                continue
            group = row.get('edge_group', '其他')
            verified_trend = str(row.get('verified_trend', row.get('trend_signal', '')) or '')
            if '中斷' in verified_trend or '下降' in verified_trend:
                color = '#dc2626'
            elif '新增' in verified_trend or '擴大' in verified_trend or '上升' in verified_trend:
                color = '#16a34a'
            else:
                color = '#2f80ed' if group == '供應鏈' else ('#eb5757' if group == '競爭' else '#f2994a')
            target_layer = supply_fg if group == '供應鏈' else (compete_fg if group == '競爭' else event_fg)
            evidence_bits = [
                str(row.get('evidence','')),
                str(row.get('verified_status','')),
                str(row.get('verified_title','')),
                str(row.get('verified_domain','')),
            ]
            popup = folium.Popup(f"<b>{html.escape(str(src))} → {html.escape(str(dst))}</b><br>{html.escape(str(row.get('relation','')))}<br><small>{html.escape('｜'.join([x for x in evidence_bits if x]))}</small>", max_width=420)
            folium.PolyLine(
                locations=[(float(s['lat']), float(s['lon'])), (float(d['lat']), float(d['lon']))],
                color=color,
                weight=2 + min(int(row.get('strength', 1)), 4),
                opacity=0.75,
                popup=popup,
                tooltip=f"{src} → {dst}｜{row.get('relation','')}",
            ).add_to(target_layer)

    for _, row in companies_df.iterrows():
        if pd.isna(row.get('lat')) or pd.isna(row.get('lon')):
            continue
        status = row.get('status', '中性/觀察')
        color = '#16a34a' if status == '正向' else ('#dc2626' if status == '負向' else '#f59e0b')
        popup = f"""
        <div style="width:320px;font-size:13px;">
            <b>{html.escape(str(row.get('node','')))}</b><br>
            {html.escape(str(row.get('city','')))} / {html.escape(str(row.get('country','')))}<br>
            角色：{html.escape(str(row.get('layer','')))}<br>
            狀態：{html.escape(str(status))}<br>
            提及次數：{int(row.get('news_hits', row.get('count', 0) or 0))}<br>
            主題：{html.escape(str(row.get('top_categories','')))}<br>
            <small>{html.escape(str(row.get('top_news','')))}</small>
        </div>
        """
        folium.CircleMarker(
            location=[float(row['lat']), float(row['lon'])],
            radius=7 + min(int(row.get('news_hits', row.get('count', 0) or 0)), 8),
            color='white',
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(popup, max_width=360),
            tooltip=f"{row.get('node')}｜{row.get('layer_bucket')}｜{status}",
        ).add_to(node_fg)
        folium.map.Marker(
            [float(row['lat']), float(row['lon'])],
            icon=folium.DivIcon(html=company_label_html(str(row.get('node'))))
        ).add_to(node_fg)

    folium.LayerControl(collapsed=True).add_to(m)
    return m


def render_supply_chain_layered_sheet(companies_df: pd.DataFrame, edges_df: pd.DataFrame):
    st.caption('方案 B：新聞驅動分層圖。只顯示本次新聞提到或自動驗證涉及的公司/關係，不再把主檔固定背景塞進主畫面。')
    if companies_df is None or companies_df.empty:
        st.info('本次新聞沒有足夠公司資料可建立供應鏈分層圖。')
        return

    news_companies = companies_df.copy()
    if 'news_hits' in news_companies.columns:
        news_companies = news_companies.sort_values(['news_hits', 'count', 'node'], ascending=[False, False, True])

    layer_order = ['上游', '中游', '平台/OEM', '下游', '其他']
    cols = st.columns(len(layer_order))
    for idx, bucket in enumerate(layer_order):
        with cols[idx]:
            render_company_cards(news_companies[news_companies['layer_bucket'] == bucket].head(8), bucket)

    st.markdown('### 本次新聞 / 自動驗證抽出的供應鏈關係')
    if edges_df is None or edges_df.empty:
        st.info('本次新聞沒有抽出明確的供應鏈連線。')
    else:
        show = edges_df[edges_df['edge_group'].isin(['供應鏈', '事件傳導', '競爭'])].copy()
        if show.empty:
            show = edges_df.copy()
        cols = ['source','target','edge_group','relation','confidence','supply_chain_status','trend_signal',
                'verified_status','verified_trend','verified_title','verified_domain','verified_url','strength','evidence']
        st.dataframe(show[[c for c in cols if c in show.columns]].head(100), use_container_width=True)

        st.markdown('### 自動驗證重點')
        verified_rows = show[show.get('verified_status', pd.Series([''] * len(show))).astype(str).str.len() > 0] if not show.empty else pd.DataFrame()
        if verified_rows.empty:
            st.caption('目前沒有自動驗證到可用證據，或查詢還沒完成。')
        else:
            for _, r in verified_rows.head(12).iterrows():
                url = str(r.get('verified_url', '') or '')
                title = html.escape(str(r.get('verified_title', '') or '無標題'))
                link = f"<a href='{html.escape(url)}' target='_blank'>{title}</a>" if url.startswith('http') else title
                st.markdown(
                    f"""
                    <div style="border:1px solid rgba(128,128,128,0.25);border-radius:12px;padding:10px 12px;margin:8px 0;background:rgba(128,128,128,0.06);">
                    <b>{html.escape(str(r.get('source','')))} → {html.escape(str(r.get('target','')))}</b><br>
                    關係：{html.escape(str(r.get('relation','')))}<br>
                    驗證：{html.escape(str(r.get('verified_status','')))}｜{html.escape(str(r.get('verified_trend','')))}<br>
                    證據：{link}<br>
                    <small>{html.escape(str(r.get('verified_domain','')))}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

def render_map_with_panel_sheet(companies_df: pd.DataFrame, edges_df: pd.DataFrame):
    st.caption('方案 C：左邊看地圖，右邊看公司狀態面板；適合你直接點一家公司，立刻看上下游、競爭與新聞。')
    if companies_df is None or companies_df.empty:
        st.info('目前沒有足夠公司資料可建立公司面板。')
        return

    company_list = companies_df['node'].dropna().tolist()
    default_index = 0
    selected = st.selectbox('選擇公司節點', company_list, index=default_index)
    left, right = st.columns([1.3, 1])

    with left:
        base_map = folium.Map(location=[22, 10], zoom_start=2, min_zoom=1, tiles='CartoDB positron', control_scale=True, world_copy_jump=True)
        selected_row = companies_df[companies_df['node'] == selected].iloc[0]
        related = edges_df[(edges_df['source'] == selected) | (edges_df['target'] == selected)].copy() if edges_df is not None and not edges_df.empty else pd.DataFrame()
        related_nodes = set([selected])
        if not related.empty:
            related_nodes.update(related['source'].tolist())
            related_nodes.update(related['target'].tolist())
        mini_df = companies_df[companies_df['node'].isin(related_nodes)].copy()
        mini_lookup = mini_df.set_index('node').to_dict('index')
        if not related.empty:
            for _, row in related.iterrows():
                src, dst = row.get('source'), row.get('target')
                if src not in mini_lookup or dst not in mini_lookup:
                    continue
                s, d = mini_lookup[src], mini_lookup[dst]
                if pd.isna(s.get('lat')) or pd.isna(d.get('lat')):
                    continue
                group = row.get('edge_group', '其他')
                color = '#2f80ed' if group == '供應鏈' else ('#eb5757' if group == '競爭' else '#f2994a')
                folium.PolyLine([(float(s['lat']), float(s['lon'])), (float(d['lat']), float(d['lon']))], color=color, weight=3, opacity=0.8, tooltip=f"{src} → {dst}｜{row.get('relation','')}").add_to(base_map)
        for _, row in mini_df.iterrows():
            if pd.isna(row.get('lat')) or pd.isna(row.get('lon')):
                continue
            is_selected = row.get('node') == selected
            fill = '#111827' if is_selected else ('#16a34a' if row.get('status') == '正向' else ('#dc2626' if row.get('status') == '負向' else '#f59e0b'))
            folium.CircleMarker(location=[float(row['lat']), float(row['lon'])], radius=10 if is_selected else 7, color='white', weight=2, fill=True, fill_color=fill, fill_opacity=0.95, tooltip=f"{row.get('node')}｜{row.get('layer')}").add_to(base_map)
            folium.map.Marker(
                [float(row['lat']), float(row['lon'])],
                icon=folium.DivIcon(html=company_label_html(str(row.get('node')), selected=is_selected))
            ).add_to(base_map)
        st_folium(base_map, width=None, height=520, returned_objects=[], key='company_panel_map')

    with right:
        st.markdown(f"### {selected}")
        st.markdown(f"**角色：** {selected_row.get('layer', '')}")
        st.markdown(f"**地點：** {selected_row.get('city', '')}, {selected_row.get('country', '')}")
        st.markdown(f"**狀態：** {selected_row.get('status', '中性/觀察')}")
        st.markdown(f"**新聞提及：** {int(selected_row.get('news_hits', selected_row.get('count', 0) or 0))} 次")
        st.markdown(f"**主題：** {selected_row.get('top_categories', '') or '—'}")
        st.markdown('**近期新聞摘要：**')
        st.write(selected_row.get('top_news', '') or '目前沒有摘要。')

        if edges_df is not None and not edges_df.empty:
            related = edges_df[(edges_df['source'] == selected) | (edges_df['target'] == selected)].copy()
            up = related[related['relation'].str.contains('供應', na=False)]
            down = related[related['relation'].str.contains('客戶|雲端|平台', na=False)]
            comp = related[related['relation'].str.contains('競爭|替代|威脅', na=False)]
            event = related[related['relation'].str.contains('事件影響|題材', na=False)]
            st.markdown('**上游 / 供應：** ' + ('、'.join(sorted(set(up['source'].tolist() + up['target'].tolist()) - {selected})) if not up.empty else '—'))
            st.markdown('**下游 / 客戶：** ' + ('、'.join(sorted(set(down['source'].tolist() + down['target'].tolist()) - {selected})) if not down.empty else '—'))
            st.markdown('**競爭對手：** ' + ('、'.join(sorted(set(comp['source'].tolist() + comp['target'].tolist()) - {selected})) if not comp.empty else '—'))
            st.markdown('**事件 / 題材：** ' + ('、'.join(sorted(set(event['source'].tolist() + event['target'].tolist()) - {selected})) if not event.empty else '—'))
            with st.expander('相關連線明細'):
                st.dataframe(related[[c for c in ['source','target','edge_group','relation','confidence','supply_chain_status','trend_signal','verified_status','verified_trend','verified_title','verified_domain','master_status','master_confidence','strength','evidence'] if c in related.columns]].head(50), use_container_width=True)
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

st.set_page_config(page_title="Global News Radar V37", layout="wide", initial_sidebar_state="collapsed")

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

st.title("🌍 Global News Radar V37：自動驗證供應鏈視圖修正版")

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
            value="最近 8 小時討論度最高的 AI 或半導體相關新聞",
            height=90,
        )
        st.caption("例：最近 8 小時討論度最高的 AI 或半導體相關新聞 / AI 伺服器供應鏈變化 / NVIDIA、Intel、AMD 在 AI CPU/GPU 的新聞")
        query_logic = "聯集 OR"
    else:
        query = st.text_input("關鍵字 / 公司 / 人名", value="NVIDIA")
        query_logic = st.radio("多關鍵字邏輯", ["交集 AND", "聯集 OR"], index=0, help="例：NVIDIA intel。交集=同時找兩者相關；聯集=分別找 NVIDIA 與 Intel 後合併。")
    time_range = st.selectbox("財經新聞時間範圍", ["最近 1 小時", "最近 6 小時", "最近 8 小時", "最近 12 小時", "最近 24 小時", "最近 3 天", "最近 7 天", "不限時間"], index=2)
    freshness_mode = st.radio(
        "新鮮度模式",
        ["熱度掃描", "新事件優先", "嚴格新事件"],
        index=1,
        help="熱度掃描：保留舊事件新包裝；新事件優先：真新事件排前、垃圾剔除；嚴格新事件：只保留真新事件。"
    )
    max_items = st.slider("最多新聞篇數", 5, 80, 40, step=5)
    translate_titles = st.checkbox("原文標題 + 智慧翻譯成繁中", value=True)
    translation_mode = st.radio(
        "翻譯模式",
        ["Groq AI 財經翻譯優先", "只用免費機翻", "不翻譯只保留原文"],
        index=0,
        help="Groq 模式需要在 Streamlit Secrets 設定 GROQ_API_KEY。"
    )
    if groq_is_enabled():
        st.success(f"Groq API：已啟用｜Light：{get_groq_model_light()}｜Heavy：{get_groq_model_heavy()}")
    else:
        st.warning("Groq API：未設定。目前會退回免費機翻或原文。")

    groq_usage_mode = st.radio(
        "Groq 使用模式",
        ["省 token", "平衡", "高品質"],
        index=1,
        help="省 token：多用 8B、少翻譯；平衡：Top 少數用 70B；高品質：更多 Top 新聞用 70B。"
    )
    if groq_usage_mode == "省 token":
        default_translate_n, default_heavy_n = 5, 0
    elif groq_usage_mode == "高品質":
        default_translate_n, default_heavy_n = 20, 8
    else:
        default_translate_n, default_heavy_n = 10, 3

    groq_translate_top_n = st.slider("Groq / 機翻標題翻譯前幾則", 0, 30, default_translate_n, step=5)
    heavy_translate_top_n = st.slider("其中用 Heavy 精翻前幾則", 0, 10, min(default_heavy_n, groq_translate_top_n), step=1)

    with st.expander("測試 Groq 翻譯"):
        test_title = st.text_input(
            "測試標題",
            value="Nvidia crashes Intel’s party: $5T giant surges as AI market pivots to CPUs",
            key="groq_test_title",
        )
        if st.button("執行翻譯測試", key="run_groq_test"):
            test = translate_title_with_engine(test_title, domain="investing.com", category="AI / 半導體", translation_mode=translation_mode, model_tier="heavy")
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

    st.divider()
    st.subheader("記錄與遺忘")
    enable_snapshot = st.checkbox("每次搜尋記錄精簡 snapshot", value=True)
    snapshot_max_files = st.slider("最多保留幾份 snapshot", 5, 80, 30, step=5)
    snapshot_max_days = st.slider("最多保留幾天", 1, 60, 14)

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
if "last_snapshot_payload" not in st.session_state:
    st.session_state["last_snapshot_payload"] = None
if "last_snapshot_path" not in st.session_state:
    st.session_state["last_snapshot_path"] = ""

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
            groq_translate_top_n=groq_translate_top_n,
            heavy_translate_top_n=heavy_translate_top_n,
            freshness_mode=freshness_mode,
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

# V37: 自動背景供應鏈驗證。不需要手動按「開始即時驗證」。
if search_button and not feed.empty:
    try:
        auto_candidates = build_realtime_verification_candidates(feed, limit=8)
        if not auto_candidates.empty:
            st.session_state["last_realtime_verification"] = run_realtime_supply_chain_verification(
                auto_candidates,
                max_results_per_relation=1,
                time_range=time_range if time_range in ["最近 24 小時", "最近 3 天", "最近 7 天", "不限時間"] else "最近 7 天",
            )
    except Exception as exc:
        st.session_state["last_realtime_verification_error"] = str(exc)

if search_button and enable_snapshot and not feed.empty:
    try:
        snap_companies, snap_edges, _ = build_company_supply_chain_snapshot(feed, max_news=80)
        payload = minimal_snapshot_payload(feed, snap_companies, snap_edges, query, time_range, freshness_mode)
        st.session_state["last_snapshot_payload"] = payload
        st.session_state["last_snapshot_path"] = save_snapshot(payload, max_files=snapshot_max_files, max_days=snapshot_max_days)
        new_candidates = build_master_candidate_rows(snap_companies, snap_edges, load_supply_chain_master())
        merge_candidates(new_candidates)
    except Exception as exc:
        st.info(f"snapshot / 候選記錄失敗：{exc}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("統合新聞流", f"{len(feed):,}")
col2.metric("公司/財經新聞", f"{len(articles):,}")
col3.metric("全球事件", f"{len(events_filtered):,}")
col4.metric("事件原始數", f"{len(events_all):,}")

if st.session_state.get("last_success_query"):
    st.caption(f"上次成功查詢：{st.session_state['last_success_query']}｜目前選擇時間範圍：{time_range}｜新鮮度模式：{freshness_mode}")

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


def build_realtime_verification_candidates(feed: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    """Build relationship candidates for real-time supply-chain verification from current news."""
    companies, edges, _ = build_company_supply_chain_snapshot(feed, max_news=80)
    if edges is None or edges.empty:
        return pd.DataFrame(columns=["source_company", "target_company", "candidate_relation", "evidence", "confidence"])
    work = edges.copy()
    if "relation" not in work.columns:
        return pd.DataFrame()
    work = work[~work["relation"].astype(str).str.startswith("主檔", na=False)].copy()
    if work.empty:
        return pd.DataFrame(columns=["source_company", "target_company", "candidate_relation", "evidence", "confidence"])
    if "confidence" not in work.columns:
        work["confidence"] = ""
    if "strength" not in work.columns:
        work["strength"] = 1
    work["_score"] = pd.to_numeric(work["strength"], errors="coerce").fillna(1)
    work["_score"] += work["confidence"].astype(str).apply(lambda x: 3 if x.startswith("高") else (2 if x.startswith("中") else 1))
    work = work.sort_values("_score", ascending=False).drop_duplicates(subset=["source", "target", "relation"])
    return pd.DataFrame([{
        "source_company": r.get("source", ""),
        "target_company": r.get("target", ""),
        "candidate_relation": r.get("relation", ""),
        "evidence": r.get("evidence", ""),
        "confidence": r.get("confidence", ""),
    } for _, r in work.head(limit).iterrows()])


def classify_verification_status(title: str, domain: str) -> tuple[str, str]:
    text = f"{title} {domain}".lower()
    high_terms = ["supplier", "supply", "customer", "contract", "deal", "partnership", "selected", "adopts", "order", "wins", "qualified", "供應", "客戶", "合約", "合作", "採用", "訂單", "認證"]
    down_terms = ["cancel", "terminate", "delay", "ban", "restriction", "cut", "drop", "lose", "lost", "退出", "取消", "延後", "限制", "禁令", "轉單", "減少"]
    up_terms = ["new", "expand", "ramp", "increase", "gain", "win", "order", "新增", "擴大", "增加", "提升", "放量", "打入"]
    confidence = "高｜公開資料有明確供應鏈線索" if any(t in text for t in high_terms) else "中｜公開資料有共現或題材關聯"
    if any(t in text for t in down_terms):
        trend = "下降 / 中斷風險"
    elif any(t in text for t in up_terms):
        trend = "新增 / 擴大候選"
    else:
        trend = "待確認"
    return confidence, trend


def run_realtime_supply_chain_verification(candidates: pd.DataFrame, max_results_per_relation: int = 3, time_range: str = "最近 7 天") -> pd.DataFrame:
    if candidates is None or candidates.empty:
        return pd.DataFrame()
    rows = []
    preferred = ["reuters.com", "finance.yahoo.com", "cnbc.com", "marketwatch.com", "investing.com"]
    for _, c in candidates.iterrows():
        src = str(c.get("source_company", "")).strip()
        dst = str(c.get("target_company", "")).strip()
        rel = str(c.get("candidate_relation", "")).strip()
        if not src or not dst:
            continue
        verification_query = f'"{src}" "{dst}" supplier OR customer OR partnership OR supply chain OR order OR contract'
        try:
            result = fetch_google_news_rss(verification_query, max_items=max_results_per_relation, preferred_domains=preferred[:2], time_range=time_range)
        except Exception as exc:
            rows.append({
                "source_company": src, "target_company": dst, "candidate_relation": rel,
                "verification_query": verification_query, "verification_status": "查詢失敗",
                "trend_signal": "待確認", "evidence_title": str(exc), "domain": "", "url": "",
            })
            continue
        if result is None or result.empty:
            rows.append({
                "source_company": src, "target_company": dst, "candidate_relation": rel,
                "verification_query": verification_query, "verification_status": "低｜未找到公開證據",
                "trend_signal": "待確認", "evidence_title": "", "domain": "", "url": "",
            })
            continue
        for _, r in result.head(max_results_per_relation).iterrows():
            conf, trend = classify_verification_status(str(r.get("title", "")), str(r.get("domain", "")))
            rows.append({
                "source_company": src, "target_company": dst, "candidate_relation": rel,
                "verification_query": verification_query, "verification_status": conf,
                "trend_signal": trend, "evidence_title": r.get("title", ""),
                "domain": r.get("domain", ""), "url": r.get("url", ""),
            })
    return pd.DataFrame(rows)


def render_realtime_verification_tab(feed: pd.DataFrame, time_range: str):
    st.subheader("即時供應鏈驗證")
    st.caption("V37：搜尋完成後會自動背景驗證 Top 關係；這頁只是讓你查看結果或手動重跑。")
    if feed is None or feed.empty:
        st.info("目前沒有新聞資料。請先搜尋一次。")
        return
    v_cols = st.columns(3)
    max_rel = v_cols[0].slider("最多驗證幾條關係", 3, 20, 8)
    max_per = v_cols[1].slider("每條關係最多證據", 1, 5, 2)
    verify_range = v_cols[2].selectbox("驗證搜尋時間範圍", ["最近 24 小時", "最近 3 天", "最近 7 天", "不限時間"], index=2)
    candidates = build_realtime_verification_candidates(feed, limit=max_rel)
    st.markdown("### 本次新聞抽出的候選關係")
    if candidates.empty:
        st.warning("本次新聞沒有抽出可驗證的公司關係。")
        return
    st.dataframe(candidates, use_container_width=True)
    if st.button("重新執行即時驗證", type="secondary"):
        with st.spinner("正在即時查詢公開供應鏈證據..."):
            st.session_state["last_realtime_verification"] = run_realtime_supply_chain_verification(candidates, max_results_per_relation=max_per, time_range=verify_range)
    verified = st.session_state.get("last_realtime_verification", pd.DataFrame())
    if verified is not None and not verified.empty:
        st.markdown("### 即時驗證結果")
        st.dataframe(verified, use_container_width=True)
        st.markdown("### 快速閱讀")
        for _, row in verified.head(20).iterrows():
            title = row.get("evidence_title", "")
            url = row.get("url", "")
            st.markdown(
                f"""
                <div style="border:1px solid rgba(128,128,128,0.25);border-radius:12px;padding:10px 12px;margin:8px 0;background:rgba(128,128,128,0.06);">
                <b>{html.escape(str(row.get('source_company','')))} → {html.escape(str(row.get('target_company','')))}</b><br>
                關係候選：{html.escape(str(row.get('candidate_relation','')))}<br>
                確認度：{html.escape(str(row.get('verification_status','')))}｜狀態：{html.escape(str(row.get('trend_signal','')))}<br>
                證據：<a href="{html.escape(str(url))}" target="_blank">{html.escape(str(title or '無標題'))}</a><br>
                <small>{html.escape(str(row.get('domain','')))}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("搜尋完成後會自動背景驗證；若目前沒有結果，可按「重新執行即時驗證」。")


tab_feed, tab_map, tab_graph, tab_verify, tab_delta, tab_candidates, tab_raw = st.tabs(["統合新聞流", "統合地圖", "產業關係圖", "即時驗證", "Delta Radar", "主檔候選", "原始資料"])

with tab_feed:
    st.subheader("統合新聞流")
    st.caption("V37：搜尋後會自動背景驗證供應鏈關係，並直接反映到方案 A/B/C。")

    if not feed.empty:
        st.markdown("### 複製新聞包")
        st.caption("複製不會消耗 Groq token。按一下複製完整 Markdown 新聞包，回 ChatGPT 直接貼上即可。")
        md_bundle = build_news_bundle_markdown(
            feed,
            ai_summary="",
            query=st.session_state.get("last_success_query", ""),
            time_range=time_range,
            plan=st.session_state.get("last_query_plan", {}),
        )
        csv_bundle = build_news_bundle_csv(feed)

        render_clipboard_button(md_bundle, "一鍵複製 Markdown 新聞包")

        with st.expander("手動複製備用區"):
            st.caption("如果 iPhone / Safari 阻擋一鍵複製，請在這裡全選文字後複製。")
            st.text_area(
                "Markdown 新聞包內容",
                value=md_bundle,
                height=260,
                label_visibility="collapsed",
            )

        with st.expander("下載備用"):
            cdl1, cdl2 = st.columns(2)
            with cdl1:
                st.download_button(
                    "下載 Markdown 新聞包",
                    data=md_bundle.encode("utf-8"),
                    file_name=make_download_filename("global_news_bundle", "md"),
                    mime="text/markdown",
                    use_container_width=True,
                )
            with cdl2:
                st.download_button(
                    "下載 CSV 新聞表",
                    data=csv_bundle,
                    file_name=make_download_filename("global_news_bundle", "csv"),
                    mime="text/csv",
                    use_container_width=True,
                )
        st.divider()

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
                heat_score = html.escape(str(row.get("heat_score", "")))
                freshness_label = html.escape(str(row.get("freshness_label", "")))
                freshness_reason = html.escape(str(row.get("freshness_reason", "")))

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
                        <div class="article-meta">{time_utc}<br>{domain}｜{location}｜{quality}<br>新鮮度：{freshness_label}<br>新鮮度理由：{freshness_reason}<br>熱度分數：{heat_score}<br>翻譯來源：{translation_engine}<br>{summary}</div>
                        <div class="article-meta"><b>判斷：</b>{hint}</div>
                        <div class="article-source"><a href="{url_safe}" target="_blank">打開來源</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            cols = ["time_utc", "data_type", "freshness_label", "freshness_reason", "heat_score", "importance", "category", "title_zh", "title", "domain", "source_quality", "location", "url"]
            st.dataframe(feed[[c for c in cols if c in feed.columns]], use_container_width=True)

with tab_map:
    st.subheader("統合地圖 / 供應鏈視圖")
    st.caption("V37：方案 A/B/C 改成新聞驅動 + 自動驗證；主檔只當背景，不再把固定資料塞進主畫面。")

    map_sheet_a, map_sheet_b, map_sheet_c, map_sheet_old = st.tabs([
        "方案 A｜供應鏈地理圖",
        "方案 B｜供應鏈分層圖",
        "方案 C｜地圖 + 狀態面板",
        "舊版｜來源國家地圖",
    ])

    companies_df, sc_edges_df, sc_summary = build_company_supply_chain_snapshot(feed, max_news=80)
    verified_df = st.session_state.get("last_realtime_verification", pd.DataFrame())
    view_companies_df, view_edges_df = get_news_driven_supply_chain_view(companies_df, sc_edges_df, verified_df)

    with map_sheet_a:
        st.caption("方案 A：新聞驅動供應鏈地理圖。公司名稱改為黑字白底高辨識標籤；線條會套用自動驗證狀態。")
        if view_companies_df.empty:
            st.info("本次新聞沒有足夠公司資料可建立供應鏈地理圖。建議搜尋 CPU、GPU、AI server、NVIDIA Intel AMD 這類主題。")
        else:
            top1, top2, top3 = st.columns(3)
            top1.metric("本次新聞公司節點", f"{len(view_companies_df):,}")
            top2.metric("本次新聞 / 驗證關係線", f"{len(view_edges_df):,}")
            top3.metric("主要公司", "、".join(sc_summary.get('top_companies', [])[:3]) or "—")
            m_a = draw_supply_chain_geo_map(view_companies_df, view_edges_df)
            st_folium(m_a, width=None, height=560, returned_objects=[], key="world_map_supply_chain_v37")
            with st.expander("節點資料表"):
                st.dataframe(view_companies_df[['node', 'layer_bucket', 'layer', 'status', 'news_hits', 'country', 'city', 'top_categories']].head(80), use_container_width=True)

    with map_sheet_b:
        render_supply_chain_layered_sheet(view_companies_df, view_edges_df)

    with map_sheet_c:
        render_map_with_panel_sheet(view_companies_df, view_edges_df)

    with map_sheet_old:
        st.caption("舊版保留給你對照：紫色數字＝公司/財經新聞來源國家篇數；藍色數字＝全球事件。")
        m = build_world_map(feed, show_news=show_news_on_map, show_events=show_events_on_map)
        st_folium(m, width=None, height=520, returned_objects=[], key="world_map")

with tab_graph:
    render_industry_relationship_page(feed)

with tab_verify:
    render_realtime_verification_tab(feed, time_range)

with tab_delta:
    render_delta_radar(st.session_state.get("last_snapshot_payload"))

with tab_candidates:
    render_master_candidate_queue()

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
