import base64
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from bs4 import BeautifulSoup

# 目标页面，从中提取真实的订阅链接
INITIAL_URL = "https://getsub.classelivre.eu.org/sub"

# 用于匹配真实订阅链接的结构化正则表达式
SUB_LINK_PATTERN_RE = r'(https?://[^\s\'"]+/sub\?uuid=[^\s\'"]+)'

# 输出文件路径
OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "proxy.txt"

def fetch_html_page(url):
    """获取指定URL的HTML内容"""
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
    """从HTML内容中基于链接结构提取真实的订阅链接"""
    print("Extracting the real subscription link based on its structure...")
    match = re.search(SUB_LINK_PATTERN_RE, html_content)
    if match:
        link = match.group(0).replace('&amp;', '&')
        print(f"Found subscription link via Regex: {link}")
        return link
    
    print("Regex failed, trying BeautifulSoup fallback...")
    soup = BeautifulSoup(html_content, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        if '/sub?uuid=' in a_tag['href']:
            link = a_tag['href'].replace('&amp;', '&')
            print(f"Found subscription link with BeautifulSoup: {link}")
            return link
            
    print("Could not find the subscription link using any method.")
    return None

def fetch_subscription_content(sub_url):
    """获取订阅链接的原始内容"""
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
    """解析单个节点链接 (vless:// 或 vmess://)"""
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
    """主执行函数"""
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
    # --- 关键改动在这里 ---
    # 编译一个正则表达式，用于匹配以两个大写字母开头
    location_pattern = re.compile(r'^[A-Z]{2}')

    for link in node_links:
        parsed_node = parse_node_link(link)
        
        # 确保节点解析成功并包含IP和地区信息
        if parsed_node and parsed_node.get('ip') and parsed_node.get('location'):
            remarks = parsed_node['location'].strip()
            ip_address = parsed_node['ip']

            # 应用新的过滤规则
            match = location_pattern.match(remarks)
            if match:
                # 如果节点名称匹配成功（以两个大写字母开头）
                two_letter_code = match.group(0)  # 提取这两个字母
                
                # 按照 "两个字母 IP地址" 的格式添加到结果列表
                output_line = f"{two_letter_code} {ip_address}"
                results.append(output_line)

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not results:
        print("No valid nodes matched the filtering criteria. Writing an empty proxy.txt.")
        OUTPUT_FILE.write_text("", 'utf-8')
        return

    try:
        # 去重并保持顺序
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
