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
# 这个模式会寻找任何包含 /sub?uuid= 的完整URL
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
    # 优先使用正则表达式直接从文本中寻找目标链接
    match = re.search(SUB_LINK_PATTERN_RE, html_content)
    if match:
        link = match.group(0)
        # 有些HTML实体可能会被错误编码，进行清理
        cleaned_link = link.replace('&amp;', '&')
        print(f"Found subscription link via Regex: {cleaned_link}")
        return cleaned_link
    
    # 如果正则失败，尝试使用BeautifulSoup作为备用方案
    print("Regex failed, trying BeautifulSoup fallback...")
    soup = BeautifulSoup(html_content, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        if '/sub?uuid=' in a_tag['href']:
            cleaned_link = a_tag['href'].replace('&amp;', '&')
            print(f"Found subscription link with BeautifulSoup: {cleaned_link}")
            return cleaned_link
            
    print("Could not find the subscription link using any method.")
    return None

def fetch_subscription_content(sub_url):
    """获取订阅链接的原始内容（通常是Base64）"""
    print(f"Fetching subscription content from: {sub_url}")
    try:
        headers = {
            # 使用常见的客户端UA
            'User-Agent': 'Clash/2023.08.17'
        }
        response = requests.get(sub_url, headers=headers, timeout=20)
        response.raise_for_status()
        # 直接返回文本，解码操作留给后续处理
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
            # 确保padding正确，以防base64解码错误
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
        # 尝试Base64解码
        decoded_content = base64.b64decode(raw_content).decode('utf-8')
        node_links = decoded_content.strip().splitlines()
        print(f"Successfully decoded Base64 content. Found {len(node_links)} nodes.")
    except (base64.binascii.Error, UnicodeDecodeError, ValueError) as e:
        # *** 关键改动在这里 ***
        # 如果解码失败 (包括ValueError)，则将原始内容作为纯文本处理
        print(f"Failed to decode as Base64 ({type(e).__name__}: {e}). Assuming content is plain text.")
        node_links = raw_content.strip().splitlines()
        
    results = []
    for link in node_links:
        parsed_node = parse_node_link(link)
        if parsed_node and parsed_node.get('ip') and parsed_node.get('location'):
            # 格式化输出: 归属地 IP
            results.append(f"{parsed_node['location']} {parsed_node['ip']}")

    if not results:
        print("No valid nodes were parsed. Output file will not be created.")
        return

    # 创建目录并写入文件
    OUTPUT_DIR.mkdir(exist_ok=True)
    try:
        new_content = "\n".join(results)
        
        has_changed = True
        if OUTPUT_FILE.exists():
            # 读取旧文件内容进行比较
            try:
                if OUTPUT_FILE.read_text('utf-8').strip() == new_content.strip():
                    has_changed = False
            except Exception:
                # 如果读取失败，则视为有变化
                pass
        
        if has_changed:
            print(f"Data has changed. Writing {len(results)} nodes to {OUTPUT_FILE}")
            OUTPUT_FILE.write_text(new_content, 'utf-8')
        else:
            print("Data has not changed. No update needed.")

    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")

if __name__ == "__main__":
    main()
