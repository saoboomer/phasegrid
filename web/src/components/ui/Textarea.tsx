import { forwardRef, type TextareaHTMLAttributes } from 'react'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = '', ...props }, ref) => (
    <textarea
      ref={ref}
      className={[
        'w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--input-bg)]',
        'px-4 py-3 text-sm leading-relaxed text-[var(--text)]',
        'placeholder:text-[var(--text-dim)]',
        'transition-all duration-200',
        'focus:border-[rgba(124,108,240,0.5)] focus:shadow-[0_0_0_3px_rgba(124,108,240,0.15)] focus:outline-none',
        className,
      ].join(' ')}
      {...props}
    />
  ),
)

Textarea.displayName = 'Textarea'
