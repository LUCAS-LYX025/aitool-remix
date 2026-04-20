from __future__ import annotations

import base64
import json
import re
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
ICON_DIR = BASE_DIR / "icons"
ICON_NAME_MAP_PATH = ICON_DIR / "name_overrides.json"
TEST_TOOLSET_TAB = "测试工程师常用工具集"
TEST_TOOLSET_URL = "https://lucas-testtool-online.streamlit.app/"


@st.cache_data(show_spinner=False)
def load_data() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_local_icon_data_uri() -> dict[str, str]:
    def to_data_uri(path: Path) -> str:
        raw = path.read_bytes()
        ext = path.suffix.lower()
        if ext == ".ico":
            mime = "image/x-icon"
        elif ext == ".svg":
            mime = "image/svg+xml"
        elif ext in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif ext == ".gif":
            mime = "image/gif"
        else:
            mime = "image/png"
        return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

    mapping: dict[str, str] = {}
    if not ICON_DIR.exists():
        return mapping
    for path in ICON_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".ico", ".svg", ".jpg", ".jpeg", ".gif"}:
            continue
        mapping[path.stem.lower()] = to_data_uri(path)
    return mapping


@st.cache_data(show_spinner=False)
def load_icon_name_overrides() -> dict[str, str]:
    if not ICON_NAME_MAP_PATH.exists():
        return {}
    try:
        raw = json.loads(ICON_NAME_MAP_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): str(v).lower() for k, v in raw.items() if str(k).strip() and str(v).strip()}
    except Exception:
        return {}
    return {}


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def get_hostname(url: str) -> str:
    try:
        host = urlparse(url).hostname
        return host or ""
    except Exception:
        return ""


def favicon_primary(url: str) -> str:
    # First choice: website's own favicon (actual site icon).
    host = get_hostname(url)
    return f"https://{host}/favicon.ico" if host else ""


def favicon_fallback_1(url: str) -> str:
    # Fallback provider 1
    host = get_hostname(url)
    return f"https://icon.horse/icon/{quote(host, safe='')}" if host else ""


def favicon_fallback_2(url: str) -> str:
    # Fallback provider 2
    host = get_hostname(url)
    return f"https://icons.duckduckgo.com/ip3/{quote(host, safe='')}.ico" if host else ""


def specific_icon_override(item: dict) -> str:
    """Pin reliable icons for known problematic domains/cards."""
    host = get_hostname(str(item.get("url", ""))).lower()
    name_raw = str(item.get("name", "")).strip()
    name = name_raw.lower()
    local = load_local_icon_data_uri()
    name_overrides = load_icon_name_overrides()

    # 0) Name override mapping generated from icons/name_overrides.json.
    mapped_stem = name_overrides.get(name_raw, "")
    if mapped_stem and mapped_stem in local:
        return local[mapped_stem]
    explicit_by_name = {
        "postman": "postman",
        "playwright": "playwright",
        "jmeter": "jmeter",
        "selenium": "selenium",
        "httprunner": "httprunner",
        "locust": "locust",
        "gatling": "gatling",
        "owasp zap": "owasp-zap",
        "burp suite": "burp-suite",
        "nessus": "nessus",
        "testlink": "testlink",
        "appium": "appium",
        "charles": "charles",
        "monkeyrunner": "monkeyrunner",
        "atx（airtest）": "atx-airtest",
        "testgpt": "testgpt",
        "selenium ide ai插件": "selenium-ide-ai",
        "testimonio": "testimonio",
        "51testing测试网": "51testing",
        "owasp官网": "owasp",
        "infoq": "infoq",
    }
    explicit_by_host = {
        "www.postman.com": "postman",
        "playwright.dev": "playwright",
        "jmeter.apache.org": "jmeter",
        "www.selenium.dev": "selenium",
        "httprunner.com": "httprunner",
        "locust.io": "locust",
        "gatling.io": "gatling",
        "www.zaproxy.org": "owasp-zap",
        "portswigger.net": "burp-suite",
        "www.tenable.com": "nessus",
        "testlink.org": "testlink",
        "appium.io": "appium",
        "www.charlesproxy.com": "charles",
        "developer.android.com": "monkeyrunner",
        "airtest.netease.com": "atx-airtest",
        "testgpt.ai": "testgpt",
        "www.testgpt.ai": "testgpt",
        "testimonio.ai": "testimonio",
        "www.testimonio.ai": "testimonio",
        "www.51testing.com": "51testing",
        "owasp.org": "owasp",
        "www.owasp.org": "owasp",
        "www.infoq.cn": "infoq",
        "infoq.cn": "infoq",
    }

    # Exact name mapping first.
    key = explicit_by_name.get(name, "")
    if key and key in local:
        return local[key]

    # Host mapping second.
    key = explicit_by_host.get(host, "")
    if key and key in local:
        return local[key]

    # Generic host->slug mapping for bulk-downloaded icons.
    host_base = host[4:] if host.startswith("www.") else host
    host_slug = re.sub(r"[^a-z0-9]+", "-", host_base).strip("-")
    if host_slug and host_slug in local:
        return local[host_slug]

    # Substring fuzzy mapping.
    for kname, kicon in explicit_by_name.items():
        if kname in name and kicon in local:
            return local[kicon]
    return ""


