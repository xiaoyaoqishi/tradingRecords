const FUTURES_SYMBOL_MAP = {
  IF: '沪深300股指',
  IH: '上证50股指',
  IC: '中证500股指',
  IM: '中证1000股指',
  T: '10年国债',
  TF: '5年国债',
  TS: '2年国债',
  TL: '30年国债',
  AU: '沪金',
  AG: '沪银',
  CU: '沪铜',
  AL: '沪铝',
  ZN: '沪锌',
  PB: '沪铅',
  NI: '沪镍',
  SN: '沪锡',
  SS: '不锈钢',
  RB: '螺纹钢',
  HC: '热卷',
  FU: '燃料油',
  BU: '沥青',
  RU: '橡胶',
  SP: '纸浆',
  BR: '丁二烯橡胶',
  SC: '原油',
  NR: '20号胶',
  LU: '低硫燃料油',
  BC: '国际铜',
  EB: '苯乙烯',
  EG: '乙二醇',
  SA: '纯碱',
  PF: '短纤',
  UR: '尿素',
  TA: 'PTA',
  MA: '甲醇',
  FG: '玻璃',
  ZC: '动力煤',
  SR: '白糖',
  CF: '棉花',
  CY: '棉纱',
  AP: '苹果',
  CJ: '红枣',
  PK: '花生',
  OI: '菜油',
  RM: '菜粕',
  SF: '硅铁',
  SM: '锰硅',
  PR: '瓶片',
  PS: '多晶硅',
  PX: '对二甲苯',
  C: '玉米',
  CS: '玉米淀粉',
  A: '豆一',
  B: '豆二',
  M: '豆粕',
  Y: '豆油',
  P: '棕榈油',
  I: '铁矿石',
  J: '焦炭',
  JM: '焦煤',
  L: '聚乙烯',
  PP: '聚丙烯',
  V: 'PVC',
  PG: '液化石油气',
  LH: '生猪',
  JD: '鸡蛋',
  RR: '粳米',
  BB: '胶合板',
  FB: '纤维板',
  SI: '工业硅',
  LC: '碳酸锂',
};

export const FUTURES_SYMBOL_OPTIONS = Object.keys(FUTURES_SYMBOL_MAP).sort().map((code) => ({
  label: `${FUTURES_SYMBOL_MAP[code]}（${code}）`,
  value: code,
}));

export function normalizeFuturesSymbol(symbol = '', contract = '') {
  const s = String(symbol || '').trim().toUpperCase();
  if (s) return s;
  const c = String(contract || '').trim().toUpperCase();
  const m = c.match(/^[A-Z]+/);
  return m ? m[0] : '';
}

export function futuresNameBySymbol(symbol = '', contract = '') {
  const code = normalizeFuturesSymbol(symbol, contract);
  return FUTURES_SYMBOL_MAP[code] || '';
}

export function formatFuturesSymbol(symbol = '', contract = '') {
  const code = normalizeFuturesSymbol(symbol, contract);
  if (!code) return symbol || '';
  const name = FUTURES_SYMBOL_MAP[code];
  return name ? `${name}（${code}）` : code;
}
