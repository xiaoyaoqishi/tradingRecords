import { Button, Space, Upload } from 'antd'
import { ReloadOutlined, UploadOutlined } from '@ant-design/icons'

export default function BatchToolbar({ loading, onRefresh, onUpload }) {
  return (
    <Space wrap>
      <Upload
        accept=".csv,.xls,.xlsx"
        maxCount={1}
        showUploadList={false}
        beforeUpload={(file) => {
          onUpload?.(file)
          return false
        }}
      >
        <Button type="primary" icon={<UploadOutlined />} loading={loading}>
          上传流水文件
        </Button>
      </Upload>
      <Button icon={<ReloadOutlined />} onClick={onRefresh} loading={loading}>
        刷新批次
      </Button>
    </Space>
  )
}
