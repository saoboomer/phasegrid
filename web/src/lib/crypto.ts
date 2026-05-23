export interface EncodeResult {
  blobUrl: string
  fingerprint: string
  durationSec: number
  sizeKb: number
}

export interface DecodeResult {
  message: string
  fingerprint: string
  charCount: number
  avgConfidence: number
}

export class CryptoError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'CryptoError'
    this.status = status
  }
}

/** Set VITE_API_URL in Vercel (e.g. https://your-api.onrender.com) — leave empty for local dev proxy */
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

const MIN_LOADING_MS = 300

async function withMinDelay<T>(promise: Promise<T>): Promise<T> {
  const [result] = await Promise.all([
    promise,
    new Promise((resolve) => setTimeout(resolve, MIN_LOADING_MS)),
  ])
  return result
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? 'Request failed').join(', ')
    }
  } catch {
  }
  return `Request failed (${res.status})`
}

export async function encodeMessage(text: string, seed = 42): Promise<EncodeResult> {
  return withMinDelay(
    (async () => {
      const res = await fetch(apiUrl('/api/encode'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, seed }),
      })
      if (!res.ok) {
        throw new CryptoError(await parseError(res), res.status)
      }
      const raw = await res.blob()
      const blob =
        raw.type === 'video/mp4'
          ? raw
          : new Blob([await raw.arrayBuffer()], { type: 'video/mp4' })
      const fingerprint = res.headers.get('X-Fingerprint') ?? ''
      const durationSec = parseFloat(res.headers.get('X-Duration-Sec') ?? '0')
      const sizeKb = parseFloat(res.headers.get('X-Size-Kb') ?? '0')
      const blobUrl = URL.createObjectURL(blob)
      return { blobUrl, fingerprint, durationSec, sizeKb }
    })(),
  )
}

export async function decodeVideo(file: File, seed = 42): Promise<DecodeResult> {
  return withMinDelay(
    (async () => {
      const form = new FormData()
      form.append('file', file)
      form.append('seed', String(seed))

      const res = await fetch(apiUrl('/api/decode'), {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        throw new CryptoError(await parseError(res), res.status)
      }
      return res.json() as Promise<DecodeResult>
    })(),
  )
}

const ALPHABET = /^[A-Z ]*$/i

export function validatePlaintext(text: string): string | null {
  if (!text.trim()) return 'Enter a message to encode.'
  const upper = text.toUpperCase()
  const encodable = upper.replace(/[^A-Z]/g, '')
  if (!encodable) return 'Message must contain at least one A–Z character.'
  const invalid = upper.replace(/[A-Z ]/g, '')
  if (invalid.length > 0) {
    const unique = [...new Set(invalid.split(''))].join('')
    return `Unsupported characters: ${unique}. Use A–Z only.`
  }
  if (!ALPHABET.test(text)) return 'Use A–Z characters only.'
  return null
}

export function validateVideoFile(file: File | null): string | null {
  if (!file) return 'Select an MP4 video to decode.'
  if (!file.name.toLowerCase().endsWith('.mp4')) {
    return 'Only .mp4 files are supported.'
  }
  if (file.size > 50 * 1024 * 1024) {
    return 'File too large (max 50 MB).'
  }
  return null
}

export function revokeBlobUrl(url: string | null) {
  if (url) URL.revokeObjectURL(url)
}

export async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text)
}
