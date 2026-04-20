import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { trackPageView } from '../api/audit'

export default function useAuditPageView() {
  const location = useLocation()

  useEffect(() => {
    const path = `/ledger${location.pathname === '/' ? '/' : location.pathname}`
    trackPageView({
      path,
      module: 'ledger',
      detail: 'page view',
    }).catch(() => {})
  }, [location.pathname])
}
