export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'phasegrid-theme'

export function getStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.remove('light', 'dark')
  root.classList.add(theme)
  localStorage.setItem(STORAGE_KEY, theme)
}

export function initTheme() {
  applyTheme(getStoredTheme())
}
