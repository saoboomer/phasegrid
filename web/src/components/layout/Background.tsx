import ColorBends from '../ColorBends/ColorBends'

/** Turquoise, white, red, with hints of yellow and purple — wider bands */
const PHASEGRID_COLORS = [
  '#2DD4BF',
  '#14B8A6',
  '#FFFFFF',
  '#F8FAFC',
  '#EF4444',
  '#DC2626',
  '#FBBF24',
  '#A855F7',
]

export function Background() {
  return (
    <div
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      aria-hidden
    >
      <div className="absolute inset-0 bg-[var(--bg)]/85" />
      <div className="absolute inset-0 opacity-90">
        <ColorBends
          rotation={90}
          speed={0.2}
          colors={PHASEGRID_COLORS}
          transparent
          autoRotate={0.15}
          scale={1}
          frequency={1}
          warpStrength={1}
          mouseInfluence={1}
          parallax={0.5}
          noise={0.15}
          iterations={1}
          intensity={1.5}
          bandWidth={11}
        />
      </div>
    </div>
  )
}
