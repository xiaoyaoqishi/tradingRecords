import { useEffect, useMemo, useState } from 'react';
import { Card, Col, Empty, Row, Spin, Typography } from 'antd';
import dayjs from 'dayjs';
import { tradeApi } from '../api';
import './Dashboard.css';
import AnalyticsFilterBar from '../features/trading/analytics/AnalyticsFilterBar';
import OverviewKpis from '../features/trading/analytics/OverviewKpis';
import TimeSeriesPanel from '../features/trading/analytics/TimeSeriesPanel';
import DimensionPanel from '../features/trading/analytics/DimensionPanel';
import StructuredReviewPanels from '../features/trading/analytics/StructuredReviewPanels';
import BehaviorPanels from '../features/trading/analytics/BehaviorPanels';
import CoverageAndPositions from '../features/trading/analytics/CoverageAndPositions';
import { formatSymbolDimensionKey } from '../features/trading/display';

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});
  const [sourceOptions, setSourceOptions] = useState([]);

  useEffect(() => {
    setLoading(true);
    tradeApi.analytics(filters)
      .then((res) => setAnalytics(res.data || null))
      .catch(() => setAnalytics(null))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    tradeApi.sources()
      .then((res) => setSourceOptions((res.data?.items || []).map((v) => ({ label: v, value: v }))))
      .catch(() => setSourceOptions([]));
  }, []);

  const parseCsv = (v) => String(v || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

  const filterValues = useMemo(() => {
    const hasDate = filters.date_from && filters.date_to;
    return {
      dateRange: hasDate ? [dayjs(filters.date_from), dayjs(filters.date_to)] : null,
      symbols: parseCsv(filters.symbol),
      sources: parseCsv(filters.source_keyword),
    };
  }, [filters]);

  const symbolOptions = useMemo(() => {
    const rows = analytics?.dimensions?.by_symbol || [];
    return rows
      .map((row) => {
        const key = String(row?.key || '').trim();
        if (!key) return null;
        return {
          value: key,
          label: formatSymbolDimensionKey(key),
        };
      })
      .filter(Boolean);
  }, [analytics]);

  const setDateRange = (dates) => {
    setFilters((prev) => {
      if (dates) {
        return { ...prev, date_from: dates[0].format('YYYY-MM-DD'), date_to: dates[1].format('YYYY-MM-DD') };
      }
      const { date_from, date_to, ...rest } = prev;
      return rest;
    });
  };

  const setSymbol = (values) => {
    setFilters((prev) => {
      if (!values || values.length === 0) {
        const { symbol, ...rest } = prev;
        return rest;
      }
      return { ...prev, symbol: values.join(',') };
    });
  };

  const setSource = (values) => {
    setFilters((prev) => {
      if (!values || values.length === 0) {
        const { source_keyword, ...rest } = prev;
        return rest;
      }
      return { ...prev, source_keyword: values.join(',') };
    });
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!analytics) return <Empty description="暂无数据" />;

  const overview = analytics.overview || {};
  const dimensions = analytics.dimensions || {};
  const behavior = analytics.behavior || {};
  const coverage = analytics.coverage || {};
  const positions = analytics.positions || {};
  const timeSeries = analytics.time_series || {};

  return (
    <div className="analytics-workspace">
      <div className="analytics-header">
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            交易分析工作台
          </Typography.Title>
          <Typography.Text type="secondary">
            多维复盘视角：收益、来源、结构化复盘、行为质量与数据覆盖率。
          </Typography.Text>
        </div>
      </div>

      <AnalyticsFilterBar
        symbolOptions={symbolOptions}
        sourceOptions={sourceOptions}
        filterValues={filterValues}
        onSetDateRange={setDateRange}
        onSetSymbol={setSymbol}
        onSetSource={setSource}
      />

      <OverviewKpis overview={overview} />

      <TimeSeriesPanel series={timeSeries} />

      <Row gutter={[12, 12]}>
        <Col xs={24} xl={12}>
          <DimensionPanel
            title="品种维度"
            rows={dimensions.by_symbol || []}
            keyLabel="品种"
            valueFormatter={formatSymbolDimensionKey}
            tablePageSize={5}
            pageSizeOptions={[5, 10, 20, 50, 100]}
          />
        </Col>
        <Col xs={24} xl={12}>
          <DimensionPanel title="来源维度" rows={dimensions.by_source || []} keyLabel="来源" />
        </Col>
      </Row>

      <StructuredReviewPanels byReviewField={dimensions.by_review_field || {}} />

      <BehaviorPanels behavior={behavior} />

      <CoverageAndPositions coverage={coverage} positions={positions} />

      <Card size="small" title="口径说明">
        <div className="analytics-note-list">
          <div>1. 结构化复盘分类字段的标准键保持英文，界面统一显示中文标签。</div>
          <div>2. 来源展示优先使用来源元数据，旧备注仅作兼容回退。</div>
          <div>3. 本页不改变粘贴导入、平仓匹配、统计/持仓业务语义。</div>
        </div>
      </Card>
    </div>
  );
}
