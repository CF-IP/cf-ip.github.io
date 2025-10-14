import os
import re
from datetime import datetime
import time
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
import requests

TARGETS = [
    { "name": "wetest_edgeone_v4", "url": "https://www.wetest.vip/page/edgeone/address_v4.html", "parser": "parse_wetest_table", "ip_col_name": "优选地址", "line_col_name": "线路名称", "fetcher": "fetch_with_selenium" },
    { "name": "wetest_cloudflare_v4", "url": "https://www.wetest.vip/page/cloudflare/address_v4.html", "parser": "parse_wetest_table", "ip_col_name": "优选地址", "line_col_name": "线路名称", "fetcher": "fetch_with_selenium" },
    { "name": "wetest_cloudflare_v6", "url": "https://www.wetest.vip/page/cloudflare/address_v6.html", "parser": "parse_wetest_table", "ip_col_name": "优选地址", "line_col_name": "线路名称", "fetcher": "fetch_with_selenium" },
    { "name": "api_uouin_com", "url": "https://api.uouin.com/cloudflare.html", "parser": "parse_uouin_text", "ip_col_name": "优选IP", "line_col_name": "线路", "fetcher": "fetch_with_selenium" },
    { "name": "hostmonit_v4", "url": "https://stock.hostmonit.com/CloudFlareYes", "parser": "parse_hostmonit_table", "ip_col_name": "IP", "line_col_name": "Line", "fetcher": "fetch_with_phantomjscloud" },
    { "name": "hostmonit_v6", "url": "https://stock.hostmonit.com/CloudFlareYesV6", "parser": "parse_hostmonit_table", "ip_col_name": "IP", "line_col_name": "Line", "fetcher": "fetch_with_phantomjscloud" },
]

def parse_wetest_table(soup):
    header = [th.get_text(strip=True) for th in soup.select("thead th")]
    rows = []
    for tr in soup.select("tbody tr"):
        row_data = [td.get_text(strip=True) for td in tr.select("td")]
        if header and len(row_data) == len(header):
            rows.append(row_data)
    return header, rows

def parse_uouin_text(page_text):
    lines = page_text.strip().splitlines()
    header, rows, colo_index = [], [], -1
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            if "线路" in line and "优选IP" in line:
                temp_header = re.split(r'\s+', line.strip())
                if temp_header[0] == '#':
                    temp_header[0] = '序号'
                
                if 'Colo' in temp_header:
                    colo_index = temp_header.index('Colo')
                    temp_header.pop(colo_index)
                header = temp_header
        elif line and line[0].isdigit():
            parts = re.split(r'\s+', line)
            if header and len(parts) >= len(header):
                if colo_index != -1 and len(parts) > colo_index:
                    parts.pop(colo_index)

                time_col_index = len(header) - 1
                time_str = " ".join(parts[time_col_index:])
                row = parts[:time_col_index] + [time_str]
                row[time_col_index] = row[time_col_index].replace("查询", "").strip()
                if len(row) == len(header):
                    rows.append(row)
    return header, rows

def parse_hostmonit_table(soup):
    table = soup.find("table")
    if not table: return [], []
    header_elements = table.select("thead th")
    if not header_elements: header_elements = table.select("tr:first-child th, tr:first-child td")
    header = [th.get_text(strip=True) for th in header_elements]
    rows = []
    row_elements = table.select("tbody tr")
    if not row_elements: row_elements = table.select("tr")[1:]
    for tr in row_elements:
        row_data = [' '.join(td.stripped_strings).strip() for td in tr.select("td")]
        if header and len(row_data) == len(header):
            rows.append(row_data)
    return header, rows

def get_selenium_driver():
    print("Initializing Selenium WebDriver with Stealth...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    return driver

def fetch_with_selenium(driver, url, target_name):
    print(f"Fetching {url} using Selenium...")
    try:
        driver.get(url)
        if "api.uouin.com" in url:
            wait = WebDriverWait(driver, 35)
            wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "CloudFlare优选IP"))
            wait.until(lambda d: "正在加载" not in d.find_element(By.TAG_NAME, 'body').text)
            time.sleep(2)
            
            initial_text = driver.find_element(By.TAG_NAME, 'body').text
            stale_timestamp = ""
            match = re.search(r'(\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2})', initial_text)
            if match:
                stale_timestamp = match.group(1)
                print(f"Captured intermediate/stale timestamp: {stale_timestamp}")
            else:
                print("Warning: Could not find initial timestamp. Proceeding with a longer blind wait.")
                time.sleep(15)
                return driver.find_element(By.TAG_NAME, 'body').text

            try:
                print("Now waiting for the timestamp to update...")
                wait.until(lambda d: stale_timestamp not in d.find_element(By.TAG_NAME, 'body').text)
                print("Timestamp has updated. Data is fresh.")
            except TimeoutException:
                print("Warning: Timed out waiting for the final timestamp update. Using the intermediate data.")

            return driver.find_element(By.TAG_NAME, 'body').text
        else:
            time.sleep(5)
            return driver.page_source
    except Exception as e:
        print(f"Error fetching {url} with Selenium: {e}")
        return ""

