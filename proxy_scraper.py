import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import yaml

INITIAL_URL = "https://getsub.classelivre.eu.org/sub"
OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "proxy.txt"

def fetch_html_page(url):
    print(f"Fetching initial HTML page: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
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
        response = requests.get(sub_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching subscription content: {e}")
        return None

def main():
    html = fetch_html_page(INITIAL_URL)
    if not html:
        return

    sub_link = extract_subscription_link(html)
    if not sub_link:
        return

    raw_content = fetch_subscription_content(sub_link)
    if not raw_content:
        return

    results = []
    location_pattern = re.compile(r'([A-Z]{2})')

    try:
        print("Attempting to parse content as YAML...")
        data = yaml.safe_load(raw_content)
        
        if isinstance(data, dict) and 'proxies' in data:
            proxies = data['proxies']
            print(f"Successfully parsed YAML. Found {len(proxies)} proxies.")
            
            for proxy in proxies:
                if 'name' in proxy and 'server' in proxy:
                    remarks = proxy['name']
                    ip_address = proxy['server']
                    
                    match = location_pattern.search(remarks)
                    if match:
                        two_letter_code = match.group(1)
                        output_line = f"{two_letter_code} {ip_address}"
                        results.append(output_line)
        else:
            print("YAML parsed, but no 'proxies' key found.")

    except yaml.YAMLError as e:
        print(f"Could not parse YAML content: {e}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not results:
        print("No valid nodes matched the filtering criteria. Writing an empty proxy.txt.")
        OUTPUT_FILE.write_text("", 'utf-8')
        return

    try:
        unique_results = list(dict.fromkeys(results))
        new_content = "\n".join(unique_results)
        
        has_changed = True
        if OUTPUT_FILE.exists():
            try:
                if OUTPUT_FILE.read_text('utf-8').strip() == new_content.strip():
                    has_changed = False
            except Exception:
                pass
        
        if has_changed:
            print(f"Data has changed. Writing {len(unique_results)} filtered nodes to {OUTPUT_FILE}")
            OUTPUT_FILE.write_text(new_content, 'utf-8')
        else:
            print("Data has not changed. No update needed.")

    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")

if __name__ == "__main__":
    main()
