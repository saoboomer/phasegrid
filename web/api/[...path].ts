/**
 * Proxies /api/* to the Python backend (Render, Railway, etc.).
 * Set PHASEGRID_API_URL in Vercel → Settings → Environment Variables.
 */
export const config = {
  runtime: 'edge',
}

const DEFAULT_API = 'https://phasegrid-api.onrender.com'

function backendBase(): string {
  return (
    process.env.PHASEGRID_API_URL ||
    process.env.VITE_API_URL ||
    DEFAULT_API
  ).replace(/\/$/, '')
}

export default async function handler(request: Request): Promise<Response> {
  const incoming = new URL(request.url)
  const target = `${backendBase()}${incoming.pathname}${incoming.search}`

  const headers = new Headers(request.headers)
  headers.delete('host')

  let body: BodyInit | undefined
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    body = await request.arrayBuffer()
  }

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
    })

    if (upstream.status === 404) {
      return Response.json(
        {
          detail:
            'API backend not found (404). Deploy the Python API on Render using render.yaml, ' +
            'then set PHASEGRID_API_URL in Vercel to that URL (e.g. https://phasegrid-api.onrender.com).',
        },
        { status: 502, headers: { 'Content-Type': 'application/json' } },
      )
    }

    const outHeaders = new Headers(upstream.headers)
    outHeaders.set('Access-Control-Allow-Origin', '*')
    outHeaders.set(
      'Access-Control-Expose-Headers',
      'X-Fingerprint, X-Duration-Sec, X-Size-Kb, X-Video-Codec, Content-Type',
    )

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: outHeaders,
    })
  } catch {
    return Response.json(
      {
        detail:
          'Cannot reach the API server. Deploy it on Render (see README) and set PHASEGRID_API_URL in Vercel.',
      },
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    )
  }
}
