import { Flex, Space, Typography } from 'antd'

export default function PageHeader({ title, subtitle, extra }) {
  return (
    <Flex align="center" justify="space-between" gap={12} wrap>
      <Space direction="vertical" size={2}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        {subtitle ? <Typography.Text type="secondary">{subtitle}</Typography.Text> : null}
      </Space>
      <Space>{extra}</Space>
    </Flex>
  )
}
