import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

INITIAL_URL = "https://getsub.classelivre.eu.org/sub"
OUTPUT_DIR = Path("data")
DEBUG_OUTPUT_FILE = OUTPUT_DIR / "raw_subscription_content.txt"

def fetch_html_page(url):
    print(f"Fetching initial HTML page: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching HTML page: {e}")
        return None

def extract_subscription_link(html_content):
    print("Attempting to extract subscription link from styled div...")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    def find_blurry_div(tag):
        return (
            tag.name == 'div' and 
            tag.has_attr('style') and 
            'blur' in tag['style'] and 
            'word-break' in tag['style']
        )

    target_div = soup.find(find_blurry_div)

    if target_div:
        div_text = target_div.get_text(strip=True)
        url_match = re.search(r'https?://[^\s]+', div_text)
        if url_match:
            link = url_match.group(0).replace('&amp;', '&')
            print(f"Found subscription link inside div: {link}")
            return link

    print("Primary method failed. Falling back to generic regex search...")
    fallback_match = re.search(r'(https?://[^\s\'"]+/sub\?uuid=[^\s\'"]+)', html_content)
    if fallback_match:
        link = fallback_match.group(0).replace('&amp;', '&')
        print(f"Found subscription link via fallback regex: {link}")
        return link

    print("Could not find the subscription link using any method.")
    return None

def fetch_subscription_content(sub_url):
    print(f"Fetching subscription content from: {sub_url}")
    try:
        headers = {'User-Agent': 'Clash/2023.08.17'}
        response = requests.get(sub_url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching subscription content: {e}")
        return None

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    html = fetch_html_page(INITIAL_URL)
    if not html:
        print("Failed to fetch initial HTML. Exiting.")
        DEBUG_OUTPUT_FILE.write_text("Error: Failed to fetch initial HTML.", 'utf-8')
        return

    sub_link = extract_subscription_link(html)
    if not sub_link:
        print("Failed to extract subscription link. Exiting.")
        DEBUG_OUTPUT_FILE.write_text("Error: Failed to extract subscription link from HTML.", 'utf-8')
        return

    raw_content = fetch_subscription_content(sub_link)
    if raw_content:
        print(f"Successfully fetched raw content. Length: {len(raw_content)} characters.")
        print(f"Writing raw content to {DEBUG_OUTPUT_FILE}")
        DEBUG_OUTPUT_FILE.write_text(raw_content, 'utf-8')
    else:
        print("Failed to fetch subscription content, or content was empty.")
        DEBUG_OUTPUT_FILE.write_text("Error: Failed to fetch content from the subscription link, or the content was empty.", 'utf-8')

if __name__ == "__main__":
    main()
