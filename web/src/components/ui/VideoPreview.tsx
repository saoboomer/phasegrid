import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface VideoPreviewProps {
  src: string | null
}

export function VideoPreview({ src }: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    setError(false)
    if (videoRef.current && src) {
      videoRef.current.load()
    }
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
      className="overflow-hidden rounded-xl border border-[var(--border)] bg-black shadow-inner"
    >
      {error ? (
        <div className="flex aspect-video flex-col items-center justify-center gap-2 px-4 text-center">
          <p className="text-sm text-[var(--text-muted)]">
            Preview unavailable in this browser.
          </p>
          <p className="text-xs text-[var(--text-dim)]">
            Use Download MP4 below — decoding from the file still works.
          </p>
        </div>
      ) : (
        <video
          ref={videoRef}
          controls
          playsInline
          preload="metadata"
          className="aspect-video w-full max-h-[420px] bg-black object-contain"
          onError={() => setError(true)}
        >
          <source src={src} type="video/mp4" />
        </video>
      )}
    </motion.div>
  )
}
