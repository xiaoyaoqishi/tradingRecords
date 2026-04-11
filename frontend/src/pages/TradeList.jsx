import { Card } from 'antd';
import { useNavigate } from 'react-router-dom';
import './TradeList.css';
import TradeWorkspaceHeader from '../features/trading/workspace/TradeWorkspaceHeader';
import TradeWorkspaceFilterBar from '../features/trading/workspace/TradeWorkspaceFilterBar';
import TradeFillsTable from '../features/trading/workspace/TradeFillsTable';
import TradePositionsTable from '../features/trading/workspace/TradePositionsTable';
import TradeDetailDrawer from '../features/trading/workspace/TradeDetailDrawer';
import TradeImportModal from '../features/trading/workspace/TradeImportModal';
import TradeBatchEditModal from '../features/trading/workspace/TradeBatchEditModal';
import TradeBatchStructuredReviewModal from '../features/trading/workspace/TradeBatchStructuredReviewModal';
import { useTradeWorkspace } from '../features/trading/workspace/useTradeWorkspace';

export default function TradeList() {
  const navigate = useNavigate();
  const ws = useTradeWorkspace();

  return (
    <div className="trade-workspace">
      <TradeWorkspaceHeader onOpenImport={ws.openImportModal} onCreateTrade={() => navigate('/trades/new')} />

      <TradeWorkspaceFilterBar
        viewMode={ws.viewMode}
        setViewMode={ws.setViewMode}
        selectedRowKeys={ws.selectedRowKeys}
        onOpenBatchEdit={ws.openBatchEdit}
        onOpenBatchStructuredReview={ws.openBatchStructuredReview}
        onBatchDelete={ws.handleBatchDelete}
        onCreateReviewSessionFromSelected={async () => {
          const row = await ws.createReviewSessionFromSelected();
          if (row?.id) navigate(`/reviews?sessionId=${row.id}&kind=${encodeURIComponent(row.review_kind || 'custom')}`);
        }}
        onCreateReviewSessionFromFilter={async () => {
          const row = await ws.createReviewSessionFromCurrentFilter();
          if (row?.id) navigate(`/reviews?sessionId=${row.id}&kind=${encodeURIComponent(row.review_kind || 'custom')}`);
        }}
        onCreateTradePlanFromSelected={async () => {
          const row = await ws.createTradePlanFromSelected();
          if (row?.id) navigate('/plans');
        }}
        onSetDateRange={ws.setDateRange}
        onUpdateFilter={ws.updateFilter}
      />

      <Card className="trade-table-card" bodyStyle={{ padding: 0 }}>
        {ws.viewMode === 'fills' ? (
          <TradeFillsTable
            rows={ws.trades}
            loading={ws.loading}
            pagination={ws.pagination}
            selectedRowKeys={ws.selectedRowKeys}
            onSelectionChange={ws.setSelectedRowKeys}
            onPageChange={(page, pageSize) => ws.setPagination((p) => ({ ...p, current: page, pageSize }))}
            onOpenDetail={ws.openTradeDetail}
            onOpenEdit={(id) => navigate(`/trades/${id}/edit`)}
            onDelete={ws.handleDeleteTrade}
          />
        ) : (
          <TradePositionsTable rows={ws.positions} loading={ws.loading} />
        )}
      </Card>

      <TradeDetailDrawer
        open={ws.detailOpen}
        tradeId={ws.activeTradeId}
        loading={ws.detailLoading}
        trade={ws.detailTrade}
        review={ws.detailReview}
        reviewExists={ws.detailReviewExists}
        source={ws.detailSource}
        legacy={ws.detailLegacy}
        reviewTaxonomy={ws.reviewTaxonomy}
        savingReview={ws.detailSavingReview}
        savingSource={ws.detailSavingSource}
        savingLegacy={ws.detailSavingLegacy}
        onClose={() => ws.setDetailOpen(false)}
        onReload={() => ws.activeTradeId && ws.loadTradeDetail(ws.activeTradeId)}
        onOpenEdit={() => ws.activeTradeId && navigate(`/trades/${ws.activeTradeId}/edit`)}
        onChangeReview={(k, v) => ws.setDetailReview((p) => ({ ...p, [k]: v }))}
        onChangeSource={(k, v) => ws.setDetailSource((p) => ({ ...p, [k]: v }))}
        onChangeLegacy={(k, v) => ws.setDetailLegacy((p) => ({ ...p, [k]: v }))}
        onSaveReview={ws.handleSaveDetailReview}
        onSaveSource={ws.handleSaveDetailSource}
        onSaveLegacy={ws.handleSaveDetailLegacy}
        onUpdateTradeSignal={ws.handleUpdateTradeSignal}
      />

      <TradeImportModal
        open={ws.importOpen}
        loading={ws.importLoading}
        sourceOptions={ws.sourceOptions}
        broker={ws.importBroker}
        text={ws.importText}
        result={ws.importResult}
        onCancel={() => ws.setImportOpen(false)}
        onConfirm={ws.handleImportTrades}
        onBrokerChange={ws.setImportBroker}
        onTextChange={ws.setImportText}
      />

      <TradeBatchEditModal
        open={ws.batchEditOpen}
        selectedCount={ws.selectedRowKeys.length}
        patch={ws.batchPatch}
        onCancel={() => ws.setBatchEditOpen(false)}
        onConfirm={ws.handleBatchEditSubmit}
        onChangePatch={(k, v) => ws.setBatchPatch((p) => ({ ...p, [k]: v }))}
      />

      <TradeBatchStructuredReviewModal
        open={ws.batchReviewOpen}
        selectedCount={ws.selectedRowKeys.length}
        review={ws.batchReviewPatch}
        reviewTaxonomy={ws.reviewTaxonomy}
        saving={ws.batchReviewSaving}
        onCancel={() => ws.setBatchReviewOpen(false)}
        onConfirm={ws.handleBatchStructuredReviewSubmit}
        onChange={(k, v) => ws.setBatchReviewPatch((p) => ({ ...p, [k]: v }))}
      />
    </div>
  );
}