def text_blob(item: dict) -> str:
    return " ".join(
        [
            item.get("name", ""),
            item.get("description", ""),
            " ".join(item.get("tags", [])),
            item.get("category", ""),
        ]
    ).lower()


def filter_items(items: list[dict], keyword: str, category: str | None) -> list[dict]:
    key = keyword.strip().lower()
    out: list[dict] = []
    for item in items:
        if category and category != "全部" and item.get("category") != category:
            continue
        if key and key not in text_blob(item):
            continue
        out.append(item)
    return out


def section_payload(data: dict, tab: str) -> tuple[list[dict], list[str]]:
    mapping = {
        "AI工具": (data.get("aiTools", []), data.get("aiCategories", [])),
        "Prompt": (data.get("prompts", []), []),
        "Skill": (data.get("skills", []), []),
        "MCP": (data.get("mcps", []), []),
        "OpenClaw": (data.get("openClaw", []), data.get("openClawCategories", [])),
        "软件测试工具": (data.get("testTools", []), data.get("testCategories", [])),
        "软件测试学习网站": (data.get("learningSites", []), []),
    }
    return mapping.get(tab, ([], []))


def ensure_state(data: dict) -> None:
    st.session_state.setdefault("active_tab", (data.get("tabs") or ["AI工具"])[0])
    st.session_state.setdefault("search", "")
    st.session_state.setdefault("category_by_tab", {})

    tabs = data.get("tabs", [])
    if st.session_state["active_tab"] not in tabs and tabs:
        st.session_state["active_tab"] = tabs[0]

    ann_sections = data.get("announcement", {}).get("sections", [])
    default_ann = ann_sections[0]["id"] if ann_sections else ""
    st.session_state.setdefault("ann_section", default_ann)


