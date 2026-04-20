import { lazy, Suspense } from 'react'
import { Alert } from 'antd'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import IconSidebar from './components/IconSidebar'
import LoadingBlock from './components/LoadingBlock'
import useAuthGuard from './hooks/useAuthGuard'
import useAuditPageView from './hooks/useAuditPageView'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Transactions = lazy(() => import('./pages/Transactions'))
const ImportTransactions = lazy(() => import('./pages/ImportTransactions'))
const Rules = lazy(() => import('./pages/Rules'))
const Accounts = lazy(() => import('./pages/Accounts'))
const Categories = lazy(() => import('./pages/Categories'))

function AppLayout() {
  useAuditPageView()

  return (
    <div className="ledger-layout">
      <IconSidebar />
      <div className="ledger-content-wrap">
        <Suspense fallback={<LoadingBlock text="页面加载中..." />}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/import" element={<ImportTransactions />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/categories" element={<Categories />} />
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
