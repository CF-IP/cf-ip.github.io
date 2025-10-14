export async function onRequest(context) {
  const { request, waitUntil } = context;
  const url = new URL(request.url);

  const apiPath = url.pathname.replace(/^\/api\//, '');
  if (!apiPath || apiPath === '/') {
    return new Response(JSON.stringify({
      status: 'ok',
      message: 'GitHub API proxy is running.'
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  const targetUrl = `https://api.github.com/${apiPath}`;
  const cache = caches.default;
  
  try {
    let response = await cache.match(targetUrl);

    if (!response) {
      const apiRequest = new Request(targetUrl, {
        headers: {
          'User-Agent': 'Cloudflare-Pages-Function-Proxy/1.0',
          'Accept': 'application/vnd.github.v3+json',
        },
      });

      const apiResponse = await fetch(apiRequest);
      response = new Response(apiResponse.body, {
        status: apiResponse.status,
        statusText: apiResponse.statusText,
        headers: new Headers(apiResponse.headers),
      });

      if (response.ok) {
        response.headers.set('Cache-Control', 's-maxage=3600');
        waitUntil(cache.put(targetUrl, response.clone()));
      }
    }
    
    return response;

  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message || 'Function script encountered an error.'
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
}
