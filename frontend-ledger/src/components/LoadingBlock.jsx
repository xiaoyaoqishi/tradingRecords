import { Flex, Spin } from 'antd'

export default function LoadingBlock({ text = '加载中...' }) {
  return (
    <Flex align="center" justify="center" style={{ minHeight: 220 }} vertical gap={12}>
      <Spin size="large" />
      <span>{text}</span>
    </Flex>
  )
}
