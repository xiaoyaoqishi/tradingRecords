import { useEffect, useState } from 'react'
import { check } from '../api/auth'

export default function useAuthGuard() {
  const [checking, setChecking] = useState(true)
  const [user, setUser] = useState(null)

  useEffect(() => {
    let mounted = true
    const run = async () => {
      try {
        const data = await check()
        if (!mounted) return
        if (!data?.authenticated) {
          const redirect = encodeURIComponent(window.location.pathname + window.location.search)
          window.location.href = `/login?redirect=${redirect}`
          return
        }
        setUser(data)
      } catch (_) {
        if (!mounted) return
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      } finally {
        if (mounted) setChecking(false)
      }
    }
    run()
    return () => {
      mounted = false
    }
  }, [])

  return { checking, user }
}
