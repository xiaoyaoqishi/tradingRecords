import { Empty } from 'antd'

export default function EmptyBlock({ description = '暂无数据' }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />
}
