const BASE_DOMAIN = "665966.xyz";

const preferredDomains = [
    "ct1", "ct2", "ct3", "ct4", "ct5",
    "cu1", "cu2", "cu3", "cu4", "cu5",
    "cm1", "cm2", "cm3", "cm4", "cm5",
    "ty1", "ty2", "ty3", "ty4", "ty5",
    "ipv61", "ipv62", "ipv63", "ipv64", "ipv65"
];

const proxyPrefixes = {
    'ca': '加拿大', 'de': '德国', 'sg': '新加坡', 'jp': '日本',
    'se': '瑞典', 'us': '美国', 'fi': '芬兰', 'gb': '英国',
    'nl': '荷兰', 'kr': '韩国', 'hk': '香港'
};
const proxyDomains = Object.keys(proxyPrefixes);

export default {
    async fetch(request) {
        const url = new URL(request.url);
        
        if (url.pathname === '/cf') {
            return handlePlainTextPath(preferredDomains, BASE_DOMAIN);
        }
        
        if (url.pathname === '/proxy') {
            return handlePlainTextPath(proxyDomains, BASE_DOMAIN);
        }

        return new Response(generateHtml(), {
            headers: { 
                'Content-Type': 'text/html; charset=UTF-8',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'
            },
        });
    },
};

function handlePlainTextPath(prefixList, baseDomain) {
    const fullDomainList = prefixList.map(prefix => `${prefix}.${baseDomain}`).join('\n');
    return new Response(fullDomainList, {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
}

function generateHtml() {
    const updateTime = getUpdateTime();
    const proxyData = generateProxyTableData(proxyDomains);
    
    return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>域名状态面板</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 10px; }
        .container { max-width: 900px; margin: 0 auto; }
        h2 { color: #bb86fc; border-bottom: 2px solid #333; padding-bottom: 10px; }
        .table-container { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background-color: #1e1e1e; box-shadow: 0 4px 8px rgba(0,0,0,0.3); min-width: 600px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #333; white-space: nowrap; }
        th { background-color: #333; color: #e0e0e0; }
        tr.data-row { cursor: pointer; transition: background-color 0.2s ease; }
        tr.data-row:hover { background-color: #383838; }
        .copy-feedback { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background-color: #03dac6; color: #121212; padding: 10px 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); opacity: 0; transition: opacity 0.5s ease, transform 0.5s ease; z-index: 1000; pointer-events: none; }
        .copy-feedback.show { opacity: 1; transform: translateX(-50%) translateY(-10px); }
        .placeholder-text { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h2>优选域名</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>序号</th><th>地址</th><th>归属地</th><th>更新时间</th></tr>
                </thead>
                <tbody id="preferred-tbody">
                    ${preferredDomains.map((prefix, index) => `
                        <tr id="row-${prefix}" class="data-row">
                            <td>${index + 1}</td>
                            <td>${prefix}.${BASE_DOMAIN}</td>
                            <td class="location-cell placeholder-text">正在查询...</td>
                            <td>${updateTime}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        <h2>ProxyIP</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>序号</th><th>地址</th><th>归属地</th><th>更新时间</th></tr>
                </thead>
                <tbody>${generateProxyTableRows(proxyData, updateTime)}</tbody>
            </table>
        </div>
    </div>
    <div id="copy-feedback" class="copy-feedback"></div>
    <script>
        const BASE_DOMAIN = "${BASE_DOMAIN}";
        const preferredDomains = ${JSON.stringify(preferredDomains)};
        const updateTime = "${updateTime}";

        async function fetchWithTimeout(resource, options = {}, timeout = 8000) {
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), timeout);
            const response = fetch(resource, { ...options, signal: controller.signal });
            response.then(() => clearTimeout(id)).catch(() => clearTimeout(id));
            return response;
        }

        async function resolveDomain(domain, recordType) {
            try {
                const response = await fetchWithTimeout(\`https://1.1.1.1/dns-query?name=\${encodeURIComponent(domain)}&type=\${recordType}\`, {
                    headers: { 'Accept': 'application/dns-json' },
                });
                if (!response.ok) return null;
                const data = await response.json();
                if (data.Answer && data.Answer.length > 0) {
                    return data.Answer.map(ans => ans.data);
                }
            } catch (error) {
                console.error(\`DNS query failed for \${domain}:\`, error);
            }
            return null;
        }

        async function getIpLocation(ip) {
            try {
                const targetUrl = \`http://ip-api.com/json/\${ip}?lang=zh-CN&fields=status,message,country\`;
                const proxyUrl = \`https://api.allorigins.win/get?url=\${encodeURIComponent(targetUrl)}\`;
                const response = await fetchWithTimeout(proxyUrl);
                if (!response.ok) return \`代理查询失败(\${response.status})\`;
                const data = await response.json();
                const ipApiData = JSON.parse(data.contents);
                if (ipApiData.status === 'success') return ipApiData.country || '未知';
                return \`查询失败(\${ipApiData.message})\`;
            } catch (error) {
                return '查询超时';
            }
        }

        async function updateRow(prefix) {
            const row = document.getElementById(\`row-\${prefix}\`);
            const locationCell = row.querySelector('.location-cell');
            const fullDomain = \`\${prefix}.\${BASE_DOMAIN}\`;
            
            const isIPv6 = prefix.startsWith('ipv6');
            let ips = await resolveDomain(fullDomain, isIPv6 ? 'AAAA' : 'A');
            if (!ips) {
                ips = await resolveDomain(fullDomain, isIPv6 ? 'A' : 'AAAA');
            }

            if (!ips || ips.length === 0) {
                locationCell.textContent = '解析无记录';
            } else {
                locationCell.textContent = await getIpLocation(ips[0]);
            }
            locationCell.classList.remove('placeholder-text');
        }

        document.addEventListener('DOMContentLoaded', () => {
            preferredDomains.forEach(prefix => updateRow(prefix));

            const container = document.querySelector('.container');
            const feedback = document.getElementById('copy-feedback');
            let feedbackTimeout;
            container.addEventListener('click', (e) => {
                const row = e.target.closest('tr.data-row');
                if (!row) return;
                const address = row.cells[1].textContent.trim();
                if (!address) return;
                navigator.clipboard.writeText(address).then(() => {
                    feedback.textContent = '已复制: ' + address;
                    feedback.classList.add('show');
                    clearTimeout(feedbackTimeout);
                    feedbackTimeout = setTimeout(() => { feedback.classList.remove('show'); }, 2000);
                }).catch(err => { console.error('复制失败: ', err); });
            });
        });
    </script>
</body>
</html>`;
}

function generateProxyTableRows(data, updateTime) {
    return data.map((item, index) => `
        <tr class="data-row">
            <td>${index + 1}</td>
            <td>${item.address}</td>
            <td>${item.location}</td>
            <td>${updateTime}</td>
        </tr>
    `).join('');
}

function generateProxyTableData(prefixList) {
    return prefixList.map(prefix => ({
        address: `${prefix}.${BASE_DOMAIN}`,
        location: proxyPrefixes[prefix] || '未知'
    }));
}

function getUpdateTime() {
    const now = new Date();
    const beijingTime = new Date(now.getTime() + 8 * 3600 * 1000);
    const minutes = beijingTime.getUTCMinutes();
    const roundedMinutes = Math.floor(minutes / 10) * 10;
    beijingTime.setUTCMinutes(roundedMinutes, 0, 0);
    const hours = beijingTime.getUTCHours().toString().padStart(2, '0');
    const finalMinutes = beijingTime.getUTCMinutes().toString().padStart(2, '0');
    return `${hours}:${finalMinutes}`;
}
