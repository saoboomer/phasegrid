import { useState } from 'react'
import { Toaster } from 'sonner'
import { Container } from './components/layout/Container'
import { Header } from './components/layout/Header'
import { EncodePanel } from './components/EncodePanel'
import { DecodePanel } from './components/DecodePanel'

const DEFAULT_SEED = 42

function App() {
  const [seed, setSeed] = useState(DEFAULT_SEED)
  const [showAdvanced, setShowAdvanced] = useState(false)

  return (
    <>
      <Toaster
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              'font-sans !bg-[var(--surface)] !text-[var(--text)] !border !border-[var(--border)]',
          },
        }}
      />
      <div className="min-h-svh">
        <Container>
          <Header />

          <div className="mb-8">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              {showAdvanced ? 'Hide' : 'Show'} advanced options
            </button>
            {showAdvanced && (
              <div className="mt-4 flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
                <label className="text-sm text-[var(--text-muted)]">Codebook seed</label>
                <input
                  type="number"
                  min={0}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value) || DEFAULT_SEED)}
                  className="w-24 rounded-lg border border-[var(--border)] bg-[var(--input-bg)] px-3 py-1.5 text-sm text-[var(--text)] focus:border-[rgba(124,108,240,0.5)] focus:outline-none focus:ring-2 focus:ring-[rgba(124,108,240,0.15)]"
                />
              </div>
            )}
          </div>

          <div className="grid gap-8 lg:grid-cols-2">
            <EncodePanel seed={seed} />
            <DecodePanel seed={seed} />
          </div>

          <footer className="mt-20 border-t border-[var(--border)] pt-10 text-center">
            <p className="text-sm text-[var(--text-dim)]">
              PhaseGrid v0.3 — deterministic optical credentials
            </p>
          </footer>
        </Container>
      </div>
    </>
  )
}

export default App
