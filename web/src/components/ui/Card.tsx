import { type ReactNode } from 'react'
import { motion } from 'framer-motion'

interface CardProps {
  title: string
  subtitle?: string
  children: ReactNode
  className?: string
}

export function Card({ title, subtitle, className = '', children }: CardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={[
        'flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 sm:p-8',
        'shadow-[var(--shadow)] transition-shadow duration-300 hover:shadow-[0_28px_56px_rgba(0,0,0,0.12)]',
        className,
      ].join(' ')}
    >
      <header className="mb-6">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-[var(--text)]">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">{subtitle}</p>
        )}
      </header>
      {children}
    </motion.section>
  )
}
