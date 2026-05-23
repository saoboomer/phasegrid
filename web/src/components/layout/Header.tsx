import { ThemeToggle } from './ThemeToggle'

export function Header() {
  return (
    <header className="mb-12 flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
      <div className="max-w-xl">
        <p className="text-sm font-medium text-[var(--text-muted)]">
          Optical credential protocol
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
          Phase<span className="accent-text">Grid</span>
        </h1>
        <p className="mt-4 text-base leading-relaxed text-[var(--text-muted)]">
          Turn a message into a spatio-temporal video signal, then recover it from the recording.
        </p>
      </div>
      <div className="flex shrink-0 items-start">
        <ThemeToggle />
      </div>
    </header>
  )
}
