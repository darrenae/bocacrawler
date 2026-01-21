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
# 工具函式
# ======================

def content_hash(title, content):
    raw = title + "||" + "||".join(content)
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

    if "電子簽證" in title or "eVisa" in title or "e-visa" in title.lower():
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
# 內容頁解析
# ======================

def extract_cp_content(soup):
    section = soup.select_one("section.cp")
    if not section:
        return []

    contents = []

    # 段落
    for p in section.find_all("p", recursive=False):
        text = p.get_text(strip=True)
        if text:
            contents.append(text)

    # 條列
    for li in section.select("ol li, ul li"):
        text = li.get_text(strip=True)
        if text:
            contents.append(text)

    # fallback
    if not contents:
        text = section.get_text(strip=True)
        if text:
            contents.append(text)

    return contents


def fetch_detail(url):
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "lxml")

    title = soup.select_one("h2.title span").get_text(strip=True)
    publish = [li.get_text(strip=True) for li in soup.select("ul.publish_info li")]
    content = extract_cp_content(soup)

    return {
        "title": title,
        "publish_info": publish,
        "content": content,
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
            f.write(f"[分類]：{item['category']}\n\n")
            f.write(f"Q: {item['title']}\n\n")
            f.write("A:\n")

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
        h = content_hash(detail["title"], detail["content"])

        old = state.get(detail["url"])
        if old and old["hash"] == h:
            continue  # 沒變

        record = {
            "url": detail["url"],
            "title": detail["title"],
            "category": category,
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
