import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { Textarea } from './ui/Textarea'
import { VideoPreview } from './ui/VideoPreview'
import {
  CryptoError,
  encodeMessage,
  revokeBlobUrl,
  validatePlaintext,
} from '../lib/crypto'

interface EncodePanelProps {
  seed: number
}

export function EncodePanel({ seed }: EncodePanelProps) {
  const [input, setInput] = useState('')
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [meta, setMeta] = useState<{ fingerprint: string; durationSec: number; sizeKb: number } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    return () => revokeBlobUrl(blobUrl)
  }, [blobUrl])

  const handleGenerate = async () => {
    const err = validatePlaintext(input)
    if (err) {
      toast.error(err)
      return
    }

    setLoading(true)
    revokeBlobUrl(blobUrl)
    setBlobUrl(null)
    setMeta(null)

    try {
      const result = await encodeMessage(input, seed)
      setBlobUrl(result.blobUrl)
      setMeta({
        fingerprint: result.fingerprint,
        durationSec: result.durationSec,
        sizeKb: result.sizeKb,
      })
      toast.success('Video generated')
    } catch (e) {
      const message = e instanceof CryptoError ? e.message : 'Generation failed.'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setInput('')
    revokeBlobUrl(blobUrl)
    setBlobUrl(null)
    setMeta(null)
  }

  return (
    <Card
      title="Encode"
      subtitle="Transform your message into an optical video credential"
    >
      <div className="flex flex-col gap-5">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--text-muted)]">
            Message
          </label>
          <Textarea
            rows={3}
            placeholder="Type your message (A–Z)…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={handleGenerate} loading={loading} disabled={!input.trim()}>
            Generate video
          </Button>
          <Button variant="secondary" onClick={handleClear} disabled={loading}>
            Clear
          </Button>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--text-muted)]">
            Preview
          </label>
          <VideoPreview src={blobUrl} />
        </div>

        {blobUrl && (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <a
              href={blobUrl}
              download="phasegrid.mp4"
              className="inline-flex items-center justify-center rounded-xl accent-gradient px-5 py-2.5 text-sm font-medium text-white shadow-lg transition-all hover:brightness-110"
            >
              Download MP4
            </a>
            {meta && (
              <p className="text-xs text-[var(--text-dim)]">
                {meta.durationSec}s · {meta.sizeKb} KB · {meta.fingerprint.slice(0, 12)}…
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
