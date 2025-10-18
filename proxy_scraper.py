import base64
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from bs4 import BeautifulSoup

INITIAL_URL = "https://getsub.classelivre.eu.org/sub"
OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "proxy.txt"

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

def parse_node_link(link):
    try:
        if link.startswith('vless://'):
            parsed_url = urlparse(link)
            address = parsed_url.hostname
            remarks = unquote(parsed_url.fragment)
            return {'ip': address, 'location': remarks}
        elif link.startswith('vmess://'):
            b64_data = link[8:]
            padded_b64 = b64_data + '=' * (-len(b64_data) % 4)
            decoded_data = base64.b64decode(padded_b64).decode('utf-8')
            vmess_json = json.loads(decoded_data)
            return {'ip': vmess_json.get('add'), 'location': vmess_json.get('ps')}
    except Exception as e:
        print(f"Could not parse node link: {link[:40]}... Error: {e}")
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

    node_links = []
    try:
        decoded_content = base64.b64decode(raw_content).decode('utf-8')
        node_links = decoded_content.strip().splitlines()
        print(f"Successfully decoded Base64 content. Found {len(node_links)} potential nodes.")
    except (base64.binascii.Error, UnicodeDecodeError, ValueError) as e:
        print(f"Failed to decode as Base64 ({type(e).__name__}). Assuming content is plain text.")
        node_links = raw_content.strip().splitlines()
        
    results = []
    location_pattern = re.compile(r'([A-Z]{2})')

    print("\n--- Filtering and Formatting Nodes ---")
    for link in node_links:
        parsed_node = parse_node_link(link)
        
        if parsed_node and parsed_node.get('ip') and parsed_node.get('location'):
            remarks = parsed_node['location'].strip()
            ip_address = parsed_node['ip']
            
            print(f"  - Parsed: IP={ip_address}, Raw Remarks='{remarks}'")

            match = location_pattern.search(remarks)
            if match:
                two_letter_code = match.group(1)
                output_line = f"{two_letter_code} {ip_address}"
                results.append(output_line)
                print(f"    - Kept! Extracted Code: {two_letter_code}, Output: '{output_line}'")
            else:
                print(f"    - Discarded. Remarks do not contain a two-letter uppercase code.")

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not results:
        print("\nNo valid nodes matched the filtering criteria. Writing an empty proxy.txt.")
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
            print(f"\nData has changed. Writing {len(unique_results)} filtered nodes to {OUTPUT_FILE}")
            OUTPUT_FILE.write_text(new_content, 'utf-8')
        else:
            print("\nData has not changed. No update needed.")

    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")

if __name__ == "__main__":
    main()
