import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import feedparser
import requests
import streamlit as st
from dateutil import parser as dateparser

TZ = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

st.set_page_config(page_title="MarketPulse AI", page_icon="📈", layout="wide")

FEEDS = {
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNBC World": "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "CNBC Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch Top Stories": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Investing.com News": "https://www.investing.com/rss/news_25.rss",
    "Google News - Crude Oil": "https://news.google.com/rss/search?q=crude+oil+OR+OPEC+OR+oil+supply&hl=en-IN&gl=IN&ceid=IN:en",
    "Google News - Gold": "https://news.google.com/rss/search?q=gold+price+OR+gold+market+OR+central+bank+gold&hl=en-IN&gl=IN&ceid=IN:en",
    "Google News - Stocks": "https://news.google.com/rss/search?q=stock+market+OR+company+earnings+OR+shares&hl=en-IN&gl=IN&ceid=IN:en",
    "Google News - Global Economy": "https://news.google.com/rss/search?q=Federal+Reserve+OR+inflation+OR+China+economy+OR+sanctions+OR+trade+war&hl=en-IN&gl=IN&ceid=IN:en",
}

ASSET_TERMS = {
    "Crude oil": ["crude", "oil price", "opec", "brent", "wti", "oil supply", "oil output", "tanker", "petroleum", "refinery"],
    "Gold & silver": ["gold", "bullion", "silver", "precious metal", "safe haven"],
    "Stocks & indices": ["stock", "stocks", "shares", "equity", "equities", "earnings", "nifty", "sensex", "nasdaq", "dow jones", "s&p 500", "ipo"],
    "FX & rates": ["dollar", "usd", "rupee", "currency", "forex", "yield", "bond", "interest rate", "federal reserve", "fed", "rbi", "ecb"],
    "Global economy & geopolitics": ["inflation", "gdp", "tariff", "sanction", "war", "conflict", "china", "trade", "central bank", "election", "economic", "recession", "shipping", "strait"],
}

BULLISH_TERMS = ["supply disruption", "supply cut", "cuts output", "production cut", "sanctions", "war", "conflict", "escalation", "safe haven", "rate cut", "lower interest rates", "dovish", "stimulus", "shortage", "surge in demand"]
BEARISH_TERMS = ["supply increase", "output increase", "production boost", "ceasefire", "de-escalation", "rate hike", "higher interest rates", "hawkish", "weak demand", "demand falls", "oversupply", "inventory build", "recession fears"]

def today_window():
    now = datetime.now(TZ)
    start = datetime.combine(now.date(), time.min, tzinfo=TZ)
    end = start + timedelta(days=1)
    return now, start, end

def parse_published(entry):
    # Strict: do not substitute updated, crawled, or retrieval time for publication time.
    value = entry.get("published") or entry.get("pubDate") or entry.get("dc:date")
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if dt is None:
            return None
        if dt.tzinfo is None:
            # An ambiguous timezone is not safe enough for strict date filtering.
            return None
        return dt.astimezone(TZ)
    except Exception:
        return None

def clean_text(value):
    return " ".join((value or "").replace("<p>", " ").replace("</p>", " ").split())

def categorize(text):
    low = text.lower()
    hits = []
    for category, terms in ASSET_TERMS.items():
        if any(term in low for term in terms):
            hits.append(category)
    return hits or ["General market news"]

def heuristic_impact(text, categories):
    low = text.lower()
    bull = sum(term in low for term in BULLISH_TERMS)
    bear = sum(term in low for term in BEARISH_TERMS)
    if bull == bear:
        direction = "Mixed / uncertain"
        rationale = "The headline alone does not establish a clear direction. Confirm the details and the market's reaction."
    elif bull > bear:
        direction = "Potentially bullish for selected safe-haven or supply-sensitive assets"
        rationale = "The headline contains terms that can indicate risk aversion, tighter supply, or easier monetary policy. The effect depends on the asset and the full report."
    else:
        direction = "Potentially bearish for selected safe-haven or supply-sensitive assets"
        rationale = "The headline contains terms that can indicate improving supply, lower risk, tighter monetary policy, or weaker demand. The effect depends on the asset and the full report."
    if "Crude oil" in categories and any(x in low for x in ["supply", "opec", "brent", "wti", "oil"]):
        rationale += " For crude oil, verify whether the news changes actual supply/demand expectations."
    if "Gold & silver" in categories:
        rationale += " For gold and silver, check real yields, the US dollar, and safe-haven demand."
    if "Stocks & indices" in categories:
        rationale += " For equities, assess the affected company/sector and whether the news is already priced in."
    return direction, rationale

