import { Card, Skeleton, Typography } from 'antd'

export default function StatCard({ title, value, hint, loading }) {
  return (
    <Card className="page-card" size="small" title={title}>
      {loading ? (
        <Skeleton active paragraph={false} />
      ) : (
        <>
          <div className="stat-value">{value}</div>
          {hint ? <Typography.Text type="secondary">{hint}</Typography.Text> : null}
        </>
      )}
    </Card>
  )
}
