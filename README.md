# claude-tool-flow

視覺化 Claude 如何呼叫工具、逐步完成任務。輸入任務後，即時看到 Claude 的決策流程——哪個工具被呼叫、順序為何、最終如何回答，並顯示本次 API token 用量與費用估算。

![sequence diagram showing Claude calling tools](https://raw.githubusercontent.com/emma034186-stack/claude-tool-flow/main/public/index.html)

## 功能

- **循序圖**：即時顯示使用者 → Claude → 工具 → 回傳的完整流程
- **步驟說明**：點「？」按鈕，用白話文解釋每個步驟在做什麼
- **Token 用量**：每次呼叫後自動更新輸入／輸出 token 數與概估費用
- **Mock 模式**：沒有 API Key 也能執行，看模擬流程

---

## 安裝與執行

### 必要條件

- Python 3.8 以上
- Anthropic API Key（[申請連結](https://console.anthropic.com/)）

---

### Mac

```bash
# 1. 下載專案
git clone https://github.com/emma034186-stack/claude-tool-flow.git
cd claude-tool-flow

# 2. 建立虛擬環境（建議）
python3 -m venv venv
source venv/bin/activate

# 3. 安裝套件
pip install flask anthropic

# 4. 啟動伺服器
python3 server.py
```

開啟瀏覽器前往 [http://localhost:3456](http://localhost:3456)

---

### Windows

```bat
:: 1. 下載專案
git clone https://github.com/emma034186-stack/claude-tool-flow.git
cd claude-tool-flow

:: 2. 建立虛擬環境（建議）
python -m venv venv
venv\Scripts\activate

:: 3. 安裝套件
pip install flask anthropic

:: 4. 啟動伺服器
python server.py
```

開啟瀏覽器前往 [http://localhost:3456](http://localhost:3456)

---

## 設定 API Key

1. 開啟頁面後點擊右上角「🔑 設定 Key」
2. 貼上你的 Anthropic API Key（格式：`sk-ant-api03-...`）
3. 點「儲存」

Key 只儲存在瀏覽器的 localStorage，不會傳送到任何第三方。

---

## 使用的模型

`claude-haiku-4-5-20251001` — 速度快、費用低，適合展示工具呼叫流程。

費用概估依官方定價：輸入 $0.80 / 1M tokens，輸出 $4.00 / 1M tokens。

---

## 技術架構

```
browser  ←→  Flask (server.py)  ←→  Anthropic API
              ↑
         Server-Sent Events (SSE) streaming
```

- **後端**：Python Flask + Anthropic Python SDK
- **前端**：原生 HTML / CSS / JavaScript（無框架）
- **串流**：SSE（Server-Sent Events）即時推送每個節點狀態
