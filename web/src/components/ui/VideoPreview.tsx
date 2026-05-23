import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface VideoPreviewProps {
  src: string | null
}

export function VideoPreview({ src }: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setError(false)
    setReady(false)
    const el = videoRef.current
    if (!el || !src) return
    el.src = src
    el.load()
  }, [src])

  if (!src) {
    return (
      <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--input-bg)]">
        <p className="text-sm text-[var(--text-dim)]">Your encoded video will appear here</p>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35 }}
      className="relative aspect-video w-full overflow-hidden rounded-xl border border-[var(--border)] bg-black shadow-inner"
    >
      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
          <p className="text-sm text-[var(--text-muted)]">Could not play this video in the browser.</p>
          <p className="text-xs text-[var(--text-dim)]">
            Run <code className="text-[var(--text)]">pip install -r requirements.txt</code> from the
            repo root, restart the API, then try again.
          </p>
        </div>
      ) : (
        <>
          {!ready && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="h-8 w-8 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            </div>
          )}
          <video
            key={src}
            ref={videoRef}
            src={src}
            controls
            playsInline
            muted
            preload="auto"
            className="h-full w-full object-contain"
            onLoadedData={() => setReady(true)}
            onCanPlay={() => setReady(true)}
            onError={() => setError(true)}
          />
        </>
      )}
    </motion.div>
  )
}
