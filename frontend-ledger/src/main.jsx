import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './App.css'

const ledgerTheme = {
  token: {
    colorPrimary: '#3498db',
    colorBgLayout: '#f4f6f8',
    colorBgContainer: '#ffffff',
    colorText: '#333333',
    colorTextSecondary: '#666666',
    colorBorder: '#e4e6ea',
    borderRadius: 6,
    fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif",
  },
  components: {
    Card: {
      headerFontSize: 14,
      bodyPadding: 16,
    },
    Table: {
      headerBg: '#f5f6f8',
      rowHoverBg: '#f7fbff',
    },
  },
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={ledgerTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
