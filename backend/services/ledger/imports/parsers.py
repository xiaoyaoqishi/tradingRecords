from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from core.errors import AppError


def decode_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError("invalid_file_encoding", "文件编码无法识别，支持 UTF-8/GBK", status_code=400)


def _table_to_rows(table: list[list[str]]) -> list[dict[str, Any]]:
    if not table:
        return []
    header = [str(x or "").strip() for x in table[0]]
    if not any(header):
        raise AppError("invalid_sheet", "表格表头为空", status_code=400)
    rows: list[dict[str, Any]] = []
    for raw in table[1:]:
        item: dict[str, Any] = {}
        for idx, col in enumerate(header):
            if not col:
                continue
            item[col] = raw[idx] if idx < len(raw) else ""
        rows.append(item)
    return rows


def _parse_csv(raw_bytes: bytes) -> list[dict[str, Any]]:
    text = decode_bytes(raw_bytes)
    sio = io.StringIO(text)
    sample = text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        pass
    reader = csv.DictReader(sio, delimiter=delimiter)
    if not reader.fieldnames:
        raise AppError("invalid_csv", "CSV 缺少表头", status_code=400)

    rows: list[dict[str, Any]] = []
    for row in reader:
        rows.append({str(k).strip(): (v if v is not None else "") for k, v in (row or {}).items() if k})
    return rows


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    out: list[str] = []
    for si in root.findall("s:si", ns):
        parts = []
        for t in si.findall(".//s:t", ns):
            parts.append(t.text or "")
        out.append("".join(parts))
    return out


def _col_index(col_ref: str) -> int:
    col = "".join(ch for ch in col_ref if ch.isalpha()).upper()
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(0, idx - 1)


def _parse_xlsx(raw_bytes: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in zf.namelist():
            candidates = [x for x in zf.namelist() if x.startswith("xl/worksheets/sheet") and x.endswith(".xml")]
            if not candidates:
                raise AppError("invalid_xlsx", "xlsx 未找到 worksheet", status_code=400)
            sheet_path = sorted(candidates)[0]

        shared = _xlsx_shared_strings(zf)
        xml = zf.read(sheet_path)

    root = ET.fromstring(xml)
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    table: list[list[str]] = []
    for row in root.findall(".//s:sheetData/s:row", ns):
        cols: dict[int, str] = {}
        max_idx = -1
        for c in row.findall("s:c", ns):
            ref = c.attrib.get("r", "")
            idx = _col_index(ref)
            max_idx = max(max_idx, idx)
            t = c.attrib.get("t")
            value = ""
            if t == "inlineStr":
                node = c.find("s:is/s:t", ns)
                value = (node.text or "") if node is not None else ""
            else:
                v = c.find("s:v", ns)
                raw = (v.text or "") if v is not None else ""
                if t == "s" and raw.isdigit() and int(raw) < len(shared):
                    value = shared[int(raw)]
                else:
                    value = raw
            cols[idx] = value

        if max_idx < 0:
            continue
        row_values = [cols.get(i, "") for i in range(max_idx + 1)]
        table.append(row_values)

    return _table_to_rows(table)


def _parse_xls(raw_bytes: bytes) -> list[dict[str, Any]]:
    # Real BIFF .xls (CFB container)
    if raw_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        try:
            import xlrd  # type: ignore
        except Exception as exc:  # pragma: no cover - env dependent
            raise AppError("missing_xls_dependency", "缺少 xls 解析依赖 xlrd", status_code=500) from exc

        try:
            book = xlrd.open_workbook(file_contents=raw_bytes)
        except Exception as exc:
            raise AppError("invalid_xls", "xls 文件解析失败", status_code=400) from exc
        if book.nsheets <= 0:
            raise AppError("invalid_xls", "xls 未包含工作表", status_code=400)

        sh = book.sheet_by_index(0)
        table: list[list[str]] = []
        for r in range(sh.nrows):
            row_vals: list[str] = []
            for c in range(sh.ncols):
                value = sh.cell_value(r, c)
                if isinstance(value, float) and value.is_integer():
                    row_vals.append(str(int(value)))
                else:
                    row_vals.append(str(value))
            table.append(row_vals)
        return _table_to_rows(table)

    # Many bank `.xls` exports are HTML table payloads.
    text = decode_bytes(raw_bytes)
    if "<table" in text.lower():
        soup = BeautifulSoup(text, "html.parser")
        table = soup.find("table")
        if table is None:
            raise AppError("invalid_xls", "xls(html) 未包含 table", status_code=400)
        lines: list[list[str]] = []
        for tr in table.find_all("tr"):
            cols = [cell.get_text(strip=True) for cell in tr.find_all(["th", "td"])]
            if cols:
                lines.append(cols)
        return _table_to_rows(lines)

    # Fallback: treat as delimited text exports renamed to `.xls`.
    sio = io.StringIO(text)
    sample = text[:4096]
    delimiter = "\t" if "\t" in sample else ","
    reader = csv.reader(sio, delimiter=delimiter)
    return _table_to_rows([list(x) for x in reader])


def parse_rows(raw_bytes: bytes, file_name: str) -> list[dict[str, Any]]:
    suffix = Path(file_name or "").suffix.lower()
    if suffix == ".csv":
        return _parse_csv(raw_bytes)
    if suffix == ".xlsx":
        return _parse_xlsx(raw_bytes)
    if suffix == ".xls":
        return _parse_xls(raw_bytes)
    raise AppError("unsupported_format", "仅支持 csv/xls/xlsx", status_code=400)
