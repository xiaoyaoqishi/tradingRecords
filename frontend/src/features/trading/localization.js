export const TAXONOMY_ZH = {
  opportunity_structure: {
    trend_initiation_pullback: '趋势启动回调',
    continuation_after_consolidation: '整理后延续',
    failed_breakout_reversal: '假突破反转',
    volatility_expansion_after_compression: '压缩后波动扩张',
    expectation_shift_second_leg: '预期切换二次段',
  },
  edge_source: {
    trend_continuation: '趋势延续',
    volatility_expansion: '波动扩张',
    positioning_squeeze: '持仓挤压',
    expectation_shift: '预期切换',
    liquidity_dislocation: '流动性错配',
    behavior_flow_asymmetry: '行为/流向不对称',
  },
  failure_type: {
    direction_wrong: '方向错误',
    timing_wrong: '时机错误',
    sizing_wrong: '仓位错误',
    execution_wrong: '执行错误',
    management_wrong: '管理错误',
    regime_mismatch: '市场环境不匹配',
    should_not_have_traded: '不该交易',
  },
  review_conclusion: {
    valid_pattern_valid_trade: '模式有效且交易有效',
    valid_pattern_invalid_trade: '模式有效但交易无效',
    invalid_pattern_but_profit: '模式无效但侥幸盈利',
    invalid_pattern_invalid_trade: '模式无效且交易无效',
    need_more_evidence: '证据不足待观察',
  },
};

export const TAXONOMY_FIELD_ZH = {
  opportunity_structure: '机会结构',
  edge_source: '优势来源',
  failure_type: '失败类型',
  review_conclusion: '复盘结论',
};

export function getTaxonomyLabel(field, canonicalValue) {
  const value = String(canonicalValue || '').trim();
  if (!value) return '-';
  return TAXONOMY_ZH[field]?.[value] || value;
}

export function taxonomyOptionsWithZh(field, values = []) {
  return values.map((value) => ({
    value,
    label: getTaxonomyLabel(field, value),
  }));
}