def fetch_with_phantomjscloud(driver, url, target_name):
    print(f"Fetching {url} using PhantomJsCloud API...")
    api_key = "a-demo-key-with-low-quota-per-ip-address"
    api_url = f"https://PhantomJsCloud.com/api/browser/v2/{api_key}/"
    today_str_pjc = datetime.now().strftime('%Y-%m-%d')
    payload = {
        "url": url, "renderType": "html",
        "requestSettings": { "doneWhen": [{ "textExists": today_str_pjc }], "doneWhenTimeout": 25000 }
    }
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        print("Successfully fetched content from PhantomJsCloud.")
        return response.text
    except Exception as e:
        print(f"Error fetching {url} with PhantomJsCloud: {e}")
        return ""

def format_to_tsv(header, rows):
    header_line = "\t".join(header)
    row_lines = ["\t".join(map(str, row)) for row in rows]
    return f"{header_line}\n" + "\n".join(row_lines)

def main():
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    driver = None
    any_file_updated = False
    all_line_ip_pairs = []
    processed_targets_data = []

    try:
        driver = get_selenium_driver()
        for target in TARGETS:
            name, url = target["name"], target["url"]
            print(f"\n--- Processing target: {name} ---")
            
            fetcher_func = globals()[target["fetcher"]]
            content = fetcher_func(driver, url, name)

            if not content:
                print(f"Content for {name} is empty. Skipping.")
                processed_targets_data.append({"target": target, "header": None, "rows": None})
                continue
            
            parser_func = globals()[target["parser"]]
            header, rows = parser_func(BeautifulSoup(content, 'html.parser') if "api.uouin.com" not in url else content)

            if not header or not rows:
                print(f"Failed to parse data for {name}. Skipping.")
            
            processed_targets_data.append({"target": target, "header": header, "rows": rows})

    finally:
        if driver:
            print("\nClosing Selenium WebDriver.")
            driver.quit()
    
    for data in processed_targets_data:
        target, header, rows = data["target"], data["header"], data["rows"]
        name = target["name"]

        if not header or not rows:
            continue

        tsv_filepath = output_dir / f"{name}.tsv"
        new_tsv_content = format_to_tsv(header, rows)
        
        has_changed = True
        if tsv_filepath.exists():
            try:
                if tsv_filepath.read_text(encoding='utf-8') == new_tsv_content:
                    has_changed = False
            except Exception as e:
                print(f"Error reading old file {tsv_filepath}: {e}")

        if has_changed:
            any_file_updated = True
            print(f"Content for {name} has changed.")
            data["has_changed"] = True
        else:
            print(f"Content for {name} has not changed.")
            data["has_changed"] = False

        data["new_tsv_content"] = new_tsv_content
    
    if any_file_updated:
        print("\nOne or more source files have changed. Writing all files...")
        for data in processed_targets_data:
            target, header, rows = data["target"], data["header"], data["rows"]
            name = target["name"]

            if not header or not rows:
                continue
                
            if data.get("has_changed", False):
                print(f"Writing updated files for {name}...")
                tsv_filepath = output_dir / f"{name}.tsv"
                ips_filepath = output_dir / f"{name}_ips.txt"
                tsv_filepath.write_text(data["new_tsv_content"], encoding='utf-8')

                ip_col_index_num = target.get("ip_col_index")
                if "api.uouin.com" in target["url"]: ip_col_index_num = 2
                new_ips_content = "\n".join([row[ip_col_index_num] for row in rows if len(row) > ip_col_index_num]) if ip_col_index_num is not None else ""
                if new_ips_content:
                    ips_filepath.write_text(new_ips_content, encoding='utf-8')

            try:
                ip_col_name = target['ip_col_name']
                line_col_name = target['line_col_name']
                if ip_col_name in header and line_col_name in header:
                    ip_col_idx = header.index(ip_col_name)
                    line_col_idx = header.index(line_col_name)
                    for row in rows:
                        if len(row) > ip_col_idx and len(row) > line_col_idx:
                            all_line_ip_pairs.append(f"{row[line_col_idx]} {row[ip_col_idx]}")
            except (ValueError, KeyError, IndexError) as e:
                print(f"Could not find required columns for {name} for sy.txt aggregation: {e}")

        if all_line_ip_pairs:
            sy_filepath = output_dir / "sy.txt"
            unique_pairs = list(dict.fromkeys(all_line_ip_pairs))
            sy_content = "\n".join(unique_pairs)
            print("Writing sy.txt...")
            sy_filepath.write_text(sy_content, encoding='utf-8')

    else:
        print("\nNo source files have changed. Nothing to write.")

if __name__ == "__main__":
    main()
