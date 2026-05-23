import { motion } from 'framer-motion'

interface VideoPreviewProps {
  src: string | null
}

export function VideoPreview({ src }: VideoPreviewProps) {
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
      className="overflow-hidden rounded-xl border border-[var(--border)] bg-black/40 shadow-inner"
    >
      <video
        src={src}
        controls
        className="aspect-video w-full bg-black"
        playsInline
      />
    </motion.div>
  )
}
