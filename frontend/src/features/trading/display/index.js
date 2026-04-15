import { formatFuturesSymbol } from '../../../utils/futures';
import { REVIEW_LINK_ROLE_ZH, mapLabel, getTaxonomyLabel } from '../localization';

const TAG_COLOR_PALETTE = [
  'magenta',
  'red',
  'volcano',
  'orange',
  'gold',
  'lime',
  'green',
  'cyan',
  'blue',
  'geekblue',
  'purple',
];

export function normalizeTagList(raw) {
  if (raw == null) return [];
  const values = Array.isArray(raw) ? raw : String(raw).split(/[,\n;|，、]+/);
  const out = [];
  const seen = new Set();
  values.forEach((item) => {
    const name = String(item || '').trim();
    if (!name) return;
    const key = name.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(name);
  });
  return out;
}

export function getTagColor(rawTag) {
  const tag = String(rawTag || '').trim();
  if (!tag) return 'default';
  let hash = 0;
  for (let i = 0; i < tag.length; i += 1) {
    hash = (hash * 131 + tag.charCodeAt(i)) >>> 0;
  }
  return TAG_COLOR_PALETTE[hash % TAG_COLOR_PALETTE.length];
}

export function formatInstrumentDisplay(symbol = '', contract = '', fallback = '-') {
  const text = formatFuturesSymbol(symbol, contract).trim();
  return text || fallback;
}

export function formatReviewRoleLabel(role) {
  return mapLabel(REVIEW_LINK_ROLE_ZH, role, '关联交易');
}

export function formatReviewConclusionLabel(value) {
  return getTaxonomyLabel('review_conclusion', value);
}

export function formatSymbolDimensionKey(value) {
  const key = String(value || '').trim();
  if (!key || key === '未分类') return key || '未分类';
  return formatInstrumentDisplay(key, key, key);
}

export function buildTradeSearchOption(item) {
  const tradeDate = item.trade_date || '-';
  const instrument = formatInstrumentDisplay(item.symbol, item.contract);
  const direction = item.direction || '-';
  const quantity = item.quantity ?? '-';
  const openPrice = item.open_price ?? '-';
  const closePrice = item.close_price ?? '-';
  const pnl = item.pnl == null ? '-' : Number(item.pnl).toFixed(2);
  const source = item.source_display || '-';
  const reviewConclusion = item.review_conclusion
    ? ` · ${formatReviewConclusionLabel(item.review_conclusion)}`
    : '';

  return {
    value: item.trade_id,
    label: `${tradeDate} · ${instrument} · ${direction} · 手数 ${quantity} · 开/平 ${openPrice}/${closePrice} · PnL ${pnl} · 来源 ${source}${reviewConclusion} · #${item.trade_id}`,
    summary: {
      trade_id: item.trade_id,
      trade_date: item.trade_date,
      symbol: item.symbol,
      contract: item.contract,
      direction: item.direction,
      quantity: item.quantity,
      open_price: item.open_price,
      close_price: item.close_price,
      status: item.status,
      pnl: item.pnl,
      source_display: item.source_display,
      review_conclusion: item.review_conclusion,
      has_trade_review: item.has_trade_review,
    },
  };
}
