import argparse
import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
import time
import json
import hashlib
import os
import re

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


def detect_category(title):
    if "eVisa" in title or "evisa" in title.lower():
        return "eVisa"
    if "APEC" in title:
        return "APEC"
    if "Resident" in title:
        return "Resident Visa"
    if "Visitor" in title:
        return "Visitor Visa"
    return "Visa"


def build_full_url(url):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return BASE + url
    return f"{BASE}/{url.lstrip('/')}"


def write_single_item_file(item, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
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
                f.write(f"{line}\n")

        for info in item["publish_info"]:
            if "發布日期" in info:
                f.write(f"\n{info}")
                break

        f.write(f"\n來源：{item['url']}\n")


# ======================
# 列表頁
# ======================


def fetch_list(page):
    # 簽證中文 lp-390-1-{page}-20.html
    url = f"{BASE}/lp-181-2-{page}-20.html"
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
# 內容抽取（修正版）
# ======================


def extract_text_content(soup):
    """
    只抽真正的文字內容
    ❌ 明確排除 publish_info
    """
    section = soup.select_one("section.cp")
    if not section:
        return None

    contents = []

    def normalize_text(text):
        return re.sub(r"\s+", " ", text).strip()

    def text_without_nested_lists(node):
        parts = []
        for child in node.contents:
            if isinstance(child, Tag) and child.name in {"ol", "ul"}:
                continue

            if isinstance(child, NavigableString):
                text = normalize_text(str(child))
            elif isinstance(child, Tag):
                text = normalize_text(child.get_text(" ", strip=True))
            else:
                text = ""

            if text:
                parts.append(text)

        return normalize_text(" ".join(parts))

    def parse_list(list_node, depth=0):
        indent = "  " * depth
        is_ordered = list_node.name == "ol"

        for idx, li in enumerate(list_node.find_all("li", recursive=False), start=1):
            text = text_without_nested_lists(li)
            if text:
                prefix = f"{idx}. " if is_ordered else "- "
                contents.append(f"{indent}{prefix}{text}")

            for nested in li.find_all(["ol", "ul"], recursive=False):
                parse_list(nested, depth + 1)

    for child in section.children:
        if not isinstance(child, Tag):
            continue

        if child.name in {"script", "style", "table"}:
            continue
        if child.name == "ul" and "publish_info" in child.get("class", []):
            continue

        if child.name in {"ol", "ul"}:
            parse_list(child)
            continue

        text = normalize_text(child.get_text(" ", strip=True))
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

    rows = []

    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            row = []
            for i, td in enumerate(tds):
                cell = td.get_text(strip=True)
                if not cell:
                    continue
                if i < len(headers):
                    row.append(f"{headers[i]}：{cell}")
                else:
                    row.append(cell)

            if row:
                rows.append("｜".join(row))

    return rows if rows else None


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


# ======================
# 單一內容頁
# ======================


def fetch_detail(url):
    full_url = build_full_url(url)
    res = requests.get(full_url, headers=HEADERS, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "lxml")

    title_node = soup.select_one("h2.title span")
    title = title_node.get_text(strip=True) if title_node else full_url
    publish_info = [
        li.get_text(strip=True)
        for li in soup.select("ul.publish_info li")
    ]

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
        "category": detect_category(title),
        "content_type": content_type,
        "content": content,
        "publish_info": publish_info,
        "url": full_url
    }


# ======================
# NotebookLM 輸出
# ======================


def export_for_notebooklm(items):
    if not items:
        print("No updates.")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
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
                    f.write(f"{line}\n")

            for info in item["publish_info"]:
                if "發布日期" in info:
                    f.write(f"\n{info}")
                    break

            f.write(f"\n來源：{item['url']}\n")
            f.write("\n" + "=" * 40 + "\n\n")


def parse_args():
    parser = argparse.ArgumentParser(description="BOCA 爬蟲與文字輸出工具")
    parser.add_argument(
        "--target",
        nargs=2,
        metavar=("URL", "OUTPUT_TXT"),
        action="append",
        help="指定單一網頁與輸出檔案，可重複使用多次。",
    )
    return parser.parse_args()


def run_custom_targets(targets):
    for url, output_file in targets:
        print(f"Fetching custom page: {url}")
        detail = fetch_detail(url)
        write_single_item_file(detail, output_file)
        print(f"Wrote: {output_file}")


# ======================
# 主流程（含 diff）
# ======================


def main():
    args = parse_args()

    if args.target:
        run_custom_targets(args.target)
        return

    state = load_state()
    updated = []

    all_items = []
    for page in range(1, 5):
        print(f"Fetching list page {page}")
        all_items.extend(fetch_list(page))
        time.sleep(1)

    for item in all_items:
        detail = fetch_detail(item["url"])
        h = content_hash(detail["title"], detail["content"], detail["content_type"])
        old = state.get(detail["url"])

        if old and old["hash"] == h:
            continue

        detail["hash"] = h
        state[detail["url"]] = detail
        updated.append(detail)

        print(f"Updated: {detail['title']}")
        time.sleep(1)

    save_state(state)
    export_for_notebooklm(updated)


# ======================
# Entry
# ======================

if __name__ == "__main__":
    main()
