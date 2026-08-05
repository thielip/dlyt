# dlyt

YouTube／Facebook／Instagram 影片與字幕下載工具（免費可公開部署）。

## 技術架構

| 層級 | 技術 | 免費託管 |
|------|------|----------|
| 前端 | Next.js | [Vercel](https://vercel.com) Free |
| 後端 | Python FastAPI + yt-dlp | [Render](https://render.com) Free |
| 任務狀態 | 記憶體 或 [Upstash Redis](https://upstash.com) Free | 建議上線使用 Redis |
| 保活 | GitHub Actions cron 打 `/health` | 免費 |

> 不做 Celery：在 FastAPI 同一進程用背景任務執行下載，較適合免費方案。

## 本機開發

雙擊或執行 **`start.bat`** 會同時啟動：

- 後端 API：http://127.0.0.1:8000（另開視窗）
- 前端 UI：http://localhost:3000（目前視窗）

首次執行會自動建立 venv、安裝依賴，並寫入 `frontend/.env.local` 指向本機 API。

僅要後端時可用 `start-backend.bat`（除錯用）。

### 無字幕時的語音辨識

若影片沒有現成字幕，可在「僅下載字幕」填入自己的 **Google Gemini API Key**（[AI Studio](https://aistudio.google.com/apikey)），由後端下載音訊後呼叫 Gemini 產生 SRT／VTT／TXT。金鑰只經單次請求傳遞，**不寫入資料庫**。

### 影片長度／單檔流量

預設**不限制**單一影片時長與單檔大小（`MAX_DURATION_SECONDS=0`、`MAX_FILESIZE_BYTES=0`、`MAX_ASR_DURATION_SECONDS=0`）。

### 月流量 90GB

`MAX_MONTHLY_OUTBOUND_BYTES` 預設約 **90GB**。累計使用達上限時，進入網站會優先顯示「**免費流量已使用完畢**」大字彈窗。

### 影片容器

一般畫質預設選 **360p 直連**，並依來源列出 360／480／720／1080。進階輸出需輸入密碼 `0000`，可選 MP4 720／1080／2160（4K，依來源）。

## API 契約（前後端共用）

| Method | Path | 說明 |
|--------|------|------|
| POST | `/api/info` | `{ "url" }` → 影片資訊 |
| POST | `/api/download` | 建立下載任務 → `{ "taskId" }` |
| GET | `/api/tasks/{id}` | 任務進度（輪詢） |
| GET | `/api/files/{id}` | 下載完成檔案 |
| GET | `/health` | 健康檢查／保活 |

## 免費上線步驟

### 1. 推到 GitHub

建立 repo 後把整個 `dlyt` 專案 push 上去（勿提交 `.env`、`.venv`、`node_modules`）。

### 2. Upstash Redis（建議）

1. 註冊 [Upstash](https://upstash.com) → 建立 Redis  
2. 複製 `REDIS_URL`（`rediss://...`）

沒有 Redis 也能跑（記憶體），但 Render 重啟／多實例會丟進度。

### 3. Render（後端）

1. [Render](https://dashboard.render.com) → New → Blueprint，選你的 GitHub repo（會讀 `render.yaml`）  
   或 New Web Service → Docker，Root / Context = `backend`  
2. Plan 選 **Free**  
3. 環境變數：

| Key | 範例 |
|-----|------|
| `REDIS_URL` | Upstash 連線字串 |
| `CORS_ORIGINS` | `https://你的前端.vercel.app,http://localhost:3000` |
| `PUBLIC_BASE_URL` | `https://你的後端.onrender.com` |
| `TMP_DIR` | `/tmp/dlyt` |

4. 部署完成後記下後端網址，確認 `https://xxx.onrender.com/health` 回 `{"status":"ok",...}`。

### 4. Vercel（前端）

1. [Vercel](https://vercel.com) → Import GitHub repo  
2. **Root Directory** = `frontend`  
3. 環境變數：

```env
NEXT_PUBLIC_API_BASE_URL=https://你的後端.onrender.com
```

4. Deploy。之後把實際前端網域補進 Render 的 `CORS_ORIGINS` 再 redeploy 後端。

### 5. GitHub Actions 保活（防 Render 休眠）

1. GitHub repo → Settings → Secrets and variables → Actions  
2. 新增 secret：`BACKEND_HEALTH_URL` = `https://你的後端.onrender.com/health`  
3. Workflow [`.github/workflows/keepalive.yml`](.github/workflows/keepalive.yml) 每 12 分鐘會自動 ping  

休眠醒來第一次請求可能要 30–60 秒，屬免費方案正常現象。

## 免費方案限制

- Render Free 有月用量；保活可減少休眠，無法保證永遠醒著。  
- 雲端 IP 可能被 YouTube 限制，下載偶發失敗；字幕通常較穩。  
- 檔案暫存在伺服器，約 30 分鐘後清除，請盡快下載。  
- 已加簡易 rate limit；公開服務仍可能被濫用。

## 專案結構

```
dlyt/
├── frontend/          # Next.js
├── backend/           # FastAPI + yt-dlp
├── .github/workflows/ # keepalive
├── render.yaml
├── start.bat          # 啟動前端
└── start-backend.bat  # 啟動後端
```
