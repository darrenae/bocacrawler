import requests
from bs4 import BeautifulSoup
import time
import json
import hashlib
import os

# ======================
# 基本設定
# ======================

BASE = "https://www.boca.gov.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GitHubActionsBot/1.0)"
}

STATE_FILE = "boca_visa_state.json"
OUTPUT_FILE = "boca_visa_qa.txt"


# ======================
# 共用工具
# ======================

def content_hash(title, content, content_type):
    raw = title + "||" + content_type + "||" + "||".join(content)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def detect_category(item):
    title = item["title"]

    if "電子簽證" in title or "eVisa" in title.lower():
        return "電子簽證"
    if "APEC" in title:
        return "APEC 商務卡"
    if "居留" in title:
        return "居留簽證"
    if "停留" in title:
        return "停留簽證"

    return "一般簽證"


# ======================
# 列表頁
# ======================

def fetch_list(page):
    url = f"{BASE}/lp-390-1-{page}-20.html"
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "lxml")
    items = []

    for a in soup.select("div.list ul li a"):
        items.append({
            "title": a.get_text(strip=True).lstrip("0123456789"),
            "url": a["href"]
        })

    return items


# ======================
# 內容頁抽取（三型態）
# ======================

def extract_text_content(soup):
    section = soup.select_one("section.cp")
    if not section:
        return None

    contents = []

    for p in section.find_all("p", recursive=False):
        text = p.get_text(strip=True)
        if text:
            contents.append(text)

    for li in section.select("ol li, ul li"):
        text = li.get_text(strip=True)
        if text:
            contents.append(text)

    return contents if contents else None


def extract_table_content(soup):
    section = soup.select_one("section.cp")
    if not section:
        return None

    tables = section.find_all("table")
    if not tables:
        return None

    results = []

    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th") if th.get_text(strip=True)]

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue

            row = []
            for i, td in enumerate(cells):
                value = td.get_text(strip=True)
                if not value:
                    continue

                if i < len(headers):
                    row.append(f"{headers[i]}：{value}")
                else:
                    row.append(value)

            if row:
                results.append("｜".join(row))

    return results if results else None


def extract_image_content(soup):
    section = soup.select_one("section.cp")
    if not section:
        return None

    images = []
    for img in section.select("img"):
        src = img.get("src")
        if src:
            if src.startswith("/"):
                src = BASE + src
            images.append(src)

    return images if images else None


def fetch_detail(url):
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "lxml")

    title = soup.select_one("h2.title span").get_text(strip=True)
    publish = [li.get_text(strip=True) for li in soup.select("ul.publish_info li")]

    table = extract_table_content(soup)
    text = extract_text_content(soup)
    images = extract_image_content(soup)

    if table:
        content_type = "table"
        content = table
    elif text:
        content_type = "text"
        content = text
    elif images:
        content_type = "image"
        content = images
    else:
        content_type = "empty"
        content = []

    return {
        "title": title,
        "publish_info": publish,
        "content": content,
        "content_type": content_type,
        "url": url
    }


# ======================
# NotebookLM 輸出
# ======================

def export_for_notebooklm(items, filename=OUTPUT_FILE):
    if not items:
        print("No updates. Skip export.")
        return

    with open(filename, "w", encoding="utf-8") as f:
        for item in items:
            f.write(f"[分類]：{item['category']}\n")

            if item["content_type"] == "table":
                f.write("[內容型態]：表格資料\n\n")
            elif item["content_type"] == "image":
                f.write("[內容型態]：流程圖（圖片）\n\n")
            else:
                f.write("\n")

            f.write(f"Q: {item['title']}\n\n")
            f.write("A:\n")

            if item["content_type"] == "image":
                f.write("- 本題內容為官方流程圖，請參考下方圖片。\n")
                for img in item["content"]:
                    f.write(f"- 流程圖連結：{img}\n")
            else:
                for line in item["content"]:
                    f.write(f"- {line}\n")

            for info in item.get("publish_info", []):
                if "發布日期" in info:
                    f.write(f"\n{info}")
                    break

            f.write(f"\n來源：{item['url']}\n")
            f.write("\n" + "=" * 40 + "\n\n")


# ======================
# 主流程（含 diff）
# ======================

def main():
    state = load_state()
    updated = []

    all_items = []
    for page in range(1, 5):
        print(f"Fetching list page {page}")
        all_items.extend(fetch_list(page))
        time.sleep(1)

    for item in all_items:
        detail = fetch_detail(item["url"])
        category = detect_category(detail)

        h = content_hash(detail["title"], detail["content"], detail["content_type"])
        old = state.get(detail["url"])

        if old and old["hash"] == h:
            continue

        record = {
            "url": detail["url"],
            "title": detail["title"],
            "category": category,
            "content_type": detail["content_type"],
            "publish_info": detail["publish_info"],
            "content": detail["content"],
            "hash": h
        }

        state[detail["url"]] = record
        updated.append(record)

        print(f"Updated: {detail['title']}")
        time.sleep(1)

    save_state(state)
    return updated


# ======================
# Entry
# ======================

if __name__ == "__main__":
    updated_items = main()
    export_for_notebooklm(updated_items)
