# Lucas 常用网站与工具导航

基于 **Streamlit** 的多栏目导航站，聚合前线 AI 快报、AI 工具、Prompt、Skill、MCP、OpenClaw、软件测试工具与学习网站，并支持站点图标、公告卡片、分类筛选与关键词搜索。

当前在线工具集（独立 tab 跳转）：
- https://lucas-testtool-online.streamlit.app/

## 功能概览

- 多 Tab 导航：
  - `🚀 前线快报`
  - `AI工具`
  - `Prompt`
  - `Skill`
  - `MCP`
  - `OpenClaw`
  - `软件测试工具`
  - `软件测试学习网站`
  - `测试工程师常用工具集`
  - `公告`
- 卡片化展示（标题 / 描述 / 标签 / 分类）
- 侧边栏分类筛选 + 全局关键词搜索
- `🚀 前线快报`：实时滚动头条 + 热度趋势榜 + 普通时间流
- 支持 `aiUpcomingEvents` 倒计时卡片（可配置发布会/截稿节点）
- `🚀 前线快报` 页面默认每 30 分钟自动刷新并触发新一轮拉取
- `Skill` 热点支持定时收集更新（默认每 60 分钟拉取 GitHub Star/最近提交时间）
- 公告区支持富样式信息卡与 CTA 按钮
- 图标优先本地命中，缺失时自动走 favicon 兜底

## 技术栈

- Python 3.9+
- Streamlit (`streamlit>=1.37,<2`)

## 本地运行

```bash
cd /Users/aitool-remix
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 目录结构

```text
aitool-remix/
├── app.py                  # Streamlit 主应用
├── data.json               # 导航数据源（tab、卡片、公告）
├── icons/                  # 本地图标资源
│   └── name_overrides.json # 名称 -> 图标文件 stem 映射
├── requirements.txt
└── README.md
```

## 数据维护说明

### 1) 新增一个网站卡片

在 `data.json` 对应栏目追加对象（如 `aiTools` / `prompts` / `testTools` 等）：

- 通用字段：`id`, `name`, `url`, `description`, `tags`
- 有分类的栏目额外字段：`category`（如 `aiTools`, `testTools`, `openClaw`）

建议：
- `id` 在同栏目内保持唯一
- `tags` 控制在 3~6 个，便于搜索与展示

可选（推荐）：增加结构化对比字段 `compare`，用于“工具对比（Beta）”更精准展示：

```json
{
  "compare": {
    "price": "免费+付费",
    "openSource": "是/否/部分",
    "api": "是/否/部分",
    "chinese": "是/否/部分",
    "scenarios": ["适用场景1", "适用场景2", "适用场景3"]
  }
}
```

说明：
- `compare` 非必填；缺失时系统会回退到 `tags/description` 关键词推断
- 建议优先维护高频工具（Top 20~50）以获得更稳定的对比结果

### 2) 配置图标（推荐）

1. 把图标放进 `icons/`（文件名建议使用域名 slug，例如 `openai-com.png`）
2. 在 `icons/name_overrides.json` 增加映射：

```json
{
  "网站名称": "openai-com"
}
```

系统会优先用本地图标；未命中时再尝试远程 favicon 兜底。

### 3) 配置前线快报倒计时

在 `data.json` 的 `aiUpcomingEvents` 数组维护事件：

- 必填字段：`title`, `target_at`
- 推荐字段：`tag`, `url`, `window_hours`
- `target_at` 建议使用 ISO 时间（例如 `2026-06-08T10:00:00-07:00`）

### 4) 配置 Skill 热点汇总

在 `data.json` 的 `skillHotspots` 维护热点分组（按 Star 初筛）：

- 分组字段：`category`, `updatedAt`, `items`
- 条目字段：`name`, `star`, `summary`, `downloadUrl`, `downloadCmd`, `scenarios`
- `Skill` Tab 会自动渲染“热点 Skill 分类汇总”卡片
- `downloadUrl` 或 `url` 为 GitHub 仓库时，页面会定时自动刷新 `star` 和最近提交时间（`freshAt`）

## 图标策略（应用内）

卡片图标加载顺序：
1. 本地图标覆盖（`name_overrides.json` / 内置映射）
2. 站点自身 favicon（`https://<host>/favicon.ico`）
3. 兜底 1：`icon.horse`
4. 兜底 2：DuckDuckGo favicon
5. 全部失败则显示文字占位图标

## 部署到 Streamlit Community Cloud

1. 将仓库推送到 GitHub
2. 打开 https://share.streamlit.io/
3. 选择仓库与分支
4. Main file path 填 `app.py`
5. 部署

如果后续只改 `data.json` / `icons`，重新推送后会自动触发更新。
