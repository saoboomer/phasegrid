import LetterGlitch from '../LetterGlitch/LetterGlitch'

/** Turquoise, cyan, red, yellow, purple — no white */
const GLITCH_COLORS = [
  '#0D9488',
  '#14B8A6',
  '#2DD4BF',
  '#06B6D4',
  '#22D3EE',
  '#EF4444',
  '#DC2626',
  '#FB7185',
  '#FBBF24',
  '#F59E0B',
  '#A855F7',
  '#8B5CF6',
  '#C084FC',
]

export function Background() {
  return (
    <div
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[var(--bg)]"
      aria-hidden
    >
      <LetterGlitch
        className="h-full w-full"
        glitchColors={GLITCH_COLORS}
        glitchSpeed={45}
        centerVignette
        outerVignette
        smooth
        characters="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
      />
    </div>
  )
}
