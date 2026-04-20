# Lucas 常用网站与工具导航

基于 **Streamlit** 的多栏目导航站，聚合 AI 工具、Prompt、Skill、MCP、OpenClaw、软件测试工具与学习网站，并支持站点图标、公告卡片、分类筛选与关键词搜索。

当前在线工具集（独立 tab 跳转）：
- https://lucas-testtool-online.streamlit.app/

## 功能概览

- 多 Tab 导航：
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

### 2) 配置图标（推荐）

1. 把图标放进 `icons/`（文件名建议使用域名 slug，例如 `openai-com.png`）
2. 在 `icons/name_overrides.json` 增加映射：

```json
{
  "网站名称": "openai-com"
}
```

系统会优先用本地图标；未命中时再尝试远程 favicon 兜底。

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