def fetch_feed(name, url, start, end):
    items, errors = [], []
    try:
        response = requests.get(url, timeout=12, headers={"User-Agent": "MarketPulseAI/0.1 (personal research app)"})
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            errors.append(f"{name}: feed could not be parsed")
        for entry in parsed.entries[:60]:
            published = parse_published(entry)
            if published is None:
                continue
            if not (start <= published < end):
                continue
            link = entry.get("link", "")
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            if not title or not link.startswith("http"):
                continue
            text = f"{title}. {summary}"
            cats = categorize(text)
            impact, rationale = heuristic_impact(text, cats)
            items.append({
                "title": title, "summary": summary, "link": link,
                "published": published, "source": name, "categories": cats,
                "impact": impact, "rationale": rationale,
            })
    except Exception as e:
        errors.append(f"{name}: {type(e).__name__} — {str(e)[:140]}")
    return items, errors

def gemini_summary(article):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    prompt = f"""You are a cautious financial-news analyst. Analyze only the supplied current article; do not add outside facts.
Headline: {article['title']}
Source summary: {article['summary']}
Categories: {', '.join(article['categories'])}

Return concise plain text with:
1. What happened (reported facts only)
2. Assets/sectors potentially affected
3. Potential impact: bullish, bearish, mixed, or uncertain, specifying the asset
4. Why, including alternative interpretation / uncertainty
5. Confidence: low, medium, or high, with one reason
Do not make a price target or claim certainty. If the supplied content is insufficient, say so."""
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key
        r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return "AI analysis unavailable. Showing rule-based preliminary assessment instead."

now, start, end = today_window()
st.title("📈 MarketPulse AI")
st.caption(f"Today's global market intelligence · Asia/Kolkata · {now.strftime('%d %b %Y')} · Window: {start.strftime('%H:%M')}–tomorrow {end.strftime('%H:%M')} IST")
st.info("Strict date mode is ON. Articles with missing/ambiguous publication timestamps and articles outside today's IST window are excluded. No previous-day fallback.")

with st.sidebar:
    st.header("News controls")
    selected_categories = st.multiselect("Asset / topic filters", list(ASSET_TERMS.keys()), default=list(ASSET_TERMS.keys()))
    use_ai = st.checkbox("Use Gemini AI analysis (optional)", value=False, help="Requires a Gemini API key in the GEMINI_API_KEY environment variable. API usage may be subject to provider limits or charges.")
    st.caption("News sources are best-effort RSS feeds. A feed outage or a missing publication timestamp can reduce coverage.")
    refresh = st.button("🔄 Refresh today's news", use_container_width=True)

@st.cache_data(ttl=300, show_spinner=False)
def load_news(day_key):
    _, day_start, day_end = today_window()
    all_items, all_errors = [], []
    for source_name, source_url in FEEDS.items():
        items, errors = fetch_feed(source_name, source_url, day_start, day_end)
        all_items.extend(items)
        all_errors.extend(errors)
    # Deduplicate by normalized title, preserving the first source link.
    unique = {}
    for item in sorted(all_items, key=lambda x: x["published"], reverse=True):
        key = "".join(ch.lower() for ch in item["title"] if ch.isalnum())
        if key and key not in unique:
            unique[key] = item
    return list(unique.values()), all_errors

if refresh:
    load_news.clear()

with st.spinner("Scanning RSS sources and validating publication timestamps…"):
    articles, errors = load_news(now.date().isoformat())

if use_ai and os.getenv("GEMINI_API_KEY", "").strip():
    with st.spinner("Preparing optional AI analysis…"):
        for article in articles:
            article["ai_analysis"] = gemini_summary(article)

if selected_categories:
    filtered = [a for a in articles if any(c in a["categories"] for c in selected_categories)]
else:
    filtered = articles

c1, c2, c3 = st.columns(3)
c1.metric("Today's qualifying articles", len(articles))
c2.metric("After topic filters", len(filtered))
c3.metric("Feeds checked", len(FEEDS))

if not articles:
    st.warning("No qualifying articles with verified publication timestamps were found for today's IST date window. The app will not show older articles as a fallback.")
    st.write("Try Refresh, or check the feed diagnostics below. Some RSS providers omit publication timestamps or may be temporarily unavailable.")
else:
    for article in filtered:
        with st.container(border=True):
            st.markdown(f"### [{article['title']}]({article['link']})")
            st.caption(f"{article['source']} · Published {article['published'].strftime('%d %b %Y, %I:%M %p IST')} · " + " / ".join(article["categories"]))
            if article["summary"]:
                st.write(article["summary"][:900] + ("…" if len(article["summary"]) > 900 else ""))
            st.markdown(f"**Preliminary impact:** {article['impact']}")
            st.write(article.get("ai_analysis") or article["rationale"])
            st.caption("Impact assessment is informational, based on limited headline/feed text; it is not a trading signal or a guarantee.")

with st.expander("Source diagnostics"):
    st.write("Feed sources checked:")
    for name, url in FEEDS.items():
        st.markdown(f"- [{name}]({url})")
    if errors:
        st.warning("Some feeds failed during this scan:")
        for err in errors:
            st.write(f"- {err}")
    else:
        st.success("No feed errors were reported in this scan.")

st.divider()
st.caption("MarketPulse AI prototype · RSS availability, publication timestamps and article-link formats depend on source providers. Verify important developments at the original publisher before acting.")