def render_header(meta: dict) -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&family=IBM+Plex+Sans+SC:wght@400;500;700&display=swap');

        .stApp, .stApp * {
            font-family: "IBM Plex Sans SC", "Manrope", "PingFang SC", "Microsoft YaHei", sans-serif;
        }

        /* Keep Streamlit/Material icon glyph fonts untouched, avoid showing icon names as text. */
        .material-symbols-rounded,
        .material-symbols-outlined,
        .material-icons,
        .material-icons-round,
        .material-icons-outlined,
        [data-testid="stIconMaterial"],
        [data-testid="stIconMaterial"] *,
        [data-testid="stSidebarCollapseButton"] *,
        [data-testid="collapsedControl"] * {
            font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons", "Noto Sans Symbols" !important;
            font-style: normal !important;
            font-weight: 400 !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased;
            font-feature-settings: "liga" 1;
            font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
        }

        .main-title {
            font-size: clamp(1.8rem, 3.2vw, 2.5rem);
            line-height: 1.1;
            font-weight: 800;
            letter-spacing: 0.01em;
            margin-bottom: 0.35rem;
            color: #1a2433;
        }

        .subtitle {
            color: #556070;
            margin-bottom: 1.1rem;
            font-size: 0.98rem;
        }

        .hero-shell {
            border-radius: 20px;
            border: 1px solid #d8e3ef;
            background: linear-gradient(120deg, rgba(255, 255, 255, 0.92), rgba(245, 252, 255, 0.92) 44%, rgba(255, 246, 236, 0.92));
            box-shadow: 0 16px 34px rgba(26, 36, 51, 0.08);
            padding: 22px 20px;
            margin-bottom: 0.8rem;
            position: relative;
            overflow: hidden;
        }

        .hero-shell:before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at 86% 10%, rgba(255, 155, 95, 0.2), transparent 40%),
                radial-gradient(circle at 10% 0%, rgba(82, 184, 205, 0.17), transparent 36%);
            pointer-events: none;
        }

        .hero-shell > * {
            position: relative;
            z-index: 1;
        }

        .hero-kicker {
            display: inline-block;
            border: 1px solid #bfd8ec;
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 0.74rem;
            color: #2f5f87;
            background: #f3faff;
            margin-bottom: 10px;
        }

        .stApp {
            background:
                radial-gradient(circle at 0% 0%, #ffe6cf 0, transparent 32%),
                radial-gradient(circle at 100% 12%, #daf3f8 0, transparent 30%),
                #f4f7fb;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f9fcff, #f4f9ff);
            border-right: 1px solid #d6e3f1;
        }

        [data-testid="stSidebar"] .stRadio > label p {
            font-weight: 600;
            color: #223447;
        }

        .stRadio [role="radiogroup"] label {
            background: #ffffff;
            border: 1px solid #d7e5f2;
            border-radius: 11px;
            padding: 8px 10px;
            margin-bottom: 8px;
            transition: 0.18s ease;
        }

        .stRadio [role="radiogroup"] label:hover {
            border-color: #7db2df;
            box-shadow: 0 4px 14px rgba(28, 111, 173, 0.12);
        }

        .card-link {
            text-decoration: none !important;
            color: inherit !important;
            display: block;
        }

        .card-wrap {
            position: relative;
            background: #ffffff;
            border: 1px solid #d8e4ef;
            border-radius: 16px;
            padding: 14px 14px 12px;
            margin-bottom: 12px;
            box-shadow: 0 10px 20px rgba(20, 48, 80, 0.07);
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
            overflow: hidden;
        }

        .card-wrap::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #ff8b53, #4eb7c7);
            opacity: 0.9;
        }

        .card-link:hover .card-wrap {
            transform: translateY(-3px);
            border-color: #95bad9;
            box-shadow: 0 16px 26px rgba(20, 48, 80, 0.14);
        }

        .card-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 6px;
        }

        .card-left {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            min-width: 0;
            flex: 1;
        }

        .card-title-wrap {
            min-width: 0;
        }

        .card-icon {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            border: 1px solid #d5e3f1;
            background: #ffffff;
            object-fit: contain;
            padding: 2px;
            flex: 0 0 36px;
        }

        .card-icon-fallback {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            border: 1px solid #d5e3f1;
            background: linear-gradient(135deg, #eaf4ff, #f9fbff);
            color: #35566f;
            font-weight: 700;
            display: grid;
            place-items: center;
            flex: 0 0 36px;
            font-size: 0.9rem;
        }

        .lucas-badge {
            position: relative;
            width: 52px;
            height: 36px;
            border-radius: 11px;
            border: 1px solid #ffb681;
            background: linear-gradient(135deg, #ff7a2f 0%, #ff9f4a 38%, #19a9bf 72%, #0d8aa6 100%);
            box-shadow: 0 8px 16px rgba(182, 92, 36, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.36);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            flex: 0 0 52px;
        }

        .lucas-badge::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, rgba(255, 255, 255, 0.28), rgba(255, 255, 255, 0) 44%);
            pointer-events: none;
        }

        .lucas-word {
            position: relative;
            z-index: 1;
            font-size: 0.62rem;
            font-weight: 800;
            letter-spacing: 0.11em;
            color: #fffaf4;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
            line-height: 1;
        }

        .card-title {
            font-weight: 700;
            font-size: 1.02rem;
            color: #172739;
            line-height: 1.28;
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .card-meta {
            color: #687a8d;
            font-size: 0.8rem;
        }

        .card-category {
            font-size: 0.72rem;
            font-weight: 700;
            color: #205f86;
            background: #edf7ff;
            border: 1px solid #c9e1f4;
            border-radius: 999px;
            padding: 3px 8px;
            white-space: nowrap;
        }

        .card-desc {
            color: #324456;
            font-size: 0.9rem;
            line-height: 1.5;
            min-height: 62px;
            margin-top: 8px;
        }

        .card-foot {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 8px;
            gap: 8px;
        }

        .tags-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .tag {
            display: inline-block;
            background: #f0f6ff;
            color: #5f7083;
            border: 1px solid #d4e3f3;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
        }

        .go-mark {
            font-size: 0.8rem;
            color: #2f8f74;
            font-weight: 700;
        }

        @media (max-width: 768px) {
            .card-desc {
                min-height: auto;
            }
            .hero-shell {
                padding: 16px 14px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="hero-shell">
            <div class="hero-kicker">AI & Testing Resource Hub</div>
            <div class="main-title">{escape(meta.get('title', '资源导航'))}</div>
            <div class="subtitle">{escape(meta.get('subtitle', ''))}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_announcement(data: dict) -> None:
    sections = data.get("announcement", {}).get("sections", [])
    if not sections:
        st.info("暂无公告内容")
        return

    ann_map = {s["label"]: s for s in sections}
    labels = list(ann_map.keys())

    active = st.sidebar.radio("公告菜单", labels, key="ann_label")
    current = ann_map[active]
    title = escape(str(current.get("title", "公告")))
    intro = escape(str(current.get("intro", ""))).replace("\n", "<br/>")
    bullets = current.get("bullets", []) or []
    footer = escape(str(current.get("footer", ""))) if current.get("footer") else ""
    cta_text = escape(str(current.get("ctaText", ""))) if current.get("ctaText") else ""
    cta_url = escape(str(current.get("ctaUrl", "")), quote=True) if current.get("ctaUrl") else ""

    bullet_html = "".join(
        f"<li><span class='ann-no'>{idx:02d}</span><span class='ann-line'>{escape(str(line))}</span></li>"
        for idx, line in enumerate(bullets, start=1)
    )
    footer_html = f"<div class='ann-footer'>{footer}</div>" if footer else ""
    cta_html = (
        f"<div class='ann-cta-wrap'><a class='ann-cta-btn' href='{cta_url}' target='_self' rel='noopener noreferrer'>{cta_text}</a></div>"
        if cta_text and cta_url
        else ""
    )

    st.markdown(
        """
        <style>
        .ann-shell {
            position: relative;
            background: linear-gradient(155deg, #ffffff 0%, #f6fbff 55%, #eef8ff 100%);
            border: 1px solid #d5e7f4;
            border-radius: 18px;
            padding: 18px 18px 14px;
            box-shadow: 0 12px 26px rgba(24, 58, 91, 0.1);
            overflow: hidden;
            margin-top: 4px;
        }
        .ann-shell::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #ff8a4d, #2eb1c7);
        }
        .ann-kicker {
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 700;
            color: #2f6e96;
            background: #edf7ff;
            border: 1px solid #c9e2f5;
            border-radius: 999px;
            padding: 3px 10px;
            margin-bottom: 10px;
        }
        .ann-title {
            font-size: 1.28rem;
            font-weight: 800;
            color: #14263a;
            line-height: 1.28;
            margin-bottom: 8px;
        }
        .ann-intro {
            color: #33485e;
            font-size: 0.95rem;
            line-height: 1.65;
            margin-bottom: 12px;
        }
        .ann-list {
            list-style: none;
            padding: 0;
            margin: 0;
            display: grid;
            gap: 8px;
        }
        .ann-list li {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            background: #ffffff;
            border: 1px solid #ddeaf6;
            border-radius: 12px;
            padding: 9px 10px;
        }
        .ann-no {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 28px;
            height: 22px;
            border-radius: 999px;
            background: #e8f5ff;
            border: 1px solid #c8e4f8;
            color: #2d6d94;
            font-weight: 800;
            font-size: 0.74rem;
            letter-spacing: 0.04em;
        }
        .ann-line {
            color: #2a3e52;
            line-height: 1.52;
            font-size: 0.9rem;
        }
        .ann-footer {
            margin-top: 12px;
            border-radius: 10px;
            border: 1px solid #d4e7f8;
            background: #f4faff;
            color: #2b5a7b;
            padding: 9px 11px;
            font-size: 0.86rem;
            font-weight: 600;
        }
        .ann-cta-wrap {
            margin-top: 12px;
            display: flex;
        }
        .ann-cta-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 8px 14px;
            border-radius: 10px;
            text-decoration: none !important;
            font-size: 0.86rem;
            font-weight: 700;
            color: #ffffff !important;
            border: 1px solid #2f89ac;
            background: linear-gradient(135deg, #ff8b53 0%, #2f9ab1 100%);
            box-shadow: 0 8px 16px rgba(39, 109, 138, 0.25);
            transition: transform 0.16s ease, box-shadow 0.16s ease;
        }
        .ann-cta-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 18px rgba(39, 109, 138, 0.32);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <section class="ann-shell">
            <div class="ann-kicker">站点说明</div>
            <div class="ann-title">{title}</div>
            <div class="ann-intro">{intro}</div>
            <ul class="ann-list">{bullet_html}</ul>
            {footer_html}
            {cta_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_tools(data: dict, tab: str) -> None:
    items, categories = section_payload(data, tab)

    default_category = st.session_state["category_by_tab"].get(tab, "全部")
    if categories and default_category not in ["全部", *categories]:
        default_category = "全部"

    with st.sidebar:
        if categories:
            options = ["全部", *categories]
            category_key = f"category_{tab}"
            if category_key not in st.session_state or st.session_state[category_key] not in options:
                st.session_state[category_key] = default_category if default_category in options else "全部"
            selected = st.radio("分类", options, key=category_key)
            st.session_state["category_by_tab"][tab] = selected
        else:
            selected = None

    search = st.text_input("搜索", key="search", placeholder="输入名称、描述、标签")

    filtered = filter_items(items, search, selected)
    st.caption(f"当前栏目：{tab} · 结果：{len(filtered)} / {len(items)}")

    if not filtered:
        st.warning("没有匹配项，试试更短关键词或切换分类。")
        return

    cols = st.columns(3)
    for i, item in enumerate(filtered):
        with cols[i % 3]:
            item_name = escape(item.get("name", "未命名"))
            item_url = escape(item.get("url", ""), quote=True)
            item_domain = escape(get_domain(item.get("url", "")))
            forced_icon = specific_icon_override(item)
            icon_primary = escape(forced_icon, quote=True) if forced_icon else escape(
                favicon_primary(item.get("url", "")), quote=True
            )
            icon_fallback_1 = escape(favicon_fallback_1(item.get("url", "")), quote=True)
            icon_fallback_2 = escape(favicon_fallback_2(item.get("url", "")), quote=True)
            item_initial = escape((item.get("name", "？")[:1] or "？"))
            item_desc = escape(item.get("description", "暂无描述")).replace("\n", "<br/>")
            tags = "".join(f"<span class='tag'>{escape(str(t))}</span>" for t in item.get("tags", [])[:4])
            category_html = (
                f"<span class='card-category'>{escape(str(item.get('category')))}</span>" if item.get("category") else ""
            )
            card_html = (
                f"<a class='card-link' href='{item_url}' target='_blank' rel='noopener noreferrer'>"
                "<article class='card-wrap'>"
                "<div class='card-top'>"
                "<div class='card-left'>"
                f"<img class='card-icon' src='{icon_primary}' data-fallback1='{icon_fallback_1}' data-fallback2='{icon_fallback_2}' "
                "alt='' loading='lazy' "
                "onerror=\"if(!this.dataset.tried1){this.dataset.tried1='1';this.src=this.dataset.fallback1;}else if(!this.dataset.tried2){this.dataset.tried2='1';this.src=this.dataset.fallback2;}else{this.style.display='none';this.nextElementSibling.style.display='grid';}\"/>"
                f"<span class='card-icon-fallback' style='display:none'>{item_initial}</span>"
                "<div class='card-title-wrap'>"
                f"<div class='card-title' title='{item_name}'>{item_name}</div>"
                f"<div class='card-meta' title='{item_domain}'>{item_domain}</div>"
                "</div>"
                "</div>"
                f"{category_html}"
                "</div>"
                f"<div class='card-desc'>{item_desc}</div>"
                "<div class='card-foot'>"
                f"<div class='tags-wrap'>{tags}</div>"
                "<span class='go-mark'>点击跳转</span>"
                "</div>"
                "</article>"
                "</a>"
            )
            st.markdown(
                card_html,
                unsafe_allow_html=True,
            )


def render_test_toolset_tab() -> None:
    st.subheader("测试工程师常用工具集")
    st.caption("点击卡片即可跳转到工具集站点。")

    card_html = (
        f"<a class='card-link' href='{escape(TEST_TOOLSET_URL, quote=True)}' target='_self' rel='noopener noreferrer'>"
        "<article class='card-wrap'>"
        "<div class='card-top'>"
        "<div class='card-left'>"
        "<span class='lucas-badge'><span class='lucas-word'>LUCAS</span></span>"
        "<div class='card-title-wrap'>"
        "<div class='card-title' title='测试工程师常用工具集'>测试工程师常用工具集</div>"
        "<div class='card-meta' title='lucas-testtool-online.streamlit.app'>lucas-testtool-online.streamlit.app</div>"
        "</div>"
        "</div>"
        "<span class='card-category'>测试导航</span>"
        "</div>"
        "<div class='card-desc'>聚合接口、自动化、性能、安全、管理类测试工具与学习入口。</div>"
        "<div class='card-foot'>"
        "<div class='tags-wrap'>"
        "<span class='tag'>测试工具</span>"
        "<span class='tag'>导航</span>"
        "<span class='tag'>性能</span>"
        "<span class='tag'>自动化</span>"
        "<span class='tag'>安全</span>"
        "</div>"
        "<span class='go-mark'>点击跳转</span>"
        "</div>"
        "</article>"
        "</a>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Lucas 常用网站与工具导航", page_icon="🧭", layout="wide")
    data = load_data()
    ensure_state(data)

    render_header(data.get("siteMeta", {}))

    tabs = data.get("tabs", [])
    if not tabs:
        st.error("数据缺失：tabs")
        return

    active_tab = st.radio("栏目", tabs, horizontal=True, label_visibility="collapsed")

    if active_tab != st.session_state.get("active_tab"):
        st.session_state["search"] = ""
    st.session_state["active_tab"] = active_tab

    if active_tab == "公告":
        render_announcement(data)
    elif active_tab == TEST_TOOLSET_TAB:
        render_test_toolset_tab()
    else:
        render_tools(data, active_tab)


if __name__ == "__main__":
    main()
