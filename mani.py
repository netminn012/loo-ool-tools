# mani.py
# pip install requests beautifulsoup4
import argparse
import os
import re
import time
import json
import csv
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_OVERVIEW = "https://loo-ool.com/rail/{line}/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://loo-ool.com/rail/"
}

def fetch(session, url, method="GET", data=None, timeout=15):
    if method == "GET":
        r = session.get(url, timeout=timeout)
    else:
        r = session.post(url, data=data or {}, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return r

def collect_candidate_urls(session, overview_url, line, date):
    r = fetch(session, overview_url)
    soup = BeautifulSoup(r.text, "html.parser")
    anchors = soup.find_all("a", href=True)
    candidates = set()

    for a in anchors:
        href = a["href"]
        abs_href = urljoin(overview_url, href)
        if "e233.cgi" in href or re.search(rf"/rail/{line}/\d+/{date}/", href):
            candidates.add(abs_href)

    return list(candidates)

def try_parse_fragment(soup):
    form = soup.find("form", id="inp")
    if not form:
        return None

    code_el = form.find("span", class_="s")
    code = code_el.get_text(strip=True) if code_el else None

    meta_el = form.find("span", class_="j")
    formation = meta_el.get_text(strip=True) if meta_el else None

    time_el = form.find("span", class_="W")
    start_time = time_el.get_text(strip=True) if time_el else None

    location = None
    if time_el and time_el.next_sibling:
        location = str(time_el.next_sibling).strip()

    du = form.find("div", class_="du")
    operations = [p.get_text("", strip=True) for p in du.find_all("p")] if du else []

    return {
        "code": code,
        "formation": formation,
        "start_time": start_time,
        "location": location,
        "operations": operations
    }

def scrape(line, date, outdir="out"):
    os.makedirs(outdir, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    overview_url = BASE_OVERVIEW.format(line=line)
    print(f"[+] Overview: {overview_url}")
    candidates = collect_candidate_urls(session, overview_url, line, date)
    print(f"[+] Found {len(candidates)} candidate URLs")

    results = []
    for url in candidates:
        try:
            print("GET:", url)
            r2 = fetch(session, url)
            soup2 = BeautifulSoup(r2.text, "html.parser")
            parsed = try_parse_fragment(soup2)
            if parsed:
                parsed["url"] = url
                results.append(parsed)
            # time.sleep(0.5)
        except Exception as e:
            print("Error:", e)

    # JSON出力
    json_path = os.path.join(outdir, f"{line}_{date}_operations.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # CSV 出力
    csv_path = os.path.join(outdir, f"{line}_{date}_operations.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "formation", "start_time", "location", "operation_line", "url"])
        for item in results:
            ops = item.get("operations", [])
            if ops:
                for line_text in ops:
                    writer.writerow([item["code"], item["formation"], item["start_time"], item["location"], line_text, item["url"]])
            else:
                writer.writerow([item["code"], item["formation"], item["start_time"], item["location"], "", item["url"]])

    print(f"[+] JSON written to {json_path}")
    print(f"[+] CSV written to {csv_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("line", help="路線コード例: K, H, T, c, A など")
    p.add_argument("--date", default=None, help="形式 YYYYMMDD （未指定時は本日）")
    p.add_argument("--outdir", default="out", help="出力フォルダ（デフォルト: out）")
    args = p.parse_args()

    date = args.date or datetime.now().strftime("%Y%m%d")
    scrape(args.line, date, outdir=args.outdir)
