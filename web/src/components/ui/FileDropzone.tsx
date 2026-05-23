import { useCallback, useRef, useState } from 'react'

interface FileDropzoneProps {
  file: File | null
  onFile: (file: File | null) => void
  disabled?: boolean
}

export function FileDropzone({ file, onFile, disabled }: FileDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    (f: File | null) => {
      if (!f) {
        onFile(null)
        return
      }
      if (!f.name.toLowerCase().endsWith('.mp4')) return
      onFile(f)
    },
    [onFile],
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      if (disabled) return
      const f = e.dataTransfer.files[0]
      handleFile(f ?? null)
    },
    [disabled, handleFile],
  )

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={[
        'relative cursor-pointer rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all duration-200',
        dragging
          ? 'border-[rgba(124,108,240,0.6)] bg-[rgba(124,108,240,0.08)]'
          : 'border-[var(--border)] bg-[var(--input-bg)] hover:border-[rgba(124,108,240,0.35)]',
        disabled && 'cursor-not-allowed opacity-50',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,.mp4"
        className="hidden"
        disabled={disabled}
        onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
      />
      {file ? (
        <div>
          <p className="text-sm font-medium text-[var(--text)]">{file.name}</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">{formatSize(file.size)}</p>
          <p className="mt-3 text-xs text-[var(--text-dim)]">Click or drop to replace</p>
        </div>
      ) : (
        <div>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--surface-elevated)]">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[var(--text-muted)]">
              <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 20h16" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <p className="text-sm font-medium text-[var(--text)]">Drop your MP4 here</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">or click to browse</p>
        </div>
      )}
    </div>
  )
}
