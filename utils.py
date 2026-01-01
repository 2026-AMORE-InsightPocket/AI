# AiService/utils.py
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import re
from typing import Any, Dict, List


def _to_str(v) -> str:
    """Oracle CLOB(oracledb.LOB) / None / str 모두 문자열로 변환"""
    if v is None:
        return ""
    # oracledb.LOB 는 read()로 문자열 획득
    if hasattr(v, "read"):
        try:
            return v.read()
        except Exception:
            return str(v)
    return str(v)

def now_kst_str() -> str:
    """KST(Asia/Seoul) 현재 시각 문자열."""
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")



def normalize_product_name(name) -> str:
    s = _to_str(name).strip().lower()
    # 공백/특수문자 normalize (원하는대로 규칙 조절 가능)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\-\(\)\[\]\.,&/+:]", "", s)
    return s

def md_table(rows: List[Dict[str, Any]], columns: List[str], headers: List[str] | None = None) -> str:
    """
    rows: dict 리스트
    columns: 뽑을 키 순서
    headers: 표시 헤더(없으면 columns 그대로)
    """
    if headers is None:
        headers = columns

    # header
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(columns)) + " |")

    # body
    for r in rows:
        vals = []
        for c in columns:
            v = r.get(c, "")
            vals.append("" if v is None else str(v))
        out.append("| " + " | ".join(vals) + " |")

    return "\n".join(out)