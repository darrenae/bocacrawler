import requests
from bs4 import BeautifulSoup
import time

BASE = "https://www.boca.gov.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GitHubActionsBot/1.0)"
}

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

def extract_cp_content(soup):
    section = soup.select_one("section.cp")
    if not section:
        return []

    contents = []

    for p in section.find_all("p", recursive=False):
        text = p.get_text(strip=True)
        if text:
            contents.append(text)

    for li in section.select("ol li, ul li"):
        text = li.get_text(strip=True)
        if text:
            contents.append(text)

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

def main():
    all_items = []
    for page in range(1, 5):
        print(f"Fetching list page {page}")
        all_items.extend(fetch_list(page))
        time.sleep(1)

    results = []
    for item in all_items:
        print(f"Fetching detail: {item['title']}")
        results.append(fetch_detail(item["url"]))
        time.sleep(1)

    print(f"Total records: {len(results)}")
    return results  

if __name__ == "__main__":
    results = main()        
    print("==== SAMPLE ====")
    print(results[0]["title"])
    print(results[0]["content"])       
