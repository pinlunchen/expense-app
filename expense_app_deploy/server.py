from __future__ import annotations

import json
import os
import re
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = BASE_DIR / "index.html"
NOTION_VERSION = "2025-09-03"
NOTION_DATA_SOURCE_ID = "2b69d524-7644-80e6-a7fe-000bc26d181b"
NOTION_FIELDS = {
    "title": "title",
    "date": "TSww",
    "amount": "Itz%5C",
    "category": "XNZW",
    "note": "%5EkFg",
}


def parse_expense(text: str, default_date: str, selected_category: str) -> dict:
    cleaned = " ".join(text.strip().split())
    amount_match = re.search(r"(\d+(?:\.\d{1,2})?)", cleaned)
    amount = amount_match.group(1) if amount_match else ""
    name = cleaned
    if amount_match:
        name = cleaned[: amount_match.start()].strip(" ,，") or cleaned
    category = normalize_category(selected_category) or guess_category(cleaned)
    return {
        "name": name or cleaned,
        "amount": amount,
        "date": default_date or datetime.now().strftime("%Y-%m-%d"),
        "category": category,
        "raw_text": cleaned,
    }


def normalize_category(category: str) -> str:
    if not category:
        return ""
    return category.replace(" / ", "／")


def guess_category(text: str) -> str:
    rules = {
        "飲食／日常採買": ["午餐", "晚餐", "早餐", "咖啡", "飲料", "便當", "麵", "飯", "超商", "午茶"],
        "交通": ["捷運", "公車", "計程車", "taxi", "uber", "高鐵", "火車"],
        "寵物": ["貓", "狗", "飼料", "罐頭", "寵物"],
        "電信網路": ["電信", "網路", "中華電信", "台哥大"],
        "保險／社會保險": ["保險", "健保", "勞保"],
        "分期": ["分期", "卡費"],
    }
    lowered = text.lower()
    for category, keywords in rules.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return category
    return "其他"


def create_notion_page(expense: dict) -> None:
    token = os.environ.get("NOTION_SECRET", "").strip()
    if not token:
        raise RuntimeError("缺少 NOTION_SECRET")
    payload = {
        "parent": {"data_source_id": NOTION_DATA_SOURCE_ID},
        "properties": {
            NOTION_FIELDS["title"]: {"title": [{"text": {"content": expense["name"]}}]},
            NOTION_FIELDS["date"]: {"date": {"start": expense["date"]}},
            NOTION_FIELDS["amount"]: {"number": float(expense["amount"] or 0)},
            NOTION_FIELDS["category"]: {"select": {"name": expense["category"]}},
            NOTION_FIELDS["note"]: {"rich_text": [{"text": {"content": expense["raw_text"]}}]},
        },
    }
    request = Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
    )
    with urlopen(request, timeout=20) as response:
        if response.status >= 400:
            raise RuntimeError("Notion 寫入失敗")


class ExpenseHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            content = INDEX_HTML.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/api/expense":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            expense = parse_expense(
                text=payload.get("transcript", ""),
                default_date=payload.get("date", ""),
                selected_category=payload.get("category", ""),
            )
            create_notion_page(expense)
        except json.JSONDecodeError:
            self.respond_json({"error": "資料格式錯誤。"}, HTTPStatus.BAD_REQUEST)
            return
        except (HTTPError, URLError, RuntimeError) as error:
            self.respond_json({"error": f"Notion 連線失敗：{error}"}, HTTPStatus.BAD_GATEWAY)
            return
        except Exception as error:
            self.respond_json({"error": f"發生錯誤：{error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.respond_json({"ok": True, "expense": expense}, HTTPStatus.OK)

    def respond_json(self, payload: dict, status: HTTPStatus) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        return


def run() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ExpenseHandler)
    print(f"Voice expense app running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
