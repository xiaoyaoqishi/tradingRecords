export const EMPTY_REVIEW_TAXONOMY = {
  opportunity_structure: [],
  edge_source: [],
  failure_type: [],
  review_conclusion: [],
};

export const EMPTY_REVIEW = {
  opportunity_structure: '',
  edge_source: '',
  failure_type: '',
  review_conclusion: '',
  entry_thesis: '',
  invalidation_valid_evidence: '',
  invalidation_trigger_evidence: '',
  invalidation_boundary: '',
  management_actions: '',
  exit_reason: '',
  review_tags: '',
  research_notes: '',
};

export const EMPTY_SOURCE = {
  broker_name: '',
  source_label: '',
  import_channel: '',
  parser_version: '',
  source_note_snapshot: '',
  exists_in_db: false,
  derived_from_notes: true,
};

export const REVIEW_FIELD_KEYS = Object.keys(EMPTY_REVIEW);

export function normalizeText(val) {
  if (val === undefined || val === null) return null;
  const trimmed = String(val).trim();
  return trimmed || null;
}

export function parseSourceFallbackFromNotes(notes = '') {
  const text = String(notes || '');
  const mBroker = text.match(/来源券商:\s*([^|]+)/);
  const mSource = text.match(/来源:\s*([^|]+)/);
  const broker = mBroker ? mBroker[1].trim() : '';
  const source = mSource ? mSource[1].trim() : '';
  if (broker && source) return `${broker} / ${source}`;
  return broker || source || '-';
}
