# Streamlit 部署说明

## 本地运行

```bash
cd /Users/leiyuxing/aitool-remix
pip install -r requirements.txt
streamlit run app.py
```

## 部署到 Streamlit Cloud（share.streamlit.io）

1. 把以下文件提交到你的 GitHub 仓库根目录：
   - `app.py`
   - `data.json`
   - `requirements.txt`
2. 打开 https://share.streamlit.io/ 并登录 GitHub。
3. 点击 `New app`：
   - Repository: 选择你的仓库
   - Branch: 选择主分支
   - Main file path: `app.py`
4. 点击 `Deploy`。

## 说明

- 数据全部来自本地 `data.json`，不依赖外部 API。
- 如需更新内容，直接修改 `data.json` 后重新提交。
