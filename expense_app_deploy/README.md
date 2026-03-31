# 語音記帳第一版

這個版本已經可以：

- 手機打開
- 按錄音
- 轉文字
- 按送出
- 寫進 Notion

## 本機啟動

```powershell
cd F:\長文範本\voice_expense_app
$env:NOTION_SECRET="你的 secret"
python server.py
```

## 可部署到 Render

官方文件：
- Web services: https://render.com/docs/web-services
- Environment variables: https://render.com/docs/configure-environment-variables
- PORT / host: https://render.com/docs/environment-variables

### 建議做法

1. 把 `F:\長文範本` 放到 GitHub
2. 到 Render 建一個 Web Service
3. 選這個 repo
4. Root directory 選 `voice_expense_app`
5. Start command 用 `python server.py`
6. 在 Render 環境變數新增 `NOTION_SECRET`

### 成功後

你會拿到一個公開網址。
之後手機直接開那個網址就能用，不用靠這台電腦開著。
