from __future__ import annotations

import base64
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
ICON_DIR = BASE_DIR / "icons"
ICON_NAME_MAP_PATH = ICON_DIR / "name_overrides.json"
TEST_TOOLSET_TAB = "测试工程师常用工具集"
TEST_TOOLSET_URL = "https://lucas-testtool-online.streamlit.app/"
AI_NEWS_TAB = "🚀 前线快报"
AI_NEWS_FEEDS = [
    {
        "name": "Google 新闻（中文）",
        "url": "https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "tier": "A",
        "weight": 470,
        "region": "CN",
    },
    {
        "name": "Google News (EN)",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
        "tier": "A",
        "weight": 460,
        "region": "INTL",
    },
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "tier": "S", "weight": 760, "region": "OFFICIAL"},
    {"name": "DeepMind Blog", "url": "https://deepmind.google/blog/rss.xml", "tier": "S", "weight": 720, "region": "OFFICIAL"},
    {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI", "tier": "S", "weight": 700, "region": "OFFICIAL"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "tier": "A", "weight": 560, "region": "INTL"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "tier": "A", "weight": 540, "region": "INTL"},
    {"name": "MIT News AI", "url": "https://news.mit.edu/rss/topic/artificial-intelligence2", "tier": "A", "weight": 620, "region": "INTL"},
    {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss", "tier": "A", "weight": 520, "region": "CN"},
    {"name": "Reddit r/artificial", "url": "https://www.reddit.com/r/artificial/.rss", "tier": "B", "weight": 280, "region": "COMMUNITY"},
    {"name": "Reddit r/MachineLearning", "url": "https://www.reddit.com/r/MachineLearning/.rss", "tier": "B", "weight": 320, "region": "COMMUNITY"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "tier": "S", "weight": 660, "region": "OFFICIAL"},
]
CLAUDE_NEWS_KEYWORDS = (
    "claude",
    "claude ai",
    "claude code",
    "anthropic",
    "anthropic ai",
    "克劳德",
)
CODEX_NEWS_KEYWORDS = (
    "codex",
    "openai codex",
    "chatgpt codex",
)
FEATURE_SIGNAL_KEYWORDS = (
    "release",
    "released",
    "launch",
    "launched",
    "announce",
    "announced",
    "rollout",
    "rolling out",
    "ship",
    "shipping",
    "new feature",
    "feature",
    "capability",
    "update",
    "updated",
    "upgrade",
    "improve",
    "improvement",
    "changelog",
    "version",
    "preview",
    "beta",
    "availability",
    "上线",
    "发布",
    "更新",
    "升级",
    "新增",
    "功能",
    "能力",
    "改进",
    "版本",
    "预览",
)
AI_UPCOMING_EVENTS: list[dict[str, str]] = []
TIER_WEIGHT = {"S": 700, "A": 500, "B": 280}
NEWS_FETCH_TIMEOUT = 4.2
NEWS_FETCH_MAX_WORKERS = 12
NEWS_SNAPSHOT_TTL_SECONDS = 900
NEWS_STALE_SNAPSHOT_MAX_AGE_SECONDS = 7 * 24 * 3600
NEWS_SNAPSHOT_PATH = BASE_DIR / ".cache" / "ai_news_snapshot.json"
NEWS_AUTO_REFRESH_MINUTES = 30
NEWS_AUTO_REFRESH_INTERVAL_SECONDS = NEWS_AUTO_REFRESH_MINUTES * 60
NEWS_AUTO_REFRESH_INTERVAL_MS = NEWS_AUTO_REFRESH_INTERVAL_SECONDS * 1000
SKILL_HOTSPOT_FETCH_TIMEOUT = 4.2
SKILL_HOTSPOT_MAX_WORKERS = 6
SKILL_HOTSPOT_REFRESH_MINUTES = 60
SKILL_HOTSPOT_REFRESH_INTERVAL_SECONDS = SKILL_HOTSPOT_REFRESH_MINUTES * 60
SKILL_HOTSPOT_REFRESH_INTERVAL_MS = SKILL_HOTSPOT_REFRESH_INTERVAL_SECONDS * 1000
SKILL_HOTSPOT_SNAPSHOT_TTL_SECONDS = SKILL_HOTSPOT_REFRESH_INTERVAL_SECONDS
SKILL_HOTSPOT_STALE_SNAPSHOT_MAX_AGE_SECONDS = 30 * 24 * 3600
SKILL_HOTSPOT_SNAPSHOT_PATH = BASE_DIR / ".cache" / "skill_hotspots_snapshot.json"
STALE_NEWS_SNAPSHOT_MARK = "__stale_news_snapshot__"
STALE_SKILLHOT_SNAPSHOT_MARK = "__stale_skillhot_snapshot__"


@st.cache_data(show_spinner=False)
def load_data() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource(show_spinner=False)
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


@st.cache_resource(show_spinner=False)
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


def _is_safe_http_url(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _safe_href(url: str, fallback: str = "#") -> str:
    raw = str(url or "").strip()
    if _is_safe_http_url(raw):
        return escape(raw, quote=True)
    return escape(fallback, quote=True)


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


def specific_icon_override(
    item: dict,
    local: dict[str, str] | None = None,
    name_overrides: dict[str, str] | None = None,
) -> str:
    """Pin reliable icons for known problematic domains/cards."""
    host = get_hostname(str(item.get("url", ""))).lower()
    name_raw = str(item.get("name", "")).strip()
    name = name_raw.lower()
    local = local if local is not None else load_local_icon_data_uri()
    name_overrides = name_overrides if name_overrides is not None else load_icon_name_overrides()

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


def _first_query_value(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    if isinstance(value, tuple):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _get_query_params() -> dict[str, str]:
    try:
        raw = st.experimental_get_query_params()
        if isinstance(raw, dict):
            return {str(k): _first_query_value(v) for k, v in raw.items() if str(k).strip()}
    except Exception:
        pass

    try:
        qp = st.query_params
        out: dict[str, str] = {}
        for key in list(qp.keys()):
            try:
                out[str(key)] = _first_query_value(qp.get(key))
            except Exception:
                out[str(key)] = _first_query_value(qp[key])
        return {k: v for k, v in out.items() if k.strip()}
    except Exception:
        return {}


def _set_query_params(params: dict[str, str]) -> None:
    clean = {str(k): str(v).strip() for k, v in params.items() if str(k).strip() and str(v).strip()}
    current = _get_query_params()
    if current == clean:
        return

    try:
        st.experimental_set_query_params(**clean)
        return
    except Exception:
        pass

    try:
        qp = st.query_params
        for key in list(qp.keys()):
            if key not in clean:
                del qp[key]
        for key, value in clean.items():
            qp[key] = value
    except Exception:
        return


def _sync_share_query(tab: str, category: str = "", keyword: str = "", ann_section: str = "") -> None:
    params: dict[str, str] = {"tab": str(tab).strip()}
    if category and category != "全部":
        params["category"] = str(category).strip()
    if keyword.strip():
        params["q"] = keyword.strip()
    if ann_section.strip():
        params["ann"] = ann_section.strip()
    _set_query_params(params)


def _hydrate_state_from_query(data: dict) -> None:
    params = _get_query_params()
    if not params:
        return

    tabs = [str(x) for x in (data.get("tabs") or [])]
    requested_tab = params.get("tab", "").strip()
    active_tab = requested_tab if requested_tab in tabs else str(st.session_state.get("active_tab", "")).strip()
    if requested_tab in tabs:
        st.session_state["active_tab"] = requested_tab

    keyword = params.get("q", "").strip()
    if keyword:
        if active_tab == AI_NEWS_TAB:
            st.session_state["news_keyword"] = keyword
        else:
            st.session_state["search"] = keyword

    category = params.get("category", "").strip()
    if category and active_tab:
        _, categories = section_payload(data, active_tab)
        valid_categories = {"全部", *[str(x) for x in categories]}
        if category in valid_categories:
            st.session_state.setdefault("category_by_tab", {})
            st.session_state["category_by_tab"][active_tab] = category
            st.session_state[f"category_{active_tab}"] = category

    ann_section = params.get("ann", "").strip()
    if ann_section:
        sections = data.get("announcement", {}).get("sections", []) or []
        for section in sections:
            sid = str(section.get("id", "")).strip()
            if sid != ann_section:
                continue
            st.session_state["ann_section"] = sid
            label = str(section.get("label", "")).strip()
            if label:
                st.session_state["ann_label"] = label
            break


def _compare_price(item: dict) -> str:
    compare = item.get("compare", {})
    if isinstance(compare, dict):
        value = compare.get("price")
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            if text:
                return text

    tags = [str(x).strip().lower() for x in (item.get("tags", []) or []) if str(x).strip()]
    tag_blob = " ".join(tags)
    for key in ("priceModel", "pricing", "price", "billing"):
        value = str(item.get(key, "")).strip()
        if value:
            return value
    if any(x in tag_blob for x in ("免费", "free", "trial", "试用")):
        if "试用" in tag_blob or "trial" in tag_blob:
            return "免费试用"
        return "免费"
    if "开源" in tag_blob or "open source" in tag_blob or "opensource" in tag_blob:
        return "免费/开源"
    if any(x in tag_blob for x in ("付费", "收费", "订阅", "pro")):
        return "付费"
    blob = text_blob(item)
    if any(x in blob for x in ("免费试用", "trial", "free trial")):
        return "免费试用"
    if any(x in blob for x in ("开源", "免费", "free", "opensource", "open source")):
        return "免费/开源"
    if any(x in blob for x in ("付费", "收费", "订阅", "pro", "subscription")):
        return "付费"
    return "待补充"


def _compare_flag(
    item: dict,
    keys: tuple[str, ...],
    positive: tuple[str, ...],
    negative: tuple[str, ...],
    compare_key: str = "",
) -> str:
    compare = item.get("compare", {})
    if compare_key and isinstance(compare, dict) and compare_key in compare:
        raw = compare.get(compare_key)
        if isinstance(raw, bool):
            return "是" if raw else "否"
        text = str(raw or "").strip()
        if text:
            return text

    tags = [str(x).strip().lower() for x in (item.get("tags", []) or []) if str(x).strip()]
    tag_blob = " ".join(tags)
    for key in keys:
        if key not in item:
            continue
        raw = item.get(key)
        if isinstance(raw, bool):
            return "是" if raw else "否"
        value = str(raw or "").strip().lower()
        if not value:
            continue
        if value in {"yes", "true", "1", "y", "是", "支持"}:
            return "是"
        if value in {"no", "false", "0", "n", "否", "不支持"}:
            return "否"
        if value in {"partial", "partly", "limited", "部分"}:
            return "部分"
        return str(raw).strip()

    if any(k in tag_blob for k in positive):
        return "是"
    if any(k in tag_blob for k in negative):
        return "否"

    blob = text_blob(item)
    if any(k in blob for k in positive):
        return "是"
    if any(k in blob for k in negative):
        return "否"
    return "待补充"


def _compare_scenarios(item: dict) -> str:
    compare = item.get("compare", {})
    if isinstance(compare, dict):
        compare_scenarios = compare.get("scenarios")
        if isinstance(compare_scenarios, list):
            values = [str(x).strip() for x in compare_scenarios if str(x).strip()]
            if values:
                return " / ".join(values[:3])
        text = str(compare_scenarios or "").strip()
        if text:
            return text
        alt_text = str(compare.get("scenario", "")).strip()
        if alt_text:
            return alt_text

    for key in ("bestFor", "scenario", "scenarios", "useCases"):
        value = item.get(key)
        if isinstance(value, list):
            lines = [str(x).strip() for x in value if str(x).strip()]
            if lines:
                return " / ".join(lines[:3])
        text = str(value or "").strip()
        if text:
            return text

    tags = item.get("tags", []) or []
    if isinstance(tags, list):
        skip = {"ai", "工具", "tool", "对话", "模型", "平台"}
        picked: list[str] = []
        for tag in tags:
            text = str(tag).strip()
            if not text:
                continue
            if text.lower() in skip:
                continue
            picked.append(text)
            if len(picked) >= 3:
                break
        if picked:
            return " / ".join(picked)
    return "待补充"


def _render_compare_panel(tab: str, filtered_items: list[dict]) -> None:
    label_to_item: dict[str, dict] = {}
    option_labels: list[str] = []
    for idx, item in enumerate(filtered_items, start=1):
        name = str(item.get("name", "未命名")).strip() or "未命名"
        domain = get_domain(str(item.get("url", ""))) or "未知域名"
        base = f"{name} · {domain}"
        label = base
        if label in label_to_item:
            label = f"{base} ({idx})"
        label_to_item[label] = item
        option_labels.append(label)

    compare_key = f"compare_selection_{tab}"
    existing = st.session_state.get(compare_key, [])
    if not isinstance(existing, list):
        existing = []
    st.session_state[compare_key] = [x for x in existing if x in option_labels][:3]

    def _clear_compare_selection() -> None:
        st.session_state[compare_key] = []

    with st.expander("工具对比（Beta）", expanded=False):
        st.caption("勾选 2-3 个工具后，按价格 / 开源 / API / 中文支持 / 适用场景做横向对比。")
        multiselect_kwargs = {
            "label": "选择待对比工具",
            "options": option_labels,
            "key": compare_key,
            "placeholder": "可多选，建议 2-3 个",
            "help": "最多可选择 3 个工具进行横向对比。",
        }
        try:
            selected_labels = st.multiselect(max_selections=3, **multiselect_kwargs)
        except TypeError:
            # Backward compatibility for older Streamlit versions.
            selected_labels = st.multiselect(**multiselect_kwargs)
            if len(selected_labels) > 3:
                keep = selected_labels[:3]
                selected_labels = keep
                st.warning("最多对比 3 个工具，已保留前 3 个。")

        selected_count = len(selected_labels)
        st.caption(f"已选择 {selected_count}/3")
        if selected_count > 0:
            st.button(
                "清空对比选择",
                key=f"{compare_key}_clear",
                on_click=_clear_compare_selection,
            )

        chosen = [(label, label_to_item[label]) for label in selected_labels if label in label_to_item]
        if 0 < len(chosen) < 2:
            st.info("至少选择 2 个工具后显示对比结果。")
            return
        if len(chosen) < 2:
            return

        metric_rows: list[tuple[str, dict[str, str]]] = []
        hidden_metrics: list[str] = []
        strict_metrics = {"价格", "开源", "API", "中文支持"}
        metrics = ("价格", "开源", "API", "中文支持", "适用场景", "官网")

        def _is_unknown(value: str) -> bool:
            text = str(value or "").strip()
            return text in {"", "待补充", "未知", "N/A", "-"}

        for metric in metrics:
            row: dict[str, str] = {}
            for label, item in chosen:
                if metric == "价格":
                    row[label] = _compare_price(item)
                elif metric == "开源":
                    row[label] = _compare_flag(
                        item,
                        keys=("openSource", "isOpenSource"),
                        positive=("开源", "open source", "opensource", "github", "apache", "mit"),
                        negative=("闭源", "closed source", "proprietary", "商业版"),
                        compare_key="openSource",
                    )
                elif metric == "API":
                    row[label] = _compare_flag(
                        item,
                        keys=("apiSupport", "hasApi"),
                        positive=("api", "sdk", "开发者", "developer", "接口", "rest"),
                        negative=("无api", "no api"),
                        compare_key="api",
                    )
                elif metric == "中文支持":
                    row[label] = _compare_flag(
                        item,
                        keys=("chineseSupport", "zhSupport"),
                        positive=("中文", "国产", "国内", "china", "zh"),
                        negative=("english only", "仅英文", "英文", "english"),
                        compare_key="chinese",
                    )
                elif metric == "适用场景":
                    row[label] = _compare_scenarios(item)
                else:
                    row[label] = get_domain(str(item.get("url", ""))) or "待补充"

            values = [row[label] for label, _ in chosen]
            if metric in strict_metrics and all(_is_unknown(v) for v in values):
                hidden_metrics.append(metric)
                continue
            metric_rows.append((metric, row))

        rows: list[dict[str, str]] = []
        for metric, value_map in metric_rows:
            row: dict[str, str] = {"对比维度": metric}
            for label, _ in chosen:
                row[label] = value_map.get(label, "待补充")
            rows.append(row)

        st.table(rows)
        st.caption(f"当前对比：{len(chosen)} 个工具")
        if hidden_metrics:
            st.caption(f"已隐藏缺少有效数据的维度：{', '.join(hidden_metrics)}")


def _strip_html(text: str) -> str:
    raw = unescape(text or "")
    return re.sub(r"<[^>]+>", "", raw).strip()


def _parse_news_time(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        iso = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _format_news_time(dt: datetime | None) -> str:
    if dt is None:
        return "时间未知"
    china_tz = timezone(timedelta(hours=8))
    return dt.astimezone(china_tz).strftime("%Y-%m-%d %H:%M")


def _truncate(text: str, limit: int = 120) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: max(0, limit - 1)].rstrip() + "…"


def _parse_countdown_time(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        dt = None
    if dt is None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        china_tz = timezone(timedelta(hours=8))
        dt = dt.replace(tzinfo=china_tz)
    return dt.astimezone(timezone.utc)


def _countdown_text(seconds: int) -> str:
    sec = max(0, int(seconds))
    if sec <= 0:
        return "已开始"
    if sec < 60:
        return "不足1分钟"
    if sec < 3600:
        return f"{sec // 60}分钟"
    if sec < 86400:
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h}小时{m}分钟"
    d = sec // 86400
    h = (sec % 86400) // 3600
    return f"{d}天{h}小时"


def _build_upcoming_events(data: dict | None = None) -> list[dict]:
    source_items: list[dict] = []
    if isinstance(data, dict):
        raw = data.get("aiUpcomingEvents", [])
        if isinstance(raw, list):
            source_items.extend(x for x in raw if isinstance(x, dict))
    if not source_items:
        source_items.extend(x for x in AI_UPCOMING_EVENTS if isinstance(x, dict))

    now_utc = datetime.now(timezone.utc)
    result: list[dict] = []
    for idx, item in enumerate(source_items, start=1):
        title = str(item.get("title") or item.get("name") or "").strip()
        target_raw = str(item.get("target_at") or item.get("start_at") or item.get("time") or "").strip()
        if not title or not target_raw:
            continue
        target_dt = _parse_countdown_time(target_raw)
        if not target_dt:
            continue
        remaining = int((target_dt - now_utc).total_seconds())
        if remaining < -3600:
            continue

        start_raw = str(item.get("start_from") or "").strip()
        start_dt = _parse_countdown_time(start_raw) if start_raw else None
        try:
            window_hours = max(1.0, float(item.get("window_hours", 72)))
        except Exception:
            window_hours = 72.0
        total_seconds = max(1.0, window_hours * 3600.0)
        if start_dt and start_dt < target_dt:
            total_seconds = max(1.0, (target_dt - start_dt).total_seconds())
            elapsed = (now_utc - start_dt).total_seconds()
        else:
            elapsed = total_seconds - max(0.0, min(float(remaining), total_seconds))
        progress_pct = int(max(0.0, min(1.0, elapsed / total_seconds)) * 100.0)

        result.append(
            {
                "id": f"upcoming_{idx}",
                "title": title,
                "tag": str(item.get("tag", "发布预告")).strip() or "发布预告",
                "url": str(item.get("url", "")).strip(),
                "target_text": _format_news_time(target_dt),
                "remaining_seconds": remaining,
                "remaining_text": _countdown_text(remaining),
                "remaining_minutes": max(0, remaining // 60),
                "progress_pct": progress_pct,
                "is_soon": 0 < remaining <= 2 * 3600,
                "target_ts": target_dt.timestamp(),
            }
        )
    result.sort(key=lambda x: float(x.get("target_ts", 0)))
    return result[:8]


def _parse_github_repo(url: str) -> tuple[str, str] | None:
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host not in {"github.com", "www.github.com"}:
            return None
        parts = [x for x in parsed.path.split("/") if x]
        if len(parts) < 2:
            return None
        owner = parts[0].strip()
        repo = parts[1].strip()
        if not owner or not repo:
            return None
        repo = repo.removesuffix(".git")
        return owner, repo
    except Exception:
        return None


def _extract_skill_repo_key(item: dict) -> str:
    for key in ("downloadUrl", "url"):
        repo = _parse_github_repo(str(item.get(key, "")).strip())
        if repo:
            return f"{repo[0]}/{repo[1]}"
    return ""


def _format_compact_count(value: int) -> str:
    n = max(0, int(value))
    if n >= 1_000_000:
        text = f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        text = f"{n / 1_000:.1f}k"
    else:
        text = str(n)
    return text.replace(".0", "")


def _skill_star_score(raw: object) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or "").strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([mk]?)", text)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return number * 1_000_000.0
    if unit == "k":
        return number * 1_000.0
    return number


def _fetch_github_repo_meta(repo_key: str, timeout: float = SKILL_HOTSPOT_FETCH_TIMEOUT) -> dict | None:
    api_url = f"https://api.github.com/repos/{quote(repo_key, safe='/')}"
    req = Request(
        api_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if isinstance(payload, dict) and str(payload.get("full_name", "")).strip():
        return payload
    return None


def _collect_skill_hotspots_live(seed_groups: list[dict]) -> tuple[list[dict], list[str]]:
    repo_keys: list[str] = []
    for group in seed_groups:
        if not isinstance(group, dict):
            continue
        items = group.get("items", []) or []
        for item in items:
            if not isinstance(item, dict):
                continue
            repo_key = _extract_skill_repo_key(item)
            if repo_key and repo_key not in repo_keys:
                repo_keys.append(repo_key)

    repo_meta: dict[str, dict] = {}
    errors: list[str] = []
    if repo_keys:
        max_workers = min(SKILL_HOTSPOT_MAX_WORKERS, max(1, len(repo_keys)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(_fetch_github_repo_meta, repo_key): repo_key for repo_key in repo_keys}
            for future in as_completed(future_map):
                repo_key = future_map[future]
                try:
                    meta = future.result()
                    if isinstance(meta, dict):
                        repo_meta[repo_key] = meta
                except Exception as exc:
                    errors.append(f"{repo_key} 拉取失败：{exc}")

    china_tz = timezone(timedelta(hours=8))
    now_label = datetime.now(china_tz).strftime("%Y-%m-%d %H:%M")
    refreshed: list[dict] = []
    for group in seed_groups:
        if not isinstance(group, dict):
            continue
        group_out = dict(group)
        items = group.get("items", []) or []
        items_out: list[dict] = []
        group_updated = False
        for item in items:
            if not isinstance(item, dict):
                continue
            item_out = dict(item)
            repo_key = _extract_skill_repo_key(item_out)
            meta = repo_meta.get(repo_key) if repo_key else None
            if isinstance(meta, dict):
                group_updated = True
                stars = meta.get("stargazers_count")
                if isinstance(stars, int) and stars >= 0:
                    item_out["star"] = f"≈{_format_compact_count(stars)}"
                pushed_at = str(meta.get("pushed_at", "")).strip()
                pushed_dt = _parse_news_time(pushed_at)
                if pushed_dt is not None:
                    item_out["freshAt"] = _format_news_time(pushed_dt)
            items_out.append(item_out)
        items_out.sort(key=lambda x: _skill_star_score(x.get("star")), reverse=True)
        group_out["items"] = items_out
        if group_updated:
            group_out["updatedAt"] = f"{now_label}（自动）"
        refreshed.append(group_out)
    return refreshed, errors


def _read_skill_hotspots_snapshot(max_age_seconds: int = SKILL_HOTSPOT_SNAPSHOT_TTL_SECONDS) -> list[dict] | None:
    try:
        if not SKILL_HOTSPOT_SNAPSHOT_PATH.exists():
            return None
        raw = json.loads(SKILL_HOTSPOT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        updated_ts = int(raw.get("updated_ts", 0) or 0)
        groups = raw.get("groups", [])
        if not isinstance(groups, list):
            return None
        if max_age_seconds > 0:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if updated_ts <= 0 or now_ts - updated_ts > max_age_seconds:
                return None
        return [x for x in groups if isinstance(x, dict)]
    except Exception:
        return None


def _write_skill_hotspots_snapshot(groups: list[dict]) -> None:
    try:
        SKILL_HOTSPOT_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_ts": int(datetime.now(timezone.utc).timestamp()),
            "groups": groups,
        }
        tmp_path = SKILL_HOTSPOT_SNAPSHOT_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(SKILL_HOTSPOT_SNAPSHOT_PATH)
    except Exception:
        return


def _sync_auto_refresh_scope(active_tab: str) -> None:
    tab_value = json.dumps(str(active_tab), ensure_ascii=False)
    news_tab_value = json.dumps(AI_NEWS_TAB, ensure_ascii=False)
    skill_tab_value = json.dumps("Skill", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (function() {{
            const host = window.parent || window;
            host.__lucas_active_tab__ = {tab_value};
            if (host.__lucas_active_tab__ !== {news_tab_value} && host.__lucas_news_autorefresh_timer__) {{
                host.clearTimeout(host.__lucas_news_autorefresh_timer__);
                host.__lucas_news_autorefresh_timer__ = null;
            }}
            if (host.__lucas_active_tab__ !== {skill_tab_value} && host.__lucas_skillhot_autorefresh_timer__) {{
                host.clearTimeout(host.__lucas_skillhot_autorefresh_timer__);
                host.__lucas_skillhot_autorefresh_timer__ = null;
            }}
        }})();
        </script>
        """,
        height=0,
    )


def _install_skillhot_auto_refresh(active_tab: str, interval_ms: int = SKILL_HOTSPOT_REFRESH_INTERVAL_MS) -> None:
    components.html(
        f"""
        <script>
        (function() {{
            const host = window.parent || window;
            const activeTab = {json.dumps(str(active_tab), ensure_ascii=False)};
            const key = "__lucas_skillhot_autorefresh_timer__";
            host.__lucas_active_tab__ = activeTab;
            if (host[key]) {{
                host.clearTimeout(host[key]);
            }}
            host[key] = host.setTimeout(function() {{
                if (host.__lucas_active_tab__ !== activeTab) return;
                host.location.reload();
            }}, {int(interval_ms)});
        }})();
        </script>
        """,
        height=0,
    )


def _bump_skillhot_nonce_if_new_window(window_seconds: int = SKILL_HOTSPOT_REFRESH_INTERVAL_SECONDS) -> None:
    bucket = int(datetime.now(timezone.utc).timestamp() // max(1, int(window_seconds)))
    prev_bucket = st.session_state.get("skillhot_auto_pull_bucket")
    st.session_state["skillhot_auto_pull_bucket"] = bucket
    if prev_bucket is not None and int(prev_bucket) != bucket:
        st.session_state["skillhot_nonce"] = int(st.session_state.get("skillhot_nonce", 0)) + 1


@st.cache_data(show_spinner=False, ttl=SKILL_HOTSPOT_SNAPSHOT_TTL_SECONDS)
def fetch_skill_hotspots(seed_groups: list[dict], nonce: int = 0) -> tuple[list[dict], list[str]]:
    _ = nonce  # cache-buster by manual/auto refresh
    groups_seed = [x for x in seed_groups if isinstance(x, dict)]

    if nonce == 0:
        snapshot = _read_skill_hotspots_snapshot(max_age_seconds=SKILL_HOTSPOT_SNAPSHOT_TTL_SECONDS)
        if snapshot:
            return snapshot, []
        stale_snapshot = _read_skill_hotspots_snapshot(max_age_seconds=SKILL_HOTSPOT_STALE_SNAPSHOT_MAX_AGE_SECONDS)
        if stale_snapshot:
            return stale_snapshot, [STALE_SKILLHOT_SNAPSHOT_MARK]

    refreshed, errors = _collect_skill_hotspots_live(groups_seed)
    if refreshed:
        _write_skill_hotspots_snapshot(refreshed)
        return refreshed, errors

    fallback = _read_skill_hotspots_snapshot(max_age_seconds=SKILL_HOTSPOT_STALE_SNAPSHOT_MAX_AGE_SECONDS)
    if fallback:
        return fallback, errors
    return groups_seed, errors


def _relative_news_time(ts: float) -> str:
    if not ts:
        return "时间未知"
    now = datetime.now(timezone.utc).timestamp()
    delta = max(0, int(now - ts))
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{delta // 60} 分钟前"
    if delta < 86400:
        return f"{delta // 3600} 小时前"
    return f"{delta // 86400} 天前"


def _tier_rank(tier: str) -> int:
    return {"S": 3, "A": 2, "B": 1}.get((tier or "B").upper(), 1)


def _emotion_tag(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["辟谣", "rumor", "澄清", "fake", "misinfo"]):
        return "🚨 辟谣"
    if any(k in t for k in ["争议", "监管", "起诉", "lawsuit", "ban", "风险"]):
        return "🤔 争议"
    if any(k in t for k in ["教程", "guide", "论文", "paper", "benchmark", "开源"]):
        return "💡 干货"
    if any(k in t for k in ["发布", "release", "launch", "上线", "融资", "增长", "突破", "升级"]):
        return "📈 利好"
    return "💡 观察"


def _event_blob(ev: dict) -> str:
    return " ".join(
        [
            str(ev.get("title", "")),
            str(ev.get("summary", "")),
            str(ev.get("source", "")),
            str(ev.get("source_line", "")),
            " ".join(str(x) for x in ev.get("sources", [])),
        ]
    ).lower()


def _classify_claude_codex_topic(ev: dict) -> str | None:
    blob = _event_blob(ev)
    has_claude = any(k in blob for k in CLAUDE_NEWS_KEYWORDS)
    has_codex = any(k in blob for k in CODEX_NEWS_KEYWORDS)
    if not (has_claude or has_codex):
        return None

    has_feature_signal = any(k in blob for k in FEATURE_SIGNAL_KEYWORDS)
    source_blob = " ".join([str(ev.get("source", "")), str(ev.get("source_line", ""))]).lower()
    is_official_source = any(k in source_blob for k in ["anthropic", "openai"])
    if not has_feature_signal and not is_official_source:
        return None

    if has_claude and has_codex:
        return "Claude + Codex"
    return "Claude" if has_claude else "Codex"


def _collect_claude_codex_feature_events(events: list[dict], limit: int) -> list[dict]:
    max_items = max(1, int(limit))
    ranked = sorted(
        events,
        key=lambda x: (float(x.get("timestamp", 0)), float(x.get("heat_score", 0))),
        reverse=True,
    )
    picked: list[dict] = []
    for ev in ranked:
        topic = _classify_claude_codex_topic(ev)
        if not topic:
            continue
        row = dict(ev)
        row["agent_topic"] = topic
        picked.append(row)
        if len(picked) >= max_items:
            break
    return picked


def _normalize_title(text: str) -> str:
    t = _strip_html(text).lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[\[\](){}【】<>“”\"'`~!@#$%^&*_+=|\\/:;,.?·，。！？、；：-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _title_tokens(text: str) -> set[str]:
    stop = {
        "ai",
        "the",
        "for",
        "and",
        "with",
        "from",
        "news",
        "artificial",
        "intelligence",
        "machine",
        "learning",
        "about",
        "this",
        "that",
        "发布",
        "宣布",
        "人工智能",
        "模型",
        "公司",
        "官方",
    }
    t = _normalize_title(text)
    tokens = re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}", t)
    out = {x for x in tokens if x not in stop}
    if out:
        return out
    return {t[:28]} if t else set()


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _build_news_events(items: list[dict]) -> list[dict]:
    now_ts = datetime.now(timezone.utc).timestamp()
    clusters: list[dict] = []

    for raw in sorted(items, key=lambda x: float(x.get("timestamp", 0)), reverse=True):
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        tokens = _title_tokens(title)
        assigned = None
        best_sim = 0.0
        for c in clusters:
            sim = _jaccard(tokens, c["tokens"])
            if sim > best_sim:
                best_sim = sim
                assigned = c
        if assigned is not None and best_sim >= 0.45:
            assigned["items"].append(raw)
            assigned["tokens"] |= tokens
        else:
            clusters.append({"items": [raw], "tokens": set(tokens)})

    events: list[dict] = []
    for idx, c in enumerate(clusters, start=1):
        c_items = c["items"]
        latest_ts = max(float(x.get("timestamp", 0)) for x in c_items)
        # primary: higher source weight first, then recency
        primary = sorted(
            c_items,
            key=lambda x: (int(x.get("source_weight", 0)), float(x.get("timestamp", 0))),
            reverse=True,
        )[0]
        source_names = []
        for x in c_items:
            s = str(x.get("source", "未知来源"))
            if s not in source_names:
                source_names.append(s)
        regions = {str(x.get("region", "INTL")) for x in c_items}
        tier = sorted((str(x.get("tier", "B")).upper() for x in c_items), key=_tier_rank, reverse=True)[0]

        age_hours = max(0.0, (now_ts - latest_ts) / 3600.0)
        recency_part = max(0.0, 420.0 - age_hours * 26.0)
        base_weight = max(int(x.get("source_weight", TIER_WEIGHT.get(tier, 280))) for x in c_items)
        mention_part = len(source_names) * 170 + len(c_items) * 70
        region_part = max(0, (len(regions) - 1) * 80)
        heat_score = int(base_weight + recency_part + mention_part + region_part)

        summary = str(primary.get("summary", "")).strip()
        summary = summary if summary else _truncate(str(primary.get("title", "")), 120)
        summary = "核心看点：" + summary
        source_line = " | ".join(source_names[:3]) + (" | ..." if len(source_names) > 3 else "")
        related_count = max(0, len(source_names) - 1)
        is_breaking = age_hours <= 2.0 and _tier_rank(tier) >= _tier_rank("A")
        is_just = age_hours < 1.0
        emoji_hot = "🔥" if heat_score >= 1000 else ""

        events.append(
            {
                "id": f"ev_{idx}",
                "title": str(primary.get("title", "无标题")),
                "link": str(primary.get("link", "")),
                "summary": summary,
                "source": str(primary.get("source", "未知来源")),
                "sources": source_names,
                "source_line": source_line,
                "regions": sorted(regions),
                "tier": tier,
                "heat_score": heat_score,
                "published_at": str(primary.get("published_at", "时间未知")),
                "relative_time": _relative_news_time(latest_ts),
                "timestamp": latest_ts,
                "mentions": len(c_items),
                "source_mentions": len(source_names),
                "related_count": related_count,
                "is_breaking": is_breaking,
                "is_just": is_just,
                "hot_emoji": emoji_hot,
                "emotion_tag": _emotion_tag(f"{primary.get('title', '')} {summary}"),
            }
        )

    return events


def _fetch_text(url: str, timeout: float = 6.0) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _parse_feed_items(feed: dict, max_items: int, timeout: float = NEWS_FETCH_TIMEOUT) -> list[dict]:
    source_name = str(feed.get("name", "未知来源"))
    source_url = str(feed.get("url", ""))
    tier = str(feed.get("tier", "B")).upper()
    source_weight = int(feed.get("weight", TIER_WEIGHT.get(tier, 280)))
    region = str(feed.get("region", "INTL")).upper()

    xml_text = _fetch_text(source_url, timeout=timeout)
    root = ET.fromstring(xml_text)
    items: list[dict] = []

    # RSS
    channel = root.find("channel") or root.find("{*}channel")
    if channel is not None:
        for node in list(channel.findall("item")) + list(channel.findall("{*}item")):
            title = _strip_html((node.findtext("title") or node.findtext("{*}title") or "").strip())
            link = (node.findtext("link") or node.findtext("{*}link") or "").strip()
            raw_time = (
                node.findtext("pubDate")
                or node.findtext("{*}pubDate")
                or node.findtext("updated")
                or node.findtext("{*}updated")
                or ""
            )
            desc_raw = (
                node.findtext("description")
                or node.findtext("{*}description")
                or node.findtext("summary")
                or node.findtext("{*}summary")
                or node.findtext("content")
                or node.findtext("{*}content")
                or ""
            )
            dt = _parse_news_time(raw_time)
            summary = _truncate(_strip_html(desc_raw), 140)
            if title and link:
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "tier": tier,
                        "source_weight": source_weight,
                        "region": region,
                        "published_at": _format_news_time(dt),
                        "summary": summary,
                        "timestamp": dt.timestamp() if dt else 0.0,
                    }
                )
            if len(items) >= max_items:
                break
        return items

    # Atom
    for entry in root.findall("{*}entry"):
        title = _strip_html((entry.findtext("{*}title") or "").strip())
        link = ""
        for link_node in entry.findall("{*}link"):
            href = (link_node.attrib.get("href") or "").strip()
            rel = (link_node.attrib.get("rel") or "alternate").strip()
            if href and rel in {"alternate", ""}:
                link = href
                break
        if not link:
            first_link = entry.find("{*}link")
            if first_link is not None:
                link = (first_link.attrib.get("href") or "").strip()
        raw_time = (entry.findtext("{*}published") or entry.findtext("{*}updated") or "").strip()
        desc_raw = (entry.findtext("{*}summary") or entry.findtext("{*}content") or "").strip()
        dt = _parse_news_time(raw_time)
        summary = _truncate(_strip_html(desc_raw), 140)
        if title and link:
            items.append(
                {
                    "title": title,
                    "link": urljoin(source_url, link),
                    "source": source_name,
                    "tier": tier,
                    "source_weight": source_weight,
                    "region": region,
                    "published_at": _format_news_time(dt),
                    "summary": summary,
                    "timestamp": dt.timestamp() if dt else 0.0,
                }
            )
        if len(items) >= max_items:
            break
    return items


def _active_news_feeds(include_community: bool) -> list[dict]:
    if include_community:
        return AI_NEWS_FEEDS
    return [x for x in AI_NEWS_FEEDS if str(x.get("tier", "B")).upper() != "B"]


def _snapshot_bucket(include_community: bool) -> str:
    return "full" if include_community else "quick"


def _read_news_snapshot(include_community: bool, max_age_seconds: int = NEWS_SNAPSHOT_TTL_SECONDS) -> list[dict] | None:
    try:
        if not NEWS_SNAPSHOT_PATH.exists():
            return None
        raw = json.loads(NEWS_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        bucket = _snapshot_bucket(include_community)
        payload = raw.get(bucket, {})
        if not isinstance(payload, dict):
            return None
        updated_ts = int(payload.get("updated_ts", 0) or 0)
        events = payload.get("events", [])
        if not isinstance(events, list):
            return None
        if max_age_seconds > 0:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if updated_ts <= 0 or now_ts - updated_ts > max_age_seconds:
                return None
        return [x for x in events if isinstance(x, dict)]
    except Exception:
        return None


def _write_news_snapshot(include_community: bool, events: list[dict]) -> None:
    try:
        NEWS_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        root: dict = {}
        if NEWS_SNAPSHOT_PATH.exists():
            try:
                old = json.loads(NEWS_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    root = old
            except Exception:
                root = {}
        bucket = _snapshot_bucket(include_community)
        root[bucket] = {
            "updated_ts": int(datetime.now(timezone.utc).timestamp()),
            "events": events,
        }
        tmp_path = NEWS_SNAPSHOT_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(NEWS_SNAPSHOT_PATH)
    except Exception:
        return


def _install_news_auto_refresh(active_tab: str, interval_ms: int = NEWS_AUTO_REFRESH_INTERVAL_MS) -> None:
    # Client-side timed page refresh while this tab is open.
    components.html(
        f"""
        <script>
        (function() {{
            const host = window.parent || window;
            const activeTab = {json.dumps(str(active_tab), ensure_ascii=False)};
            const key = "__lucas_news_autorefresh_timer__";
            host.__lucas_active_tab__ = activeTab;
            if (host[key]) {{
                host.clearTimeout(host[key]);
            }}
            host[key] = host.setTimeout(function() {{
                if (host.__lucas_active_tab__ !== activeTab) return;
                host.location.reload();
            }}, {int(interval_ms)});
        }})();
        </script>
        """,
        height=0,
    )


def _bump_news_nonce_if_new_window(window_seconds: int = NEWS_AUTO_REFRESH_INTERVAL_SECONDS) -> None:
    # Force one pull when entering a new 30-minute window.
    bucket = int(datetime.now(timezone.utc).timestamp() // max(1, int(window_seconds)))
    prev_bucket = st.session_state.get("news_auto_pull_bucket")
    st.session_state["news_auto_pull_bucket"] = bucket
    if prev_bucket is not None and int(prev_bucket) != bucket:
        st.session_state["news_nonce"] = int(st.session_state.get("news_nonce", 0)) + 1


@st.cache_data(show_spinner=False, ttl=900)
def fetch_ai_news(max_per_feed: int, include_community: bool = False, nonce: int = 0) -> tuple[list[dict], list[str]]:
    _ = nonce  # cache-buster by refresh button
    all_items: list[dict] = []
    errors: list[str] = []

    # Fast path: reuse fresh local snapshot when user did not force refresh.
    if nonce == 0:
        snapshot_events = _read_news_snapshot(include_community=include_community, max_age_seconds=NEWS_SNAPSHOT_TTL_SECONDS)
        if snapshot_events:
            return snapshot_events, []
        stale_snapshot_events = _read_news_snapshot(
            include_community=include_community,
            max_age_seconds=NEWS_STALE_SNAPSHOT_MAX_AGE_SECONDS,
        )
        if stale_snapshot_events:
            return stale_snapshot_events, [STALE_NEWS_SNAPSHOT_MARK]

    feeds = _active_news_feeds(include_community=include_community)
    if not feeds:
        return [], []

    max_workers = min(NEWS_FETCH_MAX_WORKERS, max(1, len(feeds)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_parse_feed_items, feed, max_per_feed): feed for feed in feeds}
        for future in as_completed(future_map):
            feed = future_map[future]
            name = str(feed.get("name", "未知来源"))
            try:
                all_items.extend(future.result())
            except Exception as exc:
                errors.append(f"{name} 抓取失败：{exc}")
    events = _build_news_events(all_items)
    if events:
        _write_news_snapshot(include_community=include_community, events=events)
        return events, errors

    # Fallback: if all sources fail, return latest snapshot (even stale).
    fallback_events = _read_news_snapshot(
        include_community=include_community,
        max_age_seconds=NEWS_STALE_SNAPSHOT_MAX_AGE_SECONDS,
    )
    if fallback_events:
        return fallback_events, errors
    return events, errors


def ensure_state(data: dict) -> None:
    st.session_state.setdefault("active_tab", (data.get("tabs") or [AI_NEWS_TAB])[0])
    st.session_state.setdefault("search", "")
    st.session_state.setdefault("category_by_tab", {})
    st.session_state.setdefault("news_nonce", 0)
    st.session_state.setdefault("news_nonce_applied", 0)
    st.session_state.setdefault("skillhot_nonce", 0)
    st.session_state.setdefault("skillhot_nonce_applied", 0)
    st.session_state.setdefault("url_state_initialized", False)

    tabs = data.get("tabs", [])
    if st.session_state["active_tab"] not in tabs and tabs:
        st.session_state["active_tab"] = tabs[0]

    ann_sections = data.get("announcement", {}).get("sections", [])
    default_ann = ann_sections[0]["id"] if ann_sections else ""
    st.session_state.setdefault("ann_section", default_ann)
    if not bool(st.session_state.get("url_state_initialized")):
        _hydrate_state_from_query(data)
        st.session_state["url_state_initialized"] = True


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

        .subtag-wrap {
            border: 1px solid #d6e5f2;
            border-radius: 13px;
            background: linear-gradient(165deg, #ffffff, #f5faff);
            padding: 10px 12px 8px;
            margin-bottom: 10px;
        }

        .subtag-kicker {
            font-size: 0.74rem;
            color: #55748f;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .subtag-path {
            font-size: 0.8rem;
            color: #6a839a;
            margin-top: 4px;
        }

        [data-testid="stPills"] [role="radiogroup"] {
            gap: 6px;
            row-gap: 7px;
        }

        [data-testid="stPills"] [role="radiogroup"] label {
            border: 1px solid #cfe1f0;
            border-radius: 999px;
            padding: 5px 11px;
            background: #f3f9ff;
            color: #36536b;
            font-size: 0.8rem;
            font-weight: 700;
            transition: 0.16s ease;
        }

        [data-testid="stPills"] [role="radiogroup"] label:hover {
            border-color: #88b4d9;
            background: #eaf5ff;
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

        .skillhot-shell {
            border: 1px solid #d8e6f2;
            border-radius: 16px;
            background: linear-gradient(155deg, #ffffff, #f5fbff);
            box-shadow: 0 10px 22px rgba(21, 48, 79, 0.08);
            padding: 12px;
            margin-bottom: 12px;
        }

        .skillhot-head {
            font-size: 1.02rem;
            font-weight: 800;
            color: #1b2e42;
            margin-bottom: 8px;
        }

        .skillhot-group {
            margin-bottom: 12px;
        }

        .skillhot-group:last-child {
            margin-bottom: 0;
        }

        .skillhot-group-title {
            font-size: 0.86rem;
            color: #45607a;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .skillhot-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }

        .skillhot-card {
            border: 1px solid #d9e7f3;
            border-radius: 12px;
            background: #ffffff;
            padding: 10px;
            display: grid;
            gap: 7px;
        }

        .skillhot-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .skillhot-name {
            font-size: 0.92rem;
            font-weight: 800;
            color: #1f3449;
            line-height: 1.3;
        }

        .skillhot-star {
            font-size: 0.73rem;
            font-weight: 800;
            color: #8b4e1c;
            background: #fff3e8;
            border: 1px solid #ffd2ae;
            border-radius: 999px;
            padding: 2px 8px;
            white-space: nowrap;
        }

        .skillhot-desc {
            color: #4a6178;
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .skillhot-row {
            font-size: 0.78rem;
            color: #5f7488;
            line-height: 1.4;
        }

        .skillhot-row a {
            color: #0f5f95 !important;
            text-decoration: none !important;
            font-weight: 700;
        }

        .skillhot-row a:hover {
            text-decoration: underline !important;
        }

        .skillhot-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .skillhot-tag {
            font-size: 0.72rem;
            color: #597087;
            background: #f1f7ff;
            border: 1px solid #d2e2f2;
            border-radius: 999px;
            padding: 2px 8px;
        }

        .news-shell {
            border: 1px solid #d8e4ef;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 10px 22px rgba(21, 48, 79, 0.08);
            overflow: hidden;
        }

        .news-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            padding: 12px 14px;
            border-bottom: 1px solid #e3edf6;
            background: linear-gradient(90deg, #fff4ea, #edf8ff);
        }

        .news-title-main {
            font-size: 1.02rem;
            font-weight: 800;
            color: #1b2e42;
        }

        .news-meta {
            font-size: 0.8rem;
            color: #597086;
        }

        .agent-hot-card {
            border-color: #d1e7f8;
            background: linear-gradient(165deg, #ffffff, #f5fbff);
        }

        .agent-topic-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 0.72rem;
            font-weight: 800;
            border: 1px solid #bedef3;
            background: linear-gradient(90deg, #edf8ff, #eef5ff);
            color: #2f6488;
            white-space: nowrap;
        }

        .agent-topic-tag.codex {
            border-color: #d5daf9;
            background: linear-gradient(90deg, #f4f1ff, #edf2ff);
            color: #3f4f9a;
        }

        .agent-topic-tag.dual {
            border-color: #ffd2b7;
            background: linear-gradient(90deg, #fff1e6, #eef6ff);
            color: #8f4f22;
        }

        .breaking-wrap {
            margin-bottom: 12px;
            border: 1px solid #f1c9c9;
            border-radius: 12px;
            background: linear-gradient(90deg, #fff5f5, #fffaf8);
            overflow: hidden;
            position: relative;
        }

        .breaking-label {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 82px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.74rem;
            font-weight: 800;
            color: #9c1b1b;
            background: linear-gradient(90deg, #ffd9d9, #fff2f2);
            border-right: 1px solid #f0c7c7;
        }

        .breaking-ticker {
            margin-left: 82px;
            white-space: nowrap;
            overflow: hidden;
            padding: 10px 0;
        }

        .breaking-track {
            display: inline-flex;
            gap: 26px;
            padding-right: 26px;
            animation: breaking-scroll 30s linear infinite;
            will-change: transform;
        }

        .breaking-ticker:hover .breaking-track {
            animation-play-state: paused;
        }

        .breaking-item {
            color: #532323 !important;
            text-decoration: none !important;
            font-size: 0.86rem;
            font-weight: 700;
        }

        .breaking-item:hover {
            text-decoration: underline !important;
            color: #7a1818 !important;
        }

        .breaking-new {
            display: inline-block;
            margin-right: 6px;
            padding: 1px 6px;
            border-radius: 999px;
            background: #ff4c4c;
            color: #fff;
            font-size: 0.66rem;
            font-weight: 800;
            letter-spacing: 0.03em;
        }

        @keyframes breaking-scroll {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
        }

        .hot-grid {
            display: grid;
            gap: 10px;
            padding: 12px;
            background: #f7fbff;
        }

        .hot-card {
            display: grid;
            gap: 8px;
            border: 1px solid #deebf7;
            border-radius: 12px;
            background: #ffffff;
            padding: 10px 11px;
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }

        .hot-card:hover {
            transform: translateY(-1px);
            border-color: #a7c9e8;
            box-shadow: 0 8px 16px rgba(24, 56, 88, 0.12);
        }

        .hot-card-link {
            text-decoration: none !important;
            color: inherit !important;
            display: block;
        }

        .hot-card-link:hover .hot-title {
            color: #0f5f95;
        }

        .hot-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .hot-left {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
        }

        .rank-badge {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: linear-gradient(135deg, #ff9b62, #ff7a43);
            color: #fff;
            font-size: 0.78rem;
            font-weight: 800;
            display: grid;
            place-items: center;
            flex: 0 0 28px;
            box-shadow: 0 5px 10px rgba(222, 110, 61, 0.28);
        }

        .hot-tier {
            font-size: 0.74rem;
            font-weight: 700;
            color: #2f688d;
            background: #eef7ff;
            border: 1px solid #cfe3f4;
            border-radius: 999px;
            padding: 3px 8px;
            width: fit-content;
            white-space: nowrap;
        }

        .hot-score {
            color: #7a4a19;
            background: #fff3e8;
            border: 1px solid #ffd4af;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 0.74rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .news-time {
            color: #6e8296;
            font-size: 0.78rem;
            white-space: nowrap;
        }

        .news-link {
            color: #1e3247 !important;
            text-decoration: none !important;
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.4;
        }

        .news-link:hover {
            color: #0f5f95 !important;
            text-decoration: underline !important;
        }

        .news-summary {
            color: #4b6177;
            font-size: 0.86rem;
            line-height: 1.48;
        }

        .news-source-line {
            color: #5f7387;
            font-size: 0.78rem;
            line-height: 1.35;
        }

        .hot-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .hot-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
            font-weight: 700;
            border: 1px solid #d4e3f3;
            background: #f0f6ff;
            color: #5f7083;
        }

        .hot-tag.just {
            background: #ffecec;
            border-color: #ffc9c9;
            color: #a32a2a;
        }

        .countdown-wrap {
            margin: 12px 0 14px;
            border: 1px solid #dbe8f3;
            border-radius: 14px;
            background: #ffffff;
            overflow: hidden;
            box-shadow: 0 8px 18px rgba(24, 56, 88, 0.08);
        }

        .countdown-head {
            padding: 10px 12px;
            border-bottom: 1px solid #e5eff8;
            background: linear-gradient(90deg, #eef8ff, #fff4eb);
            color: #243b52;
            font-weight: 800;
            font-size: 0.9rem;
        }

        .countdown-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            padding: 11px;
            background: #f8fbff;
        }

        .countdown-card {
            border: 1px solid #d9e7f3;
            border-radius: 12px;
            background: #ffffff;
            padding: 10px;
            display: grid;
            gap: 7px;
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }

        .countdown-card:hover {
            transform: translateY(-1px);
            border-color: #9fc2e3;
            box-shadow: 0 8px 16px rgba(24, 56, 88, 0.12);
        }

        .countdown-card.soon {
            border-color: #ffc6c6;
            background: linear-gradient(160deg, #fffefe, #fff7f7);
        }

        .countdown-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .countdown-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
            font-weight: 700;
            border: 1px solid #d3e3f3;
            background: #eef7ff;
            color: #53718e;
        }

        .countdown-left {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
            font-weight: 800;
            border: 1px solid #ffd2b0;
            background: #fff3e8;
            color: #8b4e1c;
            white-space: nowrap;
        }

        .countdown-title {
            font-size: 0.94rem;
            font-weight: 700;
            color: #1d3349;
            line-height: 1.38;
        }

        .countdown-link {
            text-decoration: none !important;
            color: inherit !important;
            display: block;
        }

        .countdown-link:hover .countdown-title {
            color: #0f5f95;
        }

        .countdown-meta {
            font-size: 0.78rem;
            color: #667f96;
        }

        .countdown-bar {
            height: 8px;
            border-radius: 999px;
            background: #eaf2fa;
            overflow: hidden;
        }

        .countdown-bar > span {
            display: block;
            height: 100%;
            background: linear-gradient(90deg, #ff8c57, #2fa5bc);
            border-radius: 999px;
            min-width: 4px;
        }

        .countdown-foot {
            font-size: 0.75rem;
            color: #7a8ea1;
        }

        .timeline-wrap {
            margin-top: 14px;
            border: 1px solid #dbe7f2;
            border-radius: 14px;
            background: #ffffff;
            overflow: hidden;
        }

        .timeline-head {
            padding: 10px 12px;
            border-bottom: 1px solid #e5eff8;
            background: #f7fbff;
            color: #2c445a;
            font-weight: 800;
            font-size: 0.9rem;
        }

        .timeline-list {
            display: grid;
            gap: 0;
        }

        .timeline-item {
            padding: 10px 12px;
            border-bottom: 1px solid #edf3f9;
            display: grid;
            gap: 6px;
            transition: background-color 0.15s ease;
        }

        .timeline-item:last-child {
            border-bottom: none;
        }

        .timeline-item:hover {
            background: #fbfdff;
        }

        .hot-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #1e3247;
            line-height: 1.4;
        }

        .hot-meta-line {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .timeline-related {
            font-size: 0.78rem;
            color: #7b8fa3;
            padding-left: 4px;
        }

        .rank-badge.rank-1 {
            background: linear-gradient(135deg, #ffd700, #ffb300);
            box-shadow: 0 5px 10px rgba(255, 179, 0, 0.35);
        }

        .rank-badge.rank-2 {
            background: linear-gradient(135deg, #c0c0c0, #9e9e9e);
            box-shadow: 0 5px 10px rgba(158, 158, 158, 0.3);
        }

        .rank-badge.rank-3 {
            background: linear-gradient(135deg, #cd7f32, #b06a28);
            box-shadow: 0 5px 10px rgba(176, 106, 40, 0.3);
        }

        .breaking-hot {
            display: inline-block;
            margin-right: 6px;
            padding: 1px 6px;
            border-radius: 999px;
            background: linear-gradient(90deg, #ff4c4c, #ff6b3d);
            color: #fff;
            font-size: 0.66rem;
            font-weight: 800;
            letter-spacing: 0.03em;
            animation: pulse-hot 1.5s ease-in-out infinite;
        }

        @keyframes pulse-hot {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.65; }
        }

        @media (max-width: 768px) {
            .card-desc {
                min-height: auto;
            }
            .skillhot-grid {
                grid-template-columns: 1fr;
            }
            .hero-shell {
                padding: 16px 14px;
            }
            .breaking-label {
                position: static;
                width: 100%;
                border-right: none;
                border-bottom: 1px solid #f0c7c7;
                padding: 6px 0;
            }
            .breaking-ticker {
                margin-left: 0;
                padding: 8px 0;
            }
            .news-time {
                text-align: left;
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
    _sync_share_query(tab="公告", ann_section=str(current.get("id", "")).strip())
    title = escape(str(current.get("title", "公告")))
    intro = escape(str(current.get("intro", ""))).replace("\n", "<br/>")
    bullets = current.get("bullets", []) or []
    footer = escape(str(current.get("footer", ""))) if current.get("footer") else ""
    cta_text = escape(str(current.get("ctaText", ""))) if current.get("ctaText") else ""
    cta_url = _safe_href(str(current.get("ctaUrl", ""))) if current.get("ctaUrl") else ""

    bullet_html = "".join(
        f"<li><span class='ann-no'>{idx:02d}</span><span class='ann-line'>{escape(str(line))}</span></li>"
        for idx, line in enumerate(bullets, start=1)
    )
    footer_html = f"<div class='ann-footer'>{footer}</div>" if footer else ""
    cta_html = (
        f"<div class='ann-cta-wrap'><a class='ann-cta-btn' href='{cta_url}' target='_self' rel='noopener noreferrer'>{cta_text}</a></div>"
        if cta_text and cta_url != "#"
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


def render_skill_hotspots(data: dict) -> None:
    seed_groups = data.get("skillHotspots", [])
    if not seed_groups:
        return

    with st.sidebar:
        st.markdown("### Skill 热点设置")
        auto_collect = st.toggle(
            "定时收集更新",
            value=True,
            key="skillhot_auto_collect",
            help=f"开启后每 {SKILL_HOTSPOT_REFRESH_MINUTES} 分钟自动拉取一次热点 Skill 仓库信息。",
        )
        if st.button("刷新热点 Skill", key="skillhot_refresh"):
            st.session_state["skillhot_nonce"] = int(st.session_state.get("skillhot_nonce", 0)) + 1

    if auto_collect:
        _install_skillhot_auto_refresh(active_tab="Skill")
        _bump_skillhot_nonce_if_new_window()

    nonce = int(st.session_state.get("skillhot_nonce", 0))
    nonce_applied = int(st.session_state.get("skillhot_nonce_applied", 0))
    fetch_nonce = nonce if nonce > nonce_applied else 0
    groups = seed_groups
    fetch_errors: list[str] = []
    if auto_collect or nonce > 0:
        if fetch_nonce:
            with st.spinner("正在刷新 Skill 热点数据..."):
                groups, fetch_errors = fetch_skill_hotspots(seed_groups=seed_groups, nonce=fetch_nonce)
            st.session_state["skillhot_nonce_applied"] = nonce
        else:
            groups, fetch_errors = fetch_skill_hotspots(seed_groups=seed_groups, nonce=0)
    used_stale_snapshot = STALE_SKILLHOT_SNAPSHOT_MARK in fetch_errors
    fetch_errors = [x for x in fetch_errors if x != STALE_SKILLHOT_SNAPSHOT_MARK]

    if auto_collect:
        st.caption(f"自动收集间隔：每 {SKILL_HOTSPOT_REFRESH_MINUTES} 分钟（支持手动刷新）")
    else:
        st.caption("当前使用静态热点 Skill 数据（已关闭定时收集）")
    if used_stale_snapshot:
        st.caption("已快速加载本地热点缓存，可点击“刷新热点 Skill”立即拉取最新仓库信息。")

    group_html: list[str] = []
    for group in groups:
        category = escape(str(group.get("category", "热点分类")))
        updated_at = escape(str(group.get("updatedAt", "")))
        items = group.get("items", []) or []
        cards: list[str] = []
        for item in items:
            name = escape(str(item.get("name", "未命名 Skill")))
            star = escape(str(item.get("star", "N/A")))
            desc = escape(str(item.get("summary", "暂无说明")))
            download_url = str(item.get("downloadUrl", "")).strip()
            download_href = _safe_href(download_url)
            download_cmd = escape(str(item.get("downloadCmd", "")).strip())
            fresh_at = escape(str(item.get("freshAt", "")).strip())
            download_html = (
                f"<a href='{download_href}' target='_blank' rel='noopener noreferrer'>下载地址</a>"
                if download_href != "#"
                else "下载地址待补充"
            )
            scenarios = item.get("scenarios", []) or []
            scenario_html = "".join(f"<span class='skillhot-tag'>{escape(str(x))}</span>" for x in scenarios[:5])
            cmd_html = f"<div class='skillhot-row'>命令：<code>{download_cmd}</code></div>" if download_cmd else ""
            fresh_html = f"<div class='skillhot-row'>最近提交：{fresh_at}</div>" if fresh_at else ""
            cards.append(
                "<article class='skillhot-card'>"
                "<div class='skillhot-top'>"
                f"<div class='skillhot-name'>{name}</div>"
                f"<span class='skillhot-star'>⭐ {star}</span>"
                "</div>"
                f"<div class='skillhot-desc'>{desc}</div>"
                f"<div class='skillhot-row'>下载：{download_html}</div>"
                f"{cmd_html}"
                f"{fresh_html}"
                f"<div class='skillhot-tags'>{scenario_html}</div>"
                "</article>"
            )
        group_html.append(
            "<section class='skillhot-group'>"
            f"<div class='skillhot-group-title'>{category}{f' · 更新于 {updated_at}' if updated_at else ''}</div>"
            f"<div class='skillhot-grid'>{''.join(cards)}</div>"
            "</section>"
        )

    st.markdown(
        (
            "<section class='skillhot-shell'>"
            "<div class='skillhot-head'>热点 Skill 分类汇总（按 Star 初筛）</div>"
            f"{''.join(group_html)}"
            "</section>"
        ),
        unsafe_allow_html=True,
    )
    if fetch_errors:
        st.caption(f"自动采集提示：{len(fetch_errors)} 个仓库本轮拉取失败，已自动回退缓存/静态数据。")


def render_tools(data: dict, tab: str) -> None:
    items, categories = section_payload(data, tab)

    default_category = st.session_state["category_by_tab"].get(tab, "全部")
    if categories and default_category not in ["全部", *categories]:
        default_category = "全部"

    selected: str | None = None
    if categories:
        options = ["全部", *categories]
        category_key = f"category_{tab}"
        if category_key not in st.session_state or st.session_state[category_key] not in options:
            st.session_state[category_key] = default_category if default_category in options else "全部"
        selected = st.pills(
            f"{tab} 子标签",
            options,
            selection_mode="single",
            default=st.session_state[category_key],
            key=category_key,
            label_visibility="collapsed",
            width="stretch",
        )
        if selected is None:
            selected = "全部"
        st.session_state["category_by_tab"][tab] = selected

    search = st.text_input("搜索", key="search", placeholder=f"在「{tab}」下搜索名称、描述、标签")
    _sync_share_query(tab=tab, category=selected or "", keyword=search)

    filtered = filter_items(items, search, selected)
    path = f"{tab} / {selected}" if selected else tab
    st.caption(f"当前路径：{path} · 结果：{len(filtered)} / {len(items)}")

    if not filtered:
        st.warning("没有匹配项，试试更短关键词或切换分类。")
        return

    _render_compare_panel(tab=tab, filtered_items=filtered)

    local_icons = load_local_icon_data_uri()
    name_overrides = load_icon_name_overrides()
    col_html = ["", "", ""]
    for i, item in enumerate(filtered):
        item_name = escape(item.get("name", "未命名"))
        item_url = _safe_href(item.get("url", ""))
        item_domain = escape(get_domain(item.get("url", "")))
        forced_icon = specific_icon_override(item, local=local_icons, name_overrides=name_overrides)
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
        col_html[i % 3] += card_html

    cols = st.columns(3)
    for idx, col in enumerate(cols):
        with col:
            if col_html[idx]:
                st.markdown(col_html[idx], unsafe_allow_html=True)


def render_ai_news_tab(data: dict | None = None) -> None:
    _install_news_auto_refresh(active_tab=AI_NEWS_TAB)
    _bump_news_nonce_if_new_window()

    st.subheader(AI_NEWS_TAB)
    st.caption("实时滚动头条 + 热度趋势榜 + 长尾时间流，聚合多源 AI 资讯并自动去重（每30分钟自动刷新并拉取）。")

    with st.sidebar:
        st.markdown("### 快报设置")
        max_per_feed = st.slider("每个来源抓取条数", min_value=4, max_value=30, value=8, key="news_per_feed")
        quick_mode = st.toggle(
            "极速模式（推荐）",
            value=True,
            key="news_quick_mode",
            help="开启后仅抓取官方与媒体源，页面加载更快。",
        )
        max_total = st.slider("页面最多展示事件", min_value=20, max_value=140, value=70, key="news_max_total")
        hot_count = st.slider("热榜展示条数", min_value=6, max_value=25, value=12, key="news_hot_count")
        agent_focus_count = st.slider(
            "Claude/Codex 专区条数",
            min_value=4,
            max_value=24,
            value=10,
            key="news_agent_focus_count",
        )
        if st.button("刷新快报", key="news_refresh"):
            st.session_state["news_nonce"] = int(st.session_state.get("news_nonce", 0)) + 1
    nonce = int(st.session_state.get("news_nonce", 0))
    nonce_applied = int(st.session_state.get("news_nonce_applied", 0))
    fetch_nonce = nonce if nonce > nonce_applied else 0

    keyword = st.text_input("关键词筛选", key="news_keyword", placeholder="例如：OpenAI / Agent / 模型 / 论文")
    _sync_share_query(tab=AI_NEWS_TAB, keyword=keyword)
    include_community = not bool(quick_mode)
    active_feeds = _active_news_feeds(include_community=include_community)
    if fetch_nonce:
        with st.spinner("正在刷新前线快报..."):
            events, errors = fetch_ai_news(max_per_feed=max_per_feed, include_community=include_community, nonce=fetch_nonce)
        st.session_state["news_nonce_applied"] = nonce
    else:
        events, errors = fetch_ai_news(max_per_feed=max_per_feed, include_community=include_community, nonce=0)
    used_stale_snapshot = STALE_NEWS_SNAPSHOT_MARK in errors
    errors = [x for x in errors if x != STALE_NEWS_SNAPSHOT_MARK]

    source_options = sorted({str(src) for ev in events for src in ev.get("sources", []) if str(src).strip()})
    selected_sources = st.multiselect(
        "来源筛选",
        source_options,
        default=source_options,
        key="news_sources_filter",
        placeholder="默认全选",
    )
    region_options = sorted({str(r) for ev in events for r in ev.get("regions", []) if str(r).strip()})
    selected_regions = st.multiselect(
        "区域筛选",
        region_options,
        default=region_options,
        key="news_regions_filter",
        placeholder="默认全选",
    )
    time_window = st.selectbox("时间范围", ["全部", "24小时", "3天", "7天", "30天"], key="news_time_window")

    now_ts = datetime.now(timezone.utc).timestamp()
    window_map = {"24小时": 24 * 3600, "3天": 3 * 24 * 3600, "7天": 7 * 24 * 3600, "30天": 30 * 24 * 3600}
    keep_seconds = window_map.get(time_window)
    key = keyword.strip().lower()

    filtered: list[dict] = []
    for ev in events:
        ts = float(ev.get("timestamp", 0) or 0)
        if keep_seconds and ts and now_ts - ts > keep_seconds:
            continue
        if source_options:
            if not selected_sources:
                continue
            if not any(src in selected_sources for src in ev.get("sources", [])):
                continue
        if region_options:
            if not selected_regions:
                continue
            if not any(region in selected_regions for region in ev.get("regions", [])):
                continue
        if key:
            blob = " ".join(
                [
                    str(ev.get("title", "")),
                    str(ev.get("summary", "")),
                    str(ev.get("source", "")),
                    " ".join(str(x) for x in ev.get("sources", [])),
                    " ".join(str(x) for x in ev.get("regions", [])),
                ]
            ).lower()
            if key not in blob:
                continue
        filtered.append(ev)

    if not filtered:
        st.warning("当前没有可展示的快报，请放宽筛选条件或点击“刷新快报”。")
        return

    filtered = sorted(filtered, key=lambda x: (float(x.get("heat_score", 0)), float(x.get("timestamp", 0))), reverse=True)
    timeline_events = sorted(filtered, key=lambda x: float(x.get("timestamp", 0)), reverse=True)[:max_total]
    hot_events = filtered[: min(hot_count, len(filtered))]
    hot_ids = {str(x.get("id", "")) for x in hot_events}
    tail_events = [x for x in timeline_events if str(x.get("id", "")) not in hot_ids]
    if len(tail_events) < 8:
        tail_events = timeline_events
    agent_events = _collect_claude_codex_feature_events(filtered, limit=agent_focus_count)

    breaking_events = [x for x in timeline_events if bool(x.get("is_breaking")) and now_ts - float(x.get("timestamp", 0)) <= 2 * 3600]
    if not breaking_events:
        sa_recent = [x for x in timeline_events if _tier_rank(str(x.get("tier", "B"))) >= _tier_rank("A")]
        breaking_events = (sa_recent or timeline_events)[: min(8, len(sa_recent or timeline_events))]
    breaking_events = breaking_events[:8]

    source_count = len({src for ev in filtered for src in ev.get("sources", [])})
    mode_text = "极速模式" if quick_mode else "全量模式"
    st.caption(
        f"{mode_text} · 覆盖来源：{source_count} / {len(active_feeds)} · 聚合事件：{len(filtered)} · Claude/Codex 专栏：{len(agent_events)}"
    )
    if used_stale_snapshot:
        st.caption("已快速加载本地快照，可点击“刷新快报”立即抓取最新资讯。")
    if errors:
        st.caption(f"抓取提示：{len(errors)} 个来源本轮拉取失败，已自动回退可用数据。")

    if breaking_events:
        ticker_seed = breaking_events * 2 if len(breaking_events) > 1 else breaking_events
        ticker_html = "".join(
            (
                f"<a class='breaking-item' href='{_safe_href(str(ev.get('link', '')))}' target='_blank' rel='noopener noreferrer'>"
                + (
                    "<span class='breaking-hot'>沸点</span>"
                    if int(ev.get("heat_score", 0)) >= 1000
                    else "<span class='breaking-new'>NEW</span>"
                )
                + f"{escape(str(ev.get('title', '无标题')))}"
                f" · {escape(str(ev.get('source', '未知来源')))}"
                "</a>"
            )
            for ev in ticker_seed
        )
        st.markdown(
            (
                "<section class='breaking-wrap'>"
                "<div class='breaking-label'>实时头条</div>"
                "<div class='breaking-ticker'>"
                f"<div class='breaking-track'>{ticker_html}</div>"
                "</div>"
                "</section>"
            ),
            unsafe_allow_html=True,
        )

    upcoming_events = _build_upcoming_events(data)
    if upcoming_events:
        def _countdown_card(ev: dict) -> str:
            soon_cls = " soon" if ev.get("is_soon") else ""
            body = (
                f"<article class='countdown-card{soon_cls}'>"
                "<div class='countdown-top'>"
                f"<span class='countdown-tag'>{escape(str(ev.get('tag', '发布预告')))}</span>"
                f"<span class='countdown-left'>还剩 {escape(str(ev.get('remaining_text', '已开始')))}</span>"
                "</div>"
                f"<div class='countdown-title'>{escape(str(ev.get('title', '预告事件')))}</div>"
                f"<div class='countdown-meta'>目标时间：{escape(str(ev.get('target_text', '时间未知')))}</div>"
                f"<div class='countdown-bar'><span style='width:{int(ev.get('progress_pct', 0))}%;'></span></div>"
                f"<div class='countdown-foot'>约 {int(ev.get('remaining_minutes', 0))} 分钟</div>"
                "</article>"
            )
            url = str(ev.get("url", "")).strip()
            url_href = _safe_href(url)
            if url_href == "#":
                return body
            return (
                f"<a class='countdown-link' href='{url_href}' target='_blank' rel='noopener noreferrer'>"
                f"{body}"
                "</a>"
            )

        countdown_rows = "".join(_countdown_card(ev) for ev in upcoming_events)
        st.markdown(
            (
                "<section class='countdown-wrap'>"
                "<div class='countdown-head'>发布会/预告倒计时</div>"
                f"<div class='countdown-grid'>{countdown_rows}</div>"
                "</section>"
            ),
            unsafe_allow_html=True,
        )

    def _agent_card(ev: dict) -> str:
        topic = str(ev.get("agent_topic", "Claude/Codex"))
        topic_cls = " dual" if topic == "Claude + Codex" else (" codex" if topic == "Codex" else "")
        related = int(ev.get("related_count", 0))
        related_html = f"<div class='timeline-related'>其他{related}家媒体也报道了</div>" if related > 0 else ""
        link = _safe_href(str(ev.get("link", "")))
        return (
            f"<a class='card-link hot-card-link' href='{link}' target='_blank' rel='noopener noreferrer'>"
            f"<article class='hot-card agent-hot-card'>"
            f"<div class='hot-top'>"
            f"<div class='hot-left'>"
            f"<span class='agent-topic-tag{topic_cls}'>{escape(topic)} 功能</span>"
            f"<span class='hot-tier'>{escape(str(ev.get('tier', 'B')))}级来源</span>"
            f"</div>"
            f"<span class='news-time'>{escape(str(ev.get('relative_time', '时间未知')))}</span>"
            f"</div>"
            f"<div class='hot-title'>{escape(str(ev.get('title', '无标题')))}</div>"
            f"<div class='news-summary'>{escape(str(ev.get('summary', '核心看点：点击查看详情。')))}</div>"
            f"<div class='news-source-line'>参考来源：{escape(str(ev.get('source_line', '未知来源')))}</div>"
            f"{related_html}"
            f"<div class='hot-meta-line'>"
            f"<span class='news-time'>{escape(str(ev.get('published_at', '时间未知')))}</span>"
            f"<span class='news-time'>热度 {int(ev.get('heat_score', 0))}</span>"
            f"</div>"
            f"</article>"
            f"</a>"
        )

    if agent_events:
        agent_rows = "".join(_agent_card(ev) for ev in agent_events)
    else:
        agent_rows = (
            "<article class='hot-card agent-hot-card'>"
            "<div class='hot-title'>当前筛选下暂无 Claude/Codex 功能资讯</div>"
            "<div class='news-summary'>可以放宽关键词/时间范围，或点击“刷新快报”获取新一轮聚合结果。</div>"
            "</article>"
        )
    st.markdown(
        (
            "<section class='news-shell'>"
            "<div class='news-head'>"
            "<div class='news-title-main'>Claude / Codex 最新功能资讯</div>"
            "<div class='news-meta'>聚焦版本发布、功能更新、能力升级（按时间优先）</div>"
            "</div>"
            f"<div class='hot-grid'>{agent_rows}</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    def _hot_card(idx: int, ev: dict) -> str:
        rank_cls = f" rank-{idx}" if idx <= 3 else ""
        just_tag = "<span class='hot-tag just'>刚</span>" if ev.get("is_just") else ""
        cross_tag = "<span class='hot-tag'>跨源讨论</span>" if int(ev.get("source_mentions", 1)) > 1 else ""
        related = int(ev.get("related_count", 0))
        related_html = f"<div class='timeline-related'>其他{related}家媒体也报道了</div>" if related > 0 else ""
        link = _safe_href(str(ev.get("link", "")))
        return (
            f"<a class='card-link hot-card-link' href='{link}' target='_blank' rel='noopener noreferrer'>"
            f"<article class='hot-card'>"
            f"<div class='hot-top'>"
            f"<div class='hot-left'>"
            f"<span class='rank-badge{rank_cls}'>{idx}</span>"
            f"<span class='hot-tier'>{escape(str(ev.get('tier', 'B')))}级来源</span>"
            f"</div>"
            f"<span class='hot-score'>{escape(str(ev.get('hot_emoji', '')))} 热度 {int(ev.get('heat_score', 0))}</span>"
            f"</div>"
            f"<div class='hot-title'>{escape(str(ev.get('title', '无标题')))}</div>"
            f"<div class='news-summary'>{escape(str(ev.get('summary', '核心看点：点击查看详情。')))}</div>"
            f"<div class='hot-tags'>"
            f"<span class='hot-tag'>{escape(str(ev.get('emotion_tag', '💡 观察')))}</span>"
            f"{just_tag}{cross_tag}"
            f"</div>"
            f"<div class='news-source-line'>参考来源：{escape(str(ev.get('source_line', '未知来源')))}</div>"
            f"{related_html}"
            f"<div class='hot-meta-line'>"
            f"<span class='news-time'>{escape(str(ev.get('relative_time', '时间未知')))}</span>"
            f"<span class='news-time'>{escape(str(ev.get('published_at', '时间未知')))}</span>"
            f"</div>"
            f"</article>"
            f"</a>"
        )

    hot_rows = "".join(_hot_card(idx, ev) for idx, ev in enumerate(hot_events, start=1))
    st.markdown(
        (
            "<section class='news-shell'>"
            "<div class='news-head'>"
            "<div class='news-title-main'>AI 热度趋势榜</div>"
            "<div class='news-meta'>按来源权重 + 多源提及 + 时间衰减计算</div>"
            "</div>"
            f"<div class='hot-grid'>{hot_rows}</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    def _timeline_item(ev: dict) -> str:
        related = int(ev.get("related_count", 0))
        related_html = f"<div class='timeline-related'>其他{related}家媒体也报道了</div>" if related > 0 else ""
        link = _safe_href(str(ev.get("link", "")))
        return (
            f"<article class='timeline-item'>"
            f"<div class='hot-meta-line'>"
            f"<span class='hot-tier'>{escape(str(ev.get('source', '未知来源')))}</span>"
            f"<span class='news-time'>{escape(str(ev.get('relative_time', '时间未知')))}</span>"
            f"</div>"
            f"<a class='news-link' href='{link}' target='_blank' rel='noopener noreferrer'>"
            f"{escape(str(ev.get('title', '无标题')))}</a>"
            f"<div class='news-summary'>{escape(str(ev.get('summary', '核心看点：点击查看详情。')))}</div>"
            f"<div class='news-source-line'>参考来源：{escape(str(ev.get('source_line', '未知来源')))}</div>"
            f"{related_html}"
            f"</article>"
        )

    timeline_rows = "".join(_timeline_item(ev) for ev in tail_events)
    st.markdown(
        (
            "<section class='timeline-wrap'>"
            "<div class='timeline-head'>普通时间流</div>"
            f"<div class='timeline-list'>{timeline_rows}</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )


def render_test_toolset_tab() -> None:
    st.subheader("测试工程师常用工具集")
    st.caption("点击卡片即可跳转到工具集站点。")
    _sync_share_query(tab=TEST_TOOLSET_TAB)

    card_html = (
        f"<a class='card-link' href='{_safe_href(TEST_TOOLSET_URL)}' target='_self' rel='noopener noreferrer'>"
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
    _sync_auto_refresh_scope(active_tab)

    if active_tab == "公告":
        render_announcement(data)
    elif active_tab == AI_NEWS_TAB:
        render_ai_news_tab(data)
    elif active_tab == TEST_TOOLSET_TAB:
        render_test_toolset_tab()
    elif active_tab == "Skill":
        render_skill_hotspots(data)
        render_tools(data, active_tab)
    else:
        render_tools(data, active_tab)


if __name__ == "__main__":
    main()
