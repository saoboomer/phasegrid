import { type ButtonHTMLAttributes, forwardRef } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
}

const variants: Record<Variant, string> = {
  primary:
    'accent-gradient text-white shadow-lg shadow-[rgba(124,108,240,0.25)] hover:brightness-110 hover:shadow-xl',
  secondary:
    'bg-[var(--surface-elevated)] border border-[var(--border)] text-[var(--text)] hover:border-[rgba(124,108,240,0.35)]',
  ghost:
    'bg-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface)]',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', loading, disabled, className = '', children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={[
        'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium',
        'transition-all duration-200 ease-out',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      ].join(' ')}
      {...props}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  ),
)

Button.displayName = 'Button'
