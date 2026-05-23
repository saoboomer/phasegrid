import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { toast } from 'sonner'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { FileDropzone } from './ui/FileDropzone'
import {
  copyToClipboard,
  CryptoError,
  decodeVideo,
  validateVideoFile,
} from '../lib/crypto'

interface DecodePanelProps {
  seed: number
}

export function DecodePanel({ seed }: DecodePanelProps) {
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  const [meta, setMeta] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleDecode = async () => {
    const err = validateVideoFile(file)
    if (err) {
      toast.error(err)
      return
    }

    setLoading(true)
    setMessage('')
    setMeta(null)

    try {
      const result = await decodeVideo(file!, seed)
      setMessage(result.message)
      setMeta(
        `${result.charCount} characters · ${(result.avgConfidence * 100).toFixed(0)}% avg confidence`,
      )
      toast.success('Message decoded')
    } catch (e) {
      const msg = e instanceof CryptoError ? e.message : 'Decoding failed.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!message) return
    try {
      await copyToClipboard(message)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Copy failed')
    }
  }

  const handleClear = () => {
    setFile(null)
    setMessage('')
    setMeta(null)
  }

  return (
    <Card
      title="Decode"
      subtitle="Upload your PhaseGrid video to recover the original message"
    >
      <div className="flex flex-col gap-5">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--text-muted)]">
            Video file
          </label>
          <FileDropzone file={file} onFile={setFile} disabled={loading} />
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={handleDecode} loading={loading} disabled={!file}>
            Decode message
          </Button>
          <Button variant="secondary" onClick={handleClear} disabled={loading}>
            Clear
          </Button>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--text-muted)]">
            Decoded message
          </label>
          <div className="relative min-h-[120px] rounded-xl border border-[var(--border)] bg-[var(--input-bg)] px-5 py-6">
            <AnimatePresence mode="wait">
              {message ? (
                <motion.div
                  key={message}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="pr-20"
                >
                  <p className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-[var(--text)] sm:text-4xl">
                    {message}
                  </p>
                  {meta && (
                    <p className="mt-3 text-xs text-[var(--text-dim)]">{meta}</p>
                  )}
                </motion.div>
              ) : (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-[var(--text-dim)]"
                >
                  Your recovered message will appear here
                </motion.p>
              )}
            </AnimatePresence>
            {message && (
              <Button
                variant="ghost"
                onClick={handleCopy}
                className="absolute right-3 top-3 !px-3 !py-1.5 text-xs"
              >
                Copy
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
