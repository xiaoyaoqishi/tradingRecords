import { useState, useEffect } from 'react';
import {
  Card, Button, Tabs, Form, Input, DatePicker, Select, InputNumber,
  Switch, message, List, Space, Popconfirm, Empty, Modal, Row, Col,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { reviewApi } from '../api';
import dayjs from 'dayjs';

const { TextArea } = Input;

export default function ReviewList() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [activeTab, setActiveTab] = useState('daily');
  const [formType, setFormType] = useState('daily');
  const [form] = Form.useForm();

  useEffect(() => { loadReviews(); }, [activeTab]);

  const loadReviews = async () => {
    setLoading(true);
    try {
      const res = await reviewApi.list({ review_type: activeTab });
      setReviews(res.data);
    } catch { message.error('加载失败'); }
    setLoading(false);
  };

  const openModal = (record = null) => {
    setEditingId(record?.id || null);
    if (record) {
      setFormType(record.review_type);
      form.setFieldsValue({ ...record, review_date: dayjs(record.review_date) });
    } else {
      setFormType(activeTab);
      form.resetFields();
      form.setFieldsValue({ review_type: activeTab, review_date: dayjs() });
    }
    setModalOpen(true);
  };

  const onFinish = async (values) => {
    try {
      const data = { ...values, review_date: values.review_date.format('YYYY-MM-DD') };
      if (editingId) {
        await reviewApi.update(editingId, data);
        message.success('更新成功');
      } else {
        await reviewApi.create(data);
        message.success('创建成功');
      }
      setModalOpen(false);
      loadReviews();
    } catch { message.error('保存失败'); }
  };

  const handleDelete = async (id) => {
    await reviewApi.delete(id);
    message.success('已删除');
    loadReviews();
  };

  const typeLabel = { daily: '日', weekly: '周', monthly: '月' };

  const dailyFields = (
    <>
      <Col span={24}><Form.Item label="今天最赚钱的交易及原因" name="best_trade"><TextArea rows={2} /></Form.Item></Col>
      <Col span={24}><Form.Item label="今天最差的交易及原因" name="worst_trade"><TextArea rows={2} /></Form.Item></Col>
      <Col span={8}><Form.Item label="是否违反纪律" name="discipline_violated" valuePropName="checked"><Switch /></Form.Item></Col>
      <Col span={8}><Form.Item label="亏损可接受" name="loss_acceptable" valuePropName="checked"><Switch /></Form.Item></Col>
      <Col span={8}><Form.Item label="执行质量(1-10)" name="execution_score"><InputNumber min={1} max={10} style={{ width: '100%' }} /></Form.Item></Col>
      <Col span={24}><Form.Item label="明天要避免什么" name="tomorrow_avoid"><TextArea rows={2} /></Form.Item></Col>
    </>
  );

  const weeklyFields = (
    <>
      <Col span={12}><Form.Item label="主要赚钱来源" name="profit_source"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="主要亏损来源" name="loss_source"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="该继续的交易类型" name="continue_trades"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="该减少的交易类型" name="reduce_trades"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="重复出现的错误" name="repeated_errors"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="下周只改一个问题" name="next_focus"><TextArea rows={2} /></Form.Item></Col>
    </>
  );

  const monthlyFields = (
    <>
      <Col span={12}><Form.Item label="盈利来自能力还是运气" name="profit_from_skill"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="真正有优势的策略" name="best_strategy"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="吞噬利润的行为" name="profit_eating_behavior"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="是否调整品种池" name="adjust_symbols"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="是否调整仓位体系" name="adjust_position"><TextArea rows={2} /></Form.Item></Col>
      <Col span={12}><Form.Item label="是否暂停某类模式" name="pause_patterns"><TextArea rows={2} /></Form.Item></Col>
    </>
  );

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><h2 style={{ margin: 0 }}>复盘记录</h2></Col>
        <Col><Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>新建复盘</Button></Col>
      </Row>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        { key: 'daily', label: '日复盘' },
        { key: 'weekly', label: '周复盘' },
        { key: 'monthly', label: '月复盘' },
      ]} />

      <List
        loading={loading}
        dataSource={reviews}
        locale={{ emptyText: <Empty description="暂无复盘记录" /> }}
        renderItem={item => (
          <Card size="small" style={{ marginBottom: 8 }}
            extra={
              <Space>
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openModal(item)} />
                <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                  <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            }>
            <Card.Meta
              title={`${item.review_date} ${typeLabel[item.review_type] || ''}复盘`}
              description={item.summary || item.best_trade || item.profit_source || item.profit_from_skill || '无摘要'}
            />
            {item.execution_score != null && <div style={{ marginTop: 8 }}>执行评分: {item.execution_score}/10</div>}
          </Card>
        )}
      />

      <Modal title={editingId ? '编辑复盘' : '新建复盘'} open={modalOpen} onCancel={() => setModalOpen(false)}
        footer={null} width={800} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="类型" name="review_type" rules={[{ required: true }]}>
                <Select options={[
                  { label: '日复盘', value: 'daily' },
                  { label: '周复盘', value: 'weekly' },
                  { label: '月复盘', value: 'monthly' },
                ]} onChange={v => setFormType(v)} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="日期" name="review_date" rules={[{ required: true }]}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>

            {formType === 'daily' && dailyFields}
            {formType === 'weekly' && weeklyFields}
            {formType === 'monthly' && monthlyFields}

            <Col span={24}><Form.Item label="总结" name="summary"><TextArea rows={3} /></Form.Item></Col>
            <Col span={24}><Form.Item label="详细内容" name="content"><TextArea rows={4} /></Form.Item></Col>
          </Row>
          <Form.Item><Button type="primary" htmlType="submit">保存</Button></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
