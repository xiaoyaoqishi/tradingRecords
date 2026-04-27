import { lazy, Suspense } from 'react'
import { Alert } from 'antd'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import IconSidebar from './components/IconSidebar'
import LoadingBlock from './components/LoadingBlock'
import useAuthGuard from './hooks/useAuthGuard'
import useAuditPageView from './hooks/useAuditPageView'

const ImportBatchesPage = lazy(() => import('./pages/ImportBatchesPage'))
const ImportReviewPage = lazy(() => import('./pages/ImportReviewPage'))
const MerchantDictionaryPage = lazy(() => import('./pages/MerchantDictionaryPage'))
const RulesPage = lazy(() => import('./pages/Rules'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))

function AppLayout() {
  useAuditPageView()

  return (
    <div className="ledger-layout">
      <IconSidebar />
      <div className="ledger-content-wrap">
        <Suspense fallback={<LoadingBlock text="页面加载中..." />}>
          <Routes>
            <Route path="/" element={<Navigate to="/imports" replace />} />
            <Route path="/imports" element={<ImportBatchesPage />} />
            <Route path="/imports/:batchId/review" element={<ImportReviewPage />} />
            <Route path="/merchants" element={<MerchantDictionaryPage />} />
            <Route path="/rules" element={<RulesPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="*" element={<Alert type="warning" showIcon message="页面不存在" />} />
          </Routes>
        </Suspense>
      </div>
    </div>
  )
}

export default function App() {
  const { checking, user } = useAuthGuard()

  if (checking) {
    return <LoadingBlock text="正在校验登录状态..." />
  }

  if (!user) {
    return null
  }

  return (
    <BrowserRouter basename="/ledger">
      <AppLayout />
    </BrowserRouter>
  )
}
