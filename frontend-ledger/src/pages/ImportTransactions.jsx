import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Divider,
  message,
  Select,
  Space,
  Statistic,
  Typography,
  Upload,
} from 'antd'
import { DeleteOutlined, EyeOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import {
  commitImport,
  createImportTemplate,
  deleteImportTemplate,
  listAccounts,
  listImportTemplates,
  previewImport,
} from '../api/ledger'
import ImportMappingTable from '../components/ImportMappingTable'
import ImportPreviewTable from '../components/ImportPreviewTable'
import PageHeader from '../components/PageHeader'

const DELIMITER_OPTIONS = [
  { label: '逗号 (,)', value: ',' },
  { label: '制表符 (Tab)', value: '\\t' },
  { label: '分号 (;)', value: ';' },
  { label: '竖线 (|)', value: '|' },
]

export default function ImportTransactions() {
  const navigate = useNavigate()
  const [uploadFile, setUploadFile] = useState(null)
  const [encoding, setEncoding] = useState('utf-8')
  const [delimiter, setDelimiter] = useState(',')
  const [hasHeader, setHasHeader] = useState(true)
  const [applyRules, setApplyRules] = useState(true)

  const [mapping, setMapping] = useState({})
  const [defaults, setDefaults] = useState({
    default_account_id: null,
    default_currency: 'CNY',
    default_transaction_type: null,
    default_direction: null,
  })

  const [accounts, setAccounts] = useState([])
  const [templates, setTemplates] = useState([])
  const [activeTemplateId, setActiveTemplateId] = useState(null)

  const [previewLoading, setPreviewLoading] = useState(false)
  const [commitLoading, setCommitLoading] = useState(false)
  const [previewData, setPreviewData] = useState(null)

  const stats = previewData?.stats || {
    total_rows: 0,
    valid_rows: 0,
    duplicate_rows: 0,
    invalid_rows: 0,
  }

  const canCommit = useMemo(() => {
    if (!previewData?.preview_rows?.length) return false
    return previewData.preview_rows.some((row) => row.status === 'valid' || row.status === 'duplicate')
  }, [previewData])

  const loadMeta = async () => {
    const [accountsRes, templatesRes] = await Promise.all([listAccounts(), listImportTemplates()])
    setAccounts(Array.isArray(accountsRes?.items) ? accountsRes.items : [])
    setTemplates(Array.isArray(templatesRes?.items) ? templatesRes.items : [])
  }

  useEffect(() => {
    loadMeta()
  }, [])

  const handleApplyTemplate = (templateId) => {
    setActiveTemplateId(templateId || null)
    const tpl = templates.find((x) => x.id === templateId)
    if (!tpl) return
    setDelimiter(tpl.delimiter || ',')
    setEncoding(tpl.encoding || 'utf-8')
    setMapping(tpl.mapping || {})
    setApplyRules(tpl.apply_rules !== false)
    message.success(`已应用模板: ${tpl.name}`)
  }

  const handlePreview = async () => {
    if (!uploadFile) {
      message.warning('请先上传 CSV 文件')
      return
    }

    setPreviewLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      formData.append('delimiter', delimiter)
      formData.append('encoding', encoding)
      formData.append('has_header', String(hasHeader))
      formData.append('mapping_json', JSON.stringify(mapping || {}))
      if (defaults.default_account_id) formData.append('default_account_id', String(defaults.default_account_id))
      if (defaults.default_currency) formData.append('default_currency', defaults.default_currency)
      if (defaults.default_transaction_type) formData.append('default_transaction_type', defaults.default_transaction_type)
      if (defaults.default_direction) formData.append('default_direction', defaults.default_direction)
      formData.append('apply_rules', String(applyRules))
      formData.append('preview_limit', '100')

      const data = await previewImport(formData)
      setPreviewData(data)
      message.success('预览完成')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleCommit = async () => {
    if (!previewData?.preview_rows?.length) {
      message.warning('请先完成预览')
      return
    }

    setCommitLoading(true)
    try {
      const payload = await commitImport({
        records: previewData.preview_rows,
        skip_duplicates: true,
        skip_invalid: true,
        apply_rules: applyRules,
        template_id: activeTemplateId || null,
      })
      message.success(
        `导入完成：新增 ${payload.created_count}，跳过重复 ${payload.skipped_duplicate_count}，跳过无效 ${payload.skipped_invalid_count}，失败 ${payload.failed_count}，命中规则 ${payload.rule_hit_rows || 0}`,
      )
      navigate('/transactions?source=import_csv')
    } finally {
      setCommitLoading(false)
    }
  }

  const handleSaveTemplate = async () => {
    const name = window.prompt('请输入模板名称')
    if (!name || !name.trim()) return

    await createImportTemplate({
      name: name.trim(),
      delimiter,
      encoding,
      mapping,
      apply_rules: applyRules,
    })
    await loadMeta()
    message.success('模板保存成功')
  }

  const handleDeleteTemplate = async () => {
    if (!activeTemplateId) {
      message.warning('请先选择模板')
      return
    }
    await deleteImportTemplate(activeTemplateId)
    setActiveTemplateId(null)
    await loadMeta()
    message.success('模板已删除')
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="CSV 导入"
        subtitle="上传 CSV -> 字段映射 -> 预览去重 -> 确认导入"
        extra={
          <Space>
            <Button icon={<SaveOutlined />} onClick={handleSaveTemplate}>保存映射模板</Button>
            <Button icon={<DeleteOutlined />} danger onClick={handleDeleteTemplate}>删除模板</Button>
          </Space>
        }
      />

      <Card className="page-card" title="1. 文件与解析选项">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Upload
            maxCount={1}
            beforeUpload={(file) => {
              setUploadFile(file)
              return false
            }}
            onRemove={() => setUploadFile(null)}
            fileList={uploadFile ? [uploadFile] : []}
          >
            <Button icon={<UploadOutlined />}>选择 CSV 文件</Button>
          </Upload>

          <Space wrap>
            <Select
              value={encoding}
              onChange={setEncoding}
              style={{ width: 160 }}
              options={[
                { label: 'UTF-8', value: 'utf-8' },
                { label: 'GBK', value: 'gbk' },
              ]}
            />
            <Select
              value={delimiter}
              onChange={setDelimiter}
              style={{ width: 160 }}
              options={DELIMITER_OPTIONS}
            />
            <Checkbox checked={hasHeader} onChange={(e) => setHasHeader(e.target.checked)}>
              包含表头
            </Checkbox>
            <Select
              placeholder="套用模板"
              value={activeTemplateId || undefined}
              onChange={handleApplyTemplate}
              style={{ width: 240 }}
              allowClear
              options={(templates || []).map((x) => ({ label: x.name, value: x.id }))}
            />
          </Space>
        </Space>
      </Card>

      <ImportMappingTable
        mapping={mapping}
        onMappingChange={setMapping}
        columns={previewData?.columns || []}
        defaults={defaults}
        onDefaultsChange={setDefaults}
        accounts={accounts}
        applyRules={applyRules}
        onApplyRulesChange={setApplyRules}
      />

      <Card className="page-card">
        <Space>
          <Button type="primary" icon={<EyeOutlined />} loading={previewLoading} onClick={handlePreview}>
            预览导入
          </Button>
          <Button type="primary" loading={commitLoading} disabled={!canCommit} onClick={handleCommit}>
            确认导入
          </Button>
        </Space>

        <Divider />

        <Space size={24} wrap>
          <Statistic title="总行数" value={stats.total_rows} />
          <Statistic title="有效" value={stats.valid_rows} valueStyle={{ color: '#1f8b4c' }} />
          <Statistic title="重复" value={stats.duplicate_rows} valueStyle={{ color: '#d48806' }} />
          <Statistic title="无效" value={stats.invalid_rows} valueStyle={{ color: '#cf1322' }} />
        </Space>

        {!previewData ? (
          <Alert style={{ marginTop: 12 }} type="info" showIcon message="请先上传 CSV 并点击预览导入" />
        ) : null}
      </Card>

      <ImportPreviewTable rows={previewData?.preview_rows || []} loading={previewLoading} />
    </Space>
  )
}
