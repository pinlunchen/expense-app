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


def normalize_text(text: str) -> str:
    t = text.lower().strip()
    mapping = {
        "橄欖油": ["橄欖油", "橄榄油", "olive oil"],
        "wifi": ["wifi", "wi-fi", "wi fi"],
        "電信": ["中華電信", "遠傳", "台哥大"],
        "買菜": ["買菜", "菜", "蔬菜", "水果", "市場", "超市"],
        "加油": ["加油", "加汽油", "加柴油"],
    }
    for standard, variants in mapping.items():
        for v in variants:
            if v in t:
                t = t.replace(v, standard)
    return t


def guess_category(text: str) -> str:
    text = normalize_text(text)

    if any(k in text for k in ["管理費", "社區費", "大樓管理費"]):
        return "管理費"

    if any(k in text for k in ["保險", "勞保", "健保", "勞健保"]):
        return "保險"

    if any(k in text for k in ["稅", "所得稅", "地價稅", "房屋稅", "牌照稅"]):
        return "稅金"

    if any(k in text for k in ["分期"]):
        return "分期"

    if any(k in text for k in ["紅包", "禮金", "人情"]):
        return "人情"

    if any(k in text for k in ["水電瓦斯", "水電", "水費", "電費", "瓦斯", "瓦斯費"]):
        return "水電瓦斯"

    if any(k in text for k in [
        "wifi", "wi-fi", "網路", "上網",
        "中華電信", "遠傳", "台哥大",
        "手機", "電信", "手機費",
    ]):
        return "電信網路"

    if any(k in text for k in [
        "早餐", "午餐", "晚餐", "點心", "飲料", "咖啡", "吃", "餐",
        "買菜", "橄欖油", "超市", "賣場", "全聯", "好市多", "家樂福", "食材", "雜貨",
    ]):
        return "飲食/食品雜貨"

    if any(k in text for k in ["加油", "捷運", "公車", "計程車", "交通", "停車", "uber", "計程"]):
        return "交通"

    if any(k in text for k in ["洗頭", "剪髮", "染髮", "燙髮", "美容", "保養", "護膚", "美甲", "睫毛"]):
        return "美容/保養"

    if any(k in text for k in ["貓", "狗", "飼料", "罐頭", "寵物", "獸醫", "貓砂"]):
        return "寵物"

    if any(k in text for k in ["chatgpt", "claude", "訂閱", "會員", "netflix", "spotify"]):
        return "訂閱費"

    if any(k in text for k in ["電影", "ktv", "旅遊", "門票", "演唱會", "展覽", "娛樂"]):
        return "娛樂/休閒"

    if any(k in text for k in ["看診", "掛號", "藥局", "藥", "醫院", "診所", "健身", "醫療"]):
        return "醫療/健康"

    if any(k in text for k in ["衣服", "褲子", "鞋子", "包包", "服飾", "外套", "內衣"]):
        return "服飾"

    if any(k in text for k in ["課程", "書", "學費", "考試", "補習", "教材", "學習"]):
        return "教育/學習"

    if any(k in text for k in ["家具", "修繕", "修理", "清潔用品", "打掃", "家居", "燈泡", "修水管"]):
        return "家居/修繕"

    return "生活用品/雜支"


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
