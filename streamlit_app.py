"""基金限购查询 — 手机版"""

import streamlit as st
import requests
import re
import time
import json
import os
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="基金限购查询", page_icon="📋", layout="centered")

# ── 配置 ──
PASSWORD = "lof2024"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://fund.eastmoney.com/",
}
CACHE_FILE = "/tmp/fund_query_cache.json"  # Streamlit Cloud 临时目录

DEFAULT_FUNDS = [
    "160140", "160216", "160416", "160644", "160716", "160717", "160719",
    "160723", "160924", "161116", "161124", "161125", "161126", "161127",
    "161128", "161129", "161130", "161226", "161812", "161815", "161831",
    "162411", "162415", "162719", "163208", "164701", "164705", "164824",
    "164906", "165513", "501018", "501025", "501043", "501225", "501300",
    "501302", "501312",
]

# ── CSS ──
st.markdown("""
<style>
.stApp { max-width: 520px; margin: 0 auto; }
[data-testid="stMetricValue"] { font-size: 1.5rem !important; }
.stButton button { font-size: 1rem !important; border-radius: 12px !important; }
@media (max-width: 480px) {
    h1 { font-size: 1.2rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ── 密码 ──
if "auth" not in st.session_state:
    st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 基金限购查询")
    pwd = st.text_input("密码", type="password")
    if st.button("进入"):
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# ── 查询逻辑（和桌面版 fund_server.py 完全一致）──
def fetch(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.encoding = r.apparent_encoding or "utf-8"
        return r
    except:
        return None

def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_status(raw):
    raw = raw.strip()
    if "暂停" in raw: return "暂停申购"
    if "限制" in raw or "限大额" in raw or "限额" in raw: return "限制大额申购"
    if "开放" in raw: return "开放申购"
    return raw if raw else "未知"

def _extract_cell_text(html, start_pos):
    depth = 1
    pos = start_pos
    while pos < len(html) and depth > 0:
        span_open = html.find("<span", pos)
        span_close = html.find("</span>", pos)
        if span_close >= 0 and (span_open < 0 or span_close < span_open):
            depth -= 1
            if depth == 0:
                raw = html[start_pos:span_close]
                return (strip_html(raw), span_close + 7)
            pos = span_close + 7
        elif span_open >= 0:
            depth += 1
            tag_close = html.find(">", span_open)
            pos = (tag_close + 1) if tag_close >= 0 else (span_open + 5)
        else:
            break
    return ("", start_pos)

def get_fund_name(code):
    resp = fetch(f"http://fund.eastmoney.com/pingzhongdata/{code}.js")
    if resp:
        m = re.search(r'fS_name\s*=\s*"([^"]+)"', resp.text)
        if m: return m.group(1)
    return f"基金{code}"

def get_subscription_status(code):
    resp = fetch(f"https://fund.eastmoney.com/{code}.html")
    if not resp:
        return "查询失败", ""
    text = resp.text

    item_match = re.search(
        r'<span[^>]*class\s*=\s*"itemTit"[^>]*>[^<]*状态[：:][^<]*</span>',
        text, re.IGNORECASE,
    )
    if not item_match:
        if "暂停申购" in text: return "暂停申购", ""
        if "限大额" in text: return "限制大额申购", ""
        if "开放申购" in text: return "开放申购", ""
        return "未知", ""

    after_item = text[item_match.end():]
    cell1_m = re.search(
        r'<span[^>]*class\s*=\s*"staticCell"[^>]*>', after_item, re.IGNORECASE,
    )
    if not cell1_m:
        return "未知", ""
    sg_raw, cell1_end = _extract_cell_text(after_item, cell1_m.end())

    after_cell1 = after_item[cell1_end:]
    cell2_m = re.search(
        r'<span[^>]*class\s*=\s*"staticCell"[^>]*>\s*([^<]*)',
        after_cell1, re.IGNORECASE,
    )
    sh_raw = cell2_m.group(1).strip() if cell2_m else ""
    return normalize_status(sg_raw), sh_raw

def extract_limit_amount(code):
    resp = fetch(f"https://fund.eastmoney.com/{code}.html")
    if not resp: return None
    text = resp.text

    item_match = re.search(
        r'<span[^>]*class\s*=\s*"itemTit"[^>]*>[^<]*状态[：:][^<]*</span>',
        text, re.IGNORECASE,
    )
    if item_match:
        after_item = text[item_match.end():]
        cell_m = re.search(
            r'<span[^>]*class\s*=\s*"staticCell"[^>]*>', after_item, re.IGNORECASE,
        )
        if cell_m:
            sg_raw, _ = _extract_cell_text(after_item, cell_m.end())
            m = re.search(r"(\d[\d,.]*)\s*[元万]", sg_raw)
            if m:
                amount = m.group(1).replace(",", "")
                try: amount = str(int(round(float(amount))))
                except: pass
                unit = "万" if "万" in sg_raw[m.end()-10:m.end()+10] else "元"
                return f"{amount}{unit}"

    patterns = [
        r"单日(?:累计)?(?:申购|购买)上限[：:]\s*(\d[\d,.]*)\s*[元万]",
        r"(?:申购|购买)(?:金额)?上限[：:]\s*(\d[\d,.]*)\s*[元万]",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            amount = m.group(1).replace(",", "")
            try: amount = str(int(round(float(amount))))
            except: pass
            unit = "万" if "万" in m.group(0) else "元"
            return f"{amount}{unit}"
    return None

def query_single(code):
    try:
        name = get_fund_name(code)
        sg_status, sh_status = get_subscription_status(code)
        is_suspended = sg_status == "暂停申购"
        is_limited = sg_status == "限制大额申购"

        if is_suspended:
            limit_amount = "—"
        elif is_limited:
            limit_amount = extract_limit_amount(code) or "需查看公告"
        else:
            limit_amount = "不限购"

        if sh_status and "暂停" in sh_status:
            sg_status += " / 暂停赎回"

        return {"code": code, "name": name, "status": sg_status, "amount": limit_amount}
    except:
        return {"code": code, "name": f"基金{code}", "status": "查询失败", "amount": "—"}

@st.cache_data(ttl=600)
def query_all(_codes_tuple):
    codes = list(_codes_tuple)
    results = []
    for code in codes:
        results.append(query_single(code))
        time.sleep(0.2)
    return results

# ── 加载缓存 ──
def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                if time.time() - data.get("ts", 0) < 3600:
                    return data.get("results", [])
    except:
        pass
    return None

def save_cache(results):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "results": results}, f, ensure_ascii=False)
    except:
        pass

# ── 主界面 ──
st.title("📋 QDII LOF 限购查询")

# 先显示缓存
cached = load_cache()
if cached:
    results = cached
    cache_time = "缓存"
else:
    results = None
    cache_time = ""

# 后台查询
if st.button("🔄 刷新数据", use_container_width=True):
    st.cache_data.clear()
    with st.spinner(f"正在查询 {len(DEFAULT_FUNDS)} 只基金..."):
        results = query_all(tuple(DEFAULT_FUNDS))
        save_cache(results)
        cache_time = ""
    st.rerun()

# 如果没有数据，显示加载中
if results is None:
    with st.spinner("首次加载，正在查询..."):
        results = query_all(tuple(DEFAULT_FUNDS))
        save_cache(results)
        cache_time = ""
    st.rerun()

# ── 筛选 ──
status_filter = st.radio("筛选", ["全部", "暂停申购", "限制大额申购", "开放申购"], horizontal=True, key="filter")

filtered = results
if status_filter == "暂停申购":
    filtered = [r for r in results if r["status"] == "暂停申购"]
elif status_filter == "限制大额申购":
    filtered = [r for r in results if r["status"] == "限制大额申购"]
elif status_filter == "开放申购":
    filtered = [r for r in results if r["status"] == "开放申购"]

# ── 统计 ──
paused = len([r for r in results if r["status"] == "暂停申购"])
limited = len([r for r in results if r["status"] == "限制大额申购"])
opened = len([r for r in results if r["status"] == "开放申购"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("暂停", str(paused))
c2.metric("限大额", str(limited))
c3.metric("开放", str(opened))
c4.metric("合计", str(len(results)))

# ── 表格 ──
st.markdown("---")
for r in filtered:
    badge = {"暂停申购": "🔴", "限制大额申购": "🟡", "开放申购": "🟢", "查询失败": "⚪", "未知": "⚪"}.get(r["status"], "⚪")
    amount_color = "#ef4444" if r["status"] == "暂停申购" else "#f59e0b" if r["status"] == "限制大额申购" else "#22c55e"
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:8px 0;border-bottom:1px solid #eee;">'
        f'<div><b>{r["code"]}</b> <span style="color:#666;font-size:0.85rem;">{r["name"]}</span></div>'
        f'<div style="text-align:right;">'
        f'<span style="font-size:0.8rem;">{badge} {r["status"]}</span><br>'
        f'<span style="font-weight:600;color:{amount_color};font-size:0.9rem;">{r["amount"]}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

# ── 底部 ──
st.markdown("---")
now_bj = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
st.caption(f"数据来源: 天天基金 ｜ 更新: {now_bj.strftime('%H:%M:%S')} (北京)")
if cache_time:
    st.caption(f"({cache_time}数据，点击刷新获取最新)")

st.components.v1.html("""
<script>
setTimeout(function() { window.location.reload(); }, 600000);
</script>
""", height=0)
