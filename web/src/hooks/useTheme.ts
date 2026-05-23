import { useCallback, useEffect, useState } from 'react'
import { applyTheme, getStoredTheme, type Theme } from '../lib/theme'

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme())

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const toggle = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
  }, [])

  return { theme, toggle, setTheme }
}
