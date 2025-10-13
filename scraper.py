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
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

TARGETS = [
    {
        "name": "wetest_edgeone_v4",
        "url": "https://www.wetest.vip/page/edgeone/address_v4.html",
        "parser": "parse_wetest_table",
        "ip_col_index": 1,
    },
    {
        "name": "wetest_cloudflare_v4",
        "url": "https://www.wetest.vip/page/cloudflare/address_v4.html",
        "parser": "parse_wetest_table",
        "ip_col_index": 1,
    },
    {
        "name": "wetest_cloudflare_v6",
        "url": "https://www.wetest.vip/page/cloudflare/address_v6.html",
        "parser": "parse_wetest_table",
        "ip_col_index": 1,
    },
    {
        "name": "api_uouin_com",
        "url": "https://api.uouin.com/cloudflare.html",
        "parser": "parse_uouin_text",
        "ip_col_index": 2,
    },
    {
        "name": "hostmonit_v4",
        "url": "https://stock.hostmonit.com/CloudFlareYes",
        "parser": "parse_hostmonit_table",
        "ip_col_index": 1,
    },
    {
        "name": "hostmonit_v6",
        "url": "https://stock.hostmonit.com/CloudFlareYesV6",
        "parser": "parse_hostmonit_table",
        "ip_col_index": 1,
    },
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
    header = []
    rows = []
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            if "线路" in line and "优选IP" in line:
                header = re.split(r'\s+', line.strip('# \t'))
        elif line and line[0].isdigit():
            parts = re.split(r'\s+', line)
            if header and len(parts) >= len(header):
                time_str = " ".join(parts[len(header)-2:])
                row = parts[:len(header)-2] + [time_str]
                if len(row) == len(header) - 1: row.insert(-1, 'N/A')
                if len(row) == len(header): rows.append(row)
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
        row_data = [ ' '.join(td.stripped_strings).strip() for td in tr.select("td")]
        if header and len(row_data) == len(header):
            rows.append(row_data)
    return header, rows

def get_selenium_driver():
    print("Initializing Selenium WebDriver with Stealth...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    return driver

def fetch_page_content(driver, url, target_name):
    print(f"Fetching {url}...")
    try:
        driver.get(url)
        if "api.uouin.com" in url:
            WebDriverWait(driver, 25).until(
                lambda d: "正在加载" not in d.find_element(By.TAG_NAME, 'body').text and datetime.now().strftime('%Y/%m/%d') in d.find_element(By.TAG_NAME, 'body').text
            )
            print("Dynamic content loaded for uouin.")
            return driver.find_element(By.TAG_NAME, 'body').text
        elif "hostmonit.com" in url:
            today_str = datetime.now().strftime('%Y-%m-%d')
            print(f"Waiting for hostmonit content with date: {today_str}")
            WebDriverWait(driver, 25).until(
                lambda d: today_str in d.find_element(By.TAG_NAME, 'body').text
            )
            print("Dynamic content with correct date loaded for hostmonit.")
            return driver.page_source
        else:
            time.sleep(5)
            return driver.page_source
    except Exception as e:
        print(f"Error fetching or waiting for {url}: {e}")
        try:
            driver.save_screenshot(f"{target_name}_error.png")
            print(f"Saved screenshot to {target_name}_error.png")
        except Exception as se:
            print(f"Could not save screenshot: {se}")
        return ""

def format_to_tsv(header, rows):
    header_line = "\t".join(header)
    row_lines = ["\t".join(map(str, row)) for row in rows]
    return header_line + "\n" + "\n".join(row_lines)

def main():
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    driver = get_selenium_driver()
    any_file_updated = False
    try:
        for target in TARGETS:
            name, url = target["name"], target["url"]
            print(f"\n--- Processing target: {name} ---")
            content = fetch_page_content(driver, url, name)
            if not content:
                print(f"Content for {name} is empty. Skipping.")
                continue
            
            parser_func = globals()[target["parser"]]
            if "api.uouin.com" in url:
                header, rows = parser_func(content)
            else:
                header, rows = parser_func(BeautifulSoup(content, 'html.parser'))

            if not header or not rows:
                print(f"Failed to parse data for {name}. Skipping.")
                continue

            new_tsv_content = format_to_tsv(header, rows)
            ip_col_index = target.get("ip_col_index")
            new_ips_content = "\n".join([row[ip_col_index] for row in rows if len(row) > ip_col_index]) if ip_col_index is not None else ""

            tsv_filepath = output_dir / f"{name}.tsv"
            ips_filepath = output_dir / f"{name}_ips.txt"

            has_changed = True
            if tsv_filepath.exists():
                try:
                    if tsv_filepath.read_text(encoding='utf-8') == new_tsv_content:
                        has_changed = False
                except Exception as e:
                    print(f"Error reading old file {tsv_filepath}: {e}")

            if has_changed:
                print(f"Content for {name} has changed. Writing new files.")
                tsv_filepath.write_text(new_tsv_content, encoding='utf-8')
                if new_ips_content:
                    ips_filepath.write_text(new_ips_content, encoding='utf-8')
                any_file_updated = True
            else:
                print(f"Content for {name} has not changed. Skipping file write.")
    finally:
        print("\nClosing Selenium WebDriver.")
        driver.quit()
    
    if not any_file_updated:
        print("\nNo files were updated.")

if __name__ == "__main__":
    main()
