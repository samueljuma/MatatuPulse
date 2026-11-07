import { useEffect, useState } from 'react'
import { getAuth } from '../api/client'

export function useAuth() {
  const [auth, setState] = useState(getAuth)
  useEffect(() => {
    const sync = () => setState(getAuth())
    window.addEventListener('mp-auth', sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener('mp-auth', sync)
      window.removeEventListener('storage', sync)
    }
  }, [])
  return auth
}
