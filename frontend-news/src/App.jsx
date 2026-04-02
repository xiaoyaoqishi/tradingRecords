import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Card, List, Popconfirm, Progress, Space, Tag, Typography, message } from 'antd';
import { DeleteOutlined, FolderOpenOutlined, FolderOutlined, GlobalOutlined, ReadOutlined, ReloadOutlined, SyncOutlined, TranslationOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { newsApi } from './api';

const { Title, Text, Paragraph, Link } = Typography;

function statusTag(status) {
  const map = {
    downloaded: { color: 'blue', text: '已同步' },
    translating: { color: 'gold', text: '翻译中' },
    translated: { color: 'green', text: '已翻译' },
    failed: { color: 'red', text: '失败' },
  };
  return map[status] || { color: 'default', text: status || '未知' };
}

export default function App() {
  const [moduleKey, setModuleKey] = useState('economist');

  const [loading, setLoading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [items, setItems] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [progress, setProgress] = useState({ status: 'idle', done: 0, total: 0, percent: 0, message: '未开始' });
  const [lastError, setLastError] = useState('');

  const [todayLoading, setTodayLoading] = useState(false);
  const [todayData, setTodayData] = useState({ updated_at: null, categories: [] });

  const pollRef = useRef(null);
  const active = useMemo(() => items.find(i => i.id === activeId) || null, [items, activeId]);

  const loadList = async () => {
    setLoading(true);
    try {
      const res = await newsApi.list();
      const list = res.data || [];
      setItems(list);
      if (!activeId && list.length) setActiveId(list[0].id);
      if (activeId && !list.find(x => x.id === activeId)) setActiveId(list[0]?.id || null);
    } catch (e) {
      message.error(e.response?.data?.detail || '获取期刊列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (id) => {
    if (!id) {
      setDetail(null);
      return;
    }
    try {
      const res = await newsApi.get(id);
      setDetail(res.data);
    } catch (e) {
      message.error(e.response?.data?.detail || '获取详情失败');
    }
  };

  const pullProgress = async (id) => {
    if (!id) return;
    try {
      const res = await newsApi.progress(id);
      setProgress(res.data);
      if (res.data.status === 'translated') {
        setTranslating(false);
        clearInterval(pollRef.current);
        pollRef.current = null;
        await loadDetail(id);
        await loadList();
        message.success('翻译完成');
      }
      if (res.data.status === 'failed') {
        setTranslating(false);
        clearInterval(pollRef.current);
        pollRef.current = null;
        setLastError(res.data.message || '翻译失败');
      }
    } catch {
      // ignore
    }
  };

  const loadTodayNews = async (force = false) => {
    setTodayLoading(true);
    try {
      const res = await newsApi.today({ force_refresh: force, limit: 8 });
      setTodayData(res.data || { updated_at: null, categories: [] });
    } catch (e) {
      message.error(e.response?.data?.detail || '获取今日新闻失败');
    } finally {
      setTodayLoading(false);
    }
  };

  useEffect(() => { loadList(); }, []);
  useEffect(() => { loadDetail(activeId); pullProgress(activeId); }, [activeId]);
  useEffect(() => { if (moduleKey === 'today') loadTodayNews(false); }, [moduleKey]);
  useEffect(() => () => pollRef.current && clearInterval(pollRef.current), []);

  const handleSync = async () => {
    setLoading(true);
    setLastError('');
    try {
      const res = await newsApi.sync();
      await loadList();
      setActiveId(res.data.id);
      message.success('已同步最新一期');
    } catch (e) {
      const msg = e.response?.data?.detail || '同步失败';
      setLastError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleTranslate = async () => {
    if (!active) return;
    setTranslating(true);
    setLastError('');
    setProgress({ status: 'translating', done: 0, total: 0, percent: 0, message: '开始翻译...' });

    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => pullProgress(active.id), 1200);

    try {
      await newsApi.translate(active.id);
      await pullProgress(active.id);
    } catch (e) {
      const msg = e.response?.data?.detail || '翻译失败';
      setLastError(msg);
      setTranslating(false);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      await pullProgress(active.id);
      message.error(msg);
    }
  };

  const handleDeleteIssue = async (id) => {
    try {
      await newsApi.remove(id);
      if (activeId === id) {
        setActiveId(null);
        setDetail(null);
      }
      await loadList();
      message.success('已删除该期 Economist 文章');
    } catch (e) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  return (
    <div className="news-page">
      <header className="news-header">
        <a href="/" className="back-link">← 返回工作台</a>
        <Title level={3} style={{ margin: '8px 0 0' }}>新闻实事</Title>
      </header>

      <div className="two-col-layout">
        <aside className="left-panel">
          <div className="folder-title">📁 子模块</div>
          <div className={`folder-item ${moduleKey === 'economist' ? 'active' : ''}`} onClick={() => setModuleKey('economist')}>
            {moduleKey === 'economist' ? <FolderOpenOutlined /> : <FolderOutlined />} Economist
          </div>
          <div className={`folder-item ${moduleKey === 'today' ? 'active' : ''}`} onClick={() => setModuleKey('today')}>
            {moduleKey === 'today' ? <FolderOpenOutlined /> : <FolderOutlined />} 今日新闻
          </div>

          {moduleKey === 'economist' && (
            <div className="sub-folder-box">
              <div className="sub-folder-header">📂 Economist / 期刊文件夹</div>
              <List
                loading={loading}
                dataSource={items}
                locale={{ emptyText: '暂无期刊，点击右侧“同步最新一期”' }}
                renderItem={(item) => {
                  const st = statusTag(item.status);
                  return (
                    <List.Item className={`issue-row ${activeId === item.id ? 'active' : ''}`} onClick={() => setActiveId(item.id)}>
                      <div className="issue-row-left">
                        <div className="issue-name">📄 {item.issue_date || '无日期'} / {item.title}</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>{dayjs(item.updated_at).format('YYYY-MM-DD HH:mm')}</Text>
                      </div>
                      <Space>
                        <Tag color={st.color}>{st.text}</Tag>
                        <Popconfirm title="删除这期文章？" description="会同时删除本地下载文件" onConfirm={() => handleDeleteIssue(item.id)}>
                          <DeleteOutlined className="issue-delete" onClick={(e) => e.stopPropagation()} />
                        </Popconfirm>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            </div>
          )}
        </aside>

        <main className="right-panel">
          {moduleKey === 'economist' && (
            <>
              <div className="toolbar">
                <Space>
                  <Button icon={<SyncOutlined />} onClick={handleSync} loading={loading}>同步最新一期</Button>
                  <Button type="primary" icon={<TranslationOutlined />} onClick={handleTranslate} disabled={!active || translating} loading={translating}>翻译当前期</Button>
                </Space>
              </div>

              {(translating || progress.status === 'translating' || progress.status === 'failed' || lastError) && (
                <Card className="progress-card">
                  <Space direction="vertical" style={{ width: '100%' }} size={8}>
                    <div className="progress-line">
                      <Text strong>翻译进度</Text>
                      <Text type="secondary">{progress.message || '处理中...'}</Text>
                    </div>
                    <Progress percent={Number(progress.percent || 0)} status={progress.status === 'failed' ? 'exception' : 'active'} />
                    {lastError && <Alert type="error" showIcon message={lastError} />}
                  </Space>
                </Card>
              )}

              <Card title={detail?.title || '信息区'} extra={detail?.status ? <Tag color={statusTag(detail.status).color}>{statusTag(detail.status).text}</Tag> : null}>
                {!detail ? (
                  <div className="empty-reader"><ReadOutlined /> 左侧选择一期后查看内容</div>
                ) : (
                  <div className="reader-content">
                    <Paragraph type="secondary" style={{ marginTop: 0 }}>来源：{detail.source_repo} / {detail.source_path}</Paragraph>
                    <Paragraph className="reader-text">{detail.content_zh || detail.content_en || '该期暂无内容'}</Paragraph>
                  </div>
                )}
              </Card>
            </>
          )}

          {moduleKey === 'today' && (
            <>
              <div className="toolbar">
                <Space>
                  <Button icon={<ReloadOutlined />} onClick={() => loadTodayNews(true)} loading={todayLoading}>刷新今日新闻</Button>
                  <Tag color="geekblue">仅展示有出处的新闻</Tag>
                </Space>
                <Text type="secondary">更新时间：{todayData.updated_at ? dayjs(todayData.updated_at).format('YYYY-MM-DD HH:mm:ss') : '—'}</Text>
              </div>

              {(todayData.categories || []).map((cat) => (
                <Card key={cat.name} title={`📁 ${cat.name}`} style={{ marginBottom: 12 }}>
                  <List
                    dataSource={cat.items || []}
                    locale={{ emptyText: '暂无来源数据' }}
                    renderItem={(it) => (
                      <List.Item>
                        <Space direction="vertical" size={4} style={{ width: '100%' }}>
                          <Link href={it.url} target="_blank" rel="noreferrer">{it.title}</Link>
                          <Space size={8} wrap>
                            <Tag icon={<GlobalOutlined />} color="blue">{it.source}</Tag>
                            {it.published_at && <Tag>{dayjs(it.published_at).format('MM-DD HH:mm')}</Tag>}
                          </Space>
                          {it.summary && <Text type="secondary">{it.summary}</Text>}
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>
              ))}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
