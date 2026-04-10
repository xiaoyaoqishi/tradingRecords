import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Popconfirm, Segmented, Space, Table, Tag, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { brokerApi } from '../api';

export default function InfoMaintain() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [moduleKey, setModuleKey] = useState('broker');
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const res = await brokerApi.list();
      setRows(res.data || []);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    form.setFieldsValue({
      name: row.name || '',
      account: row.account || '',
      password: row.password || '',
      extra_info: row.extra_info || '',
      notes: row.notes || '',
    });
    setOpen(true);
  };

  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await brokerApi.update(editing.id, values);
        message.success('已更新');
      } else {
        await brokerApi.create(values);
        message.success('已创建');
      }
      setOpen(false);
      load();
    } catch (e) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  const remove = async (id) => {
    try {
      await brokerApi.delete(id);
      message.success('已删除');
      load();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', width: 160 },
    { title: '账号', dataIndex: 'account', width: 180, render: (v) => v || '-' },
    {
      title: '密码',
      dataIndex: 'password',
      width: 120,
      render: (v) => (v ? <Tag>已设置</Tag> : '-'),
    },
    { title: '其他信息', dataIndex: 'extra_info', render: (v) => v || '-' },
    { title: '备注', dataIndex: 'notes', render: (v) => v || '-' },
    {
      title: '操作',
      width: 150,
      render: (_, row) => (
        <Space>
          <Button type="link" size="small" onClick={() => openEdit(row)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => remove(row.id)}>
            <Button type="link" danger size="small">删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>信息维护</h2>
        <Segmented
          value={moduleKey}
          onChange={setModuleKey}
          options={[
            { label: '券商信息', value: 'broker' },
          ]}
        />
      </div>

      {moduleKey === 'broker' && (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增券商信息</Button>
          </div>
          <Table rowKey="id" loading={loading} dataSource={rows} columns={columns} pagination={false} />
        </Card>
      )}

      <Modal
        title={editing ? '编辑券商信息' : '新增券商信息'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：宏源期货" />
          </Form.Item>
          <Form.Item label="账号" name="account">
            <Input placeholder="账号/客户号" />
          </Form.Item>
          <Form.Item label="密码" name="password">
            <Input.Password placeholder="可留空" />
          </Form.Item>
          <Form.Item label="其他信息" name="extra_info">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="例如：APP、资金账号、风控限制等" />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
