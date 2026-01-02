# AiService/chains/daily_report.py
from __future__ import annotations

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from db import get_oracle_conn
import sql as Q
import settings
from utils import _to_str, normalize_product_name, md_table
from rag_store import upsert_report_doc, ingest_doc_to_rag


# =========================
# Config (RULE v2 기준)
# =========================
TARGET_HOUR_KST_DEFAULT = 11

BIG_RANK_MOVE = 5            # |Δrank| >= 5
ASPECT_NEG_RATIO_THR = 0.35  # neg_ratio >= 0.35
ASPECT_MENTION_THR = 30      # mention_total >= 30
MAX_ASPECTS_PER_PRODUCT = 3
MAX_REVIEW_PRODUCTS = 5
REVIEW_COUNT_SPIKE = 50      # (MVP) review_count 증가가 50 이상이면 급증으로 간주

KST = ZoneInfo("Asia/Seoul")


# =========================
# DB helpers
# - IMPORTANT: LOB(CLOB) 는 커넥션 열린 상태에서 read() 해야 함.
# =========================
def _row_to_dict(cur, row) -> Dict[str, Any]:
    cols = [d[0] for d in cur.description]
    out: Dict[str, Any] = {}
    for i, c in enumerate(cols):
        v = row[i]
        if hasattr(v, "read"):  # oracledb.LOB
            try:
                v = v.read()
            except Exception:
                v = str(v)
        out[c] = v
    return out


def fetch_one(sql: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conn = get_oracle_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(cur, row)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_all(sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    conn = get_oracle_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in cur.description]
        out: List[Dict[str, Any]] = []
        for r in rows:
            item = {}
            for i, c in enumerate(cols):
                v = r[i]
                if hasattr(v, "read"):
                    try:
                        v = v.read()
                    except Exception:
                        v = str(v)
                item[c] = v
            out.append(item)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def execute(sql: str, params: Dict[str, Any]) -> None:
    conn = get_oracle_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =========================
# Pure helpers
# =========================
def safe_delta_rank(yesterday_rank: Optional[int], today_rank: Optional[int]) -> Optional[int]:
    if yesterday_rank is None or today_rank is None:
        return None
    return int(yesterday_rank) - int(today_rank)  # +면 상승 (20->8 => +12)


def choose_customers_say(today: Any, current: Any) -> Optional[str]:
    t = _to_str(today).strip()
    if t:
        return t
    c = _to_str(current).strip()
    if c:
        return c
    return None


def to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def neg_ratio(neg: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return neg / total


def risk_score(neg_r: float, total: int) -> float:
    return neg_r * total


# =========================
# Time helpers
# =========================
def today_kst_date() -> date:
    return datetime.now(KST).date()


def make_target_dt(report_date: date, hour_kst: int) -> datetime:
    # DB 세션을 KST로 맞춰둔 전제면 naive datetime도 OK
    return datetime(report_date.year, report_date.month, report_date.day, hour_kst, 0, 0)


def doc_id_for_daily(report_date: date) -> str:
    return f"daily_{report_date.isoformat()}"


# =========================
# Load RULE_DOC (must exist)
# =========================
def load_rule_doc() -> Dict[str, Any]:
    row = fetch_one(Q.Q_RULE_DOC_LATEST, {"doc_type_rule": settings.DOC_TYPE_RULE})
    if not row:
        # RULE_DOC 없으면 생성 금지
        raise RuntimeError("RULE_DOC가 DB에 없습니다. (rag_docs / doc_type_id=RULE_DOC 확인)")
    body = _to_str(row.get("BODY_MD")).strip()
    if not body:
        raise RuntimeError("RULE_DOC body_md가 비어있습니다.")
    return {
        "doc_id": row.get("DOC_ID"),
        "title": row.get("TITLE"),
        "body_md": body,
    }


# =========================
# Ranking / category
# =========================
def load_categories() -> List[Dict[str, Any]]:
    rows = fetch_all(Q.Q_CATEGORIES, {})
    out = []
    for r in rows:
        out.append({
            "id": int(r["ID"]),
            "code": r["CODE"],
            "name": r["NAME"],
            "sort_order": int(r["SORT_ORDER"]),
        })
    return out


def load_snapshot_at_or_before(category_id: int, target_time: datetime) -> Optional[Dict[str, Any]]:
    r = fetch_one(Q.Q_RANKING_SNAPSHOT_AT_OR_BEFORE, {"category_id": category_id, "target_time": target_time})
    if not r:
        return None
    return {"id": int(r["ID"]), "snapshot_time": r["SNAPSHOT_TIME"]}


def load_top30(snapshot_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(Q.Q_TOP30_BY_SNAPSHOT, {"snapshot_id": snapshot_id})
    out = []
    for r in rows:
        out.append({
            "rank": int(r["RANK"]),
            "product_name": r["PRODUCT_NAME"],
            "price": float(r["PRICE"]),
            "is_laneige": r["IS_LANEIGE"],
        })
    return out


# =========================
# Laneige runs / snapshots
# =========================
def load_laneige_latest_run() -> Optional[Dict[str, Any]]:
    r = fetch_one(Q.Q_LANEIGE_LATEST_RUN, {})
    if not r:
        return None
    return {"snapshot_id": int(r["SNAPSHOT_ID"]), "snapshot_time": r["SNAPSHOT_TIME"]}


def load_laneige_prev_run(latest_run_time: Any) -> Optional[Dict[str, Any]]:
    r = fetch_one(Q.Q_LANEIGE_PREV_RUN, {"latest_run_time": latest_run_time})
    if not r:
        return None
    return {"snapshot_id": int(r["SNAPSHOT_ID"]), "snapshot_time": r["SNAPSHOT_TIME"]}


def load_laneige_products_by_run(run_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(Q.Q_LANEIGE_PRODUCT_SNAPSHOTS_BY_RUN, {"run_id": run_id})
    out = []
    for r in rows:
        out.append({
            "product_snapshot_id": int(r["PRODUCT_SNAPSHOT_ID"]),
            "snapshot_id": int(r["SNAPSHOT_ID"]),
            "product_id": int(r["PRODUCT_ID"]),
            "product_name": r["PRODUCT_NAME"],
            "customers_say_current": _to_str(r.get("CUSTOMERS_SAY_CURRENT")),
            "customers_say": _to_str(r.get("CUSTOMERS_SAY")),
            "price": float(r["PRICE"]),
            "review_count": int(r["REVIEW_COUNT"]),
            "rating": to_float(r.get("RATING")),
            "last_month_sales": to_int(r.get("LAST_MONTH_SALES")),
            "rank_1": to_int(r.get("RANK_1")),
            "rank_1_category": r.get("RANK_1_CATEGORY"),
            "rank_2": to_int(r.get("RANK_2")),
            "rank_2_category": r.get("RANK_2_CATEGORY"),
        })
    return out


def load_aspects(product_snapshot_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(Q.Q_ASPECT_DETAILS_BY_PRODUCT_SNAPSHOT, {"product_snapshot_id": product_snapshot_id})
    out = []
    for r in rows:
        out.append({
            "aspect_name": r["ASPECT_NAME"],
            "mention_total": int(r["MENTION_TOTAL"]),
            "mention_positive": int(r["MENTION_POSITIVE"]),
            "mention_negative": int(r["MENTION_NEGATIVE"]),
            "summary": _to_str(r.get("SUMMARY")),
        })
    return out


# =========================
# Fact bundle builders
# =========================
def build_category_sections(report_day: date, target_hour_kst: int) -> List[Dict[str, Any]]:
    cats = load_categories()
    today_target = make_target_dt(report_day, target_hour_kst)
    yday_target = make_target_dt(report_day - timedelta(days=1), target_hour_kst)

    sections: List[Dict[str, Any]] = []
    for c in cats:
        today_snap = load_snapshot_at_or_before(c["id"], today_target)
        yday_snap = load_snapshot_at_or_before(c["id"], yday_target)
        if not today_snap or not yday_snap:
            continue

        today_items = load_top30(today_snap["id"])
        yday_items = load_top30(yday_snap["id"])

        today_laneige = [it for it in today_items if it["is_laneige"] == "Y"]
        yday_laneige = [it for it in yday_items if it["is_laneige"] == "Y"]

        entered = (len(yday_laneige) == 0 and len(today_laneige) >= 1)
        exited = (len(yday_laneige) >= 1 and len(today_laneige) == 0)

        # laneige movers within TOP30 (name match)
        ymap = {normalize_product_name(it["product_name"]): it for it in yday_laneige}
        movers: List[Dict[str, Any]] = []
        unmatched = 0
        for it in today_laneige:
            key = normalize_product_name(it["product_name"])
            y = ymap.get(key)
            if not y:
                unmatched += 1
                continue
            d = safe_delta_rank(y["rank"], it["rank"])
            if d is None:
                continue
            movers.append({
                "product_name": it["product_name"],
                "today_rank": it["rank"],
                "yesterday_rank": y["rank"],
                "delta_rank": d,
                "price": it["price"],
            })

        movers.sort(key=lambda x: abs(x["delta_rank"]), reverse=True)
        movers = movers[:5]

        sections.append({
            "category": c,
            "today_snapshot": {"id": today_snap["id"], "time": today_snap["snapshot_time"]},
            "yesterday_snapshot": {"id": yday_snap["id"], "time": yday_snap["snapshot_time"]},
            "top30_today": today_items,
            "top30_yesterday": yday_items,
            "laneige": {
                "count_today": len(today_laneige),
                "count_yesterday": len(yday_laneige),
                "entered": entered,
                "exited": exited,
                "movers": movers,
                "unmatched_today_laneige": unmatched,
            }
        })

    return sections


def build_laneige_changes() -> Dict[str, Any]:
    latest = load_laneige_latest_run()
    if not latest:
        return {"ok": False, "reason": "NO_LANEIGE_RUN", "changes": [], "runs": None}

    prev = load_laneige_prev_run(latest["snapshot_time"])
    if not prev:
        return {"ok": False, "reason": "NO_PREV_LANEIGE_RUN", "changes": [], "runs": {"latest": latest, "prev": None}}

    today_rows = load_laneige_products_by_run(latest["snapshot_id"])
    prev_rows = load_laneige_products_by_run(prev["snapshot_id"])
    prev_by_pid = {r["product_id"]: r for r in prev_rows}

    changes: List[Dict[str, Any]] = []
    for t in today_rows:
        p = prev_by_pid.get(t["product_id"])
        if p:
            t1, t2 = t.get("rank_1"), t.get("rank_2")
            p1, p2 = p.get("rank_1"), p.get("rank_2")
            if t1 == p1 and t2 == p2:
                continue

            changes.append({
                "product_id": t["product_id"],
                "product_snapshot_id": t["product_snapshot_id"],
                "product_name": t["product_name"],
                "today": t,
                "yesterday": p,
                "delta": {
                    "rank_1": safe_delta_rank(p1, t1) if (p1 is not None and t1 is not None) else None,
                    "rank_2": safe_delta_rank(p2, t2) if (p2 is not None and t2 is not None) else None,
                    "review_count": t["review_count"] - p["review_count"],
                },
                "customers_say_selected": choose_customers_say(t.get("customers_say"), t.get("customers_say_current")),
            })
        else:
            changes.append({
                "product_id": t["product_id"],
                "product_snapshot_id": t["product_snapshot_id"],
                "product_name": t["product_name"],
                "today": t,
                "yesterday": None,
                "delta": None,
                "customers_say_selected": choose_customers_say(t.get("customers_say"), t.get("customers_say_current")),
                "note": "NEW_PRODUCT_IN_RUN",
            })

    def change_score(ch: Dict[str, Any]) -> int:
        d = ch.get("delta") or {}
        return max(abs(d.get("rank_1") or 0), abs(d.get("rank_2") or 0), abs(d.get("review_count") or 0))

    changes.sort(key=change_score, reverse=True)
    return {"ok": True, "runs": {"latest": latest, "prev": prev}, "changes": changes}


def decide_review_include(category_sections: List[Dict[str, Any]], laneige_changes: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if any(sec["laneige"]["entered"] or sec["laneige"]["exited"] for sec in category_sections):
        reasons.append("TOP30_진입/이탈 발생")

    for ch in laneige_changes.get("changes", []):
        d = ch.get("delta") or {}
        r1 = d.get("rank_1")
        r2 = d.get("rank_2")
        if (r1 is not None and abs(r1) >= BIG_RANK_MOVE) or (r2 is not None and abs(r2) >= BIG_RANK_MOVE):
            reasons.append(f"큰 랭킹 변동(|Δrank|≥{BIG_RANK_MOVE})")
            break

    for ch in laneige_changes.get("changes", []):
        d = ch.get("delta") or {}
        rc = d.get("review_count")
        if isinstance(rc, int) and rc >= REVIEW_COUNT_SPIKE:
            reasons.append(f"리뷰 수 급증(Δreviews≥{REVIEW_COUNT_SPIKE})")
            break

    return (len(reasons) > 0), reasons


def build_review_products(laneige_changes: Dict[str, Any]) -> List[Dict[str, Any]]:
    def score(ch: Dict[str, Any]) -> int:
        d = ch.get("delta") or {}
        return max(abs(d.get("rank_1") or 0), abs(d.get("rank_2") or 0), abs(d.get("review_count") or 0))

    targets = sorted(laneige_changes.get("changes", []), key=score, reverse=True)[:MAX_REVIEW_PRODUCTS]

    out: List[Dict[str, Any]] = []
    for ch in targets:
        psid = ch["product_snapshot_id"]
        aspects = load_aspects(psid)

        risky: List[Dict[str, Any]] = []
        for a in aspects:
            total = a["mention_total"]
            neg = a["mention_negative"]
            nr = neg_ratio(neg, total)

            if nr >= ASPECT_NEG_RATIO_THR and total >= ASPECT_MENTION_THR:
                risky.append({
                    "aspect_name": a["aspect_name"],
                    "mention_total": total,
                    "mention_positive": a["mention_positive"],
                    "mention_negative": neg,
                    "neg_ratio": nr,
                    "risk_score": risk_score(nr, total),
                    "summary": a["summary"],
                })

        risky.sort(key=lambda x: x["risk_score"], reverse=True)
        risky = risky[:MAX_ASPECTS_PER_PRODUCT]

        out.append({
            "product_id": ch["product_id"],
            "product_name": ch["product_name"],
            "customers_say": ch.get("customers_say_selected"),
            "aspects": risky,
            "delta": ch.get("delta"),
        })

    return out


# =========================
# Render blocks
# =========================
def render_category_tables(category_sections: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for sec in category_sections:
        cat = sec["category"]
        blocks.append(f"### {cat['code']} ({cat['name']})")
        blocks.append(f"- 기준 스냅샷: today={sec['today_snapshot']['time']} / yesterday={sec['yesterday_snapshot']['time']}")
        blocks.append(f"- TOP30 내 라네즈 개수: today={sec['laneige']['count_today']} / yesterday={sec['laneige']['count_yesterday']}")
        if sec["laneige"]["entered"]:
            blocks.append("- 상태: **라네즈 TOP30 진입(어제 0 → 오늘 ≥1)**")
        if sec["laneige"]["exited"]:
            blocks.append("- 상태: **라네즈 TOP30 이탈(어제 ≥1 → 오늘 0)**")

        movers = sec["laneige"]["movers"]
        if movers:
            m_lines = []
            for m in movers:
                sign = "▲" if m["delta_rank"] > 0 else ("▼" if m["delta_rank"] < 0 else "—")
                m_lines.append(
                    f"  - {sign} {m['product_name']}: Δrank={m['delta_rank']:+d} (today #{m['today_rank']}, yesterday #{m['yesterday_rank']})"
                )
            blocks.append("- 라네즈 movers (TOP30 내, name 매칭):\n" + "\n".join(m_lines))
        else:
            if sec["laneige"]["count_today"] > 0:
                blocks.append(f"- 라네즈 movers: 매칭 가능한 항목이 부족함 (unmatched={sec['laneige']['unmatched_today_laneige']})")

        table_md = md_table(
            sec["top30_today"],
            columns=["rank", "product_name", "price", "is_laneige"],
            headers=["rank", "product_name", "price", "laneige(Y/N)"]
        )
        blocks.append("<!--TOP30_TABLE_START-->\n" + table_md + "\n<!--TOP30_TABLE_END-->")
        blocks.append("")

    return "\n".join(blocks).strip()


def render_laneige_changes_block(laneige_changes: Dict[str, Any], max_items: int = 30) -> str:
    changes = laneige_changes.get("changes", [])
    if not changes:
        return "_변동이 있는 라네즈 제품이 없습니다._"

    lines: List[str] = []
    for ch in changes[:max_items]:
        t = ch["today"]
        d = ch.get("delta") or {}

        r1 = t.get("rank_1")
        r1c = t.get("rank_1_category")
        r2 = t.get("rank_2")
        r2c = t.get("rank_2_category")

        dr1 = d.get("rank_1")
        dr2 = d.get("rank_2")
        drc = d.get("review_count")

        def fmt_rank(r): return f"#{r}" if r is not None else "None"

        parts = []
        parts.append(f"rank_1={fmt_rank(r1)} ({r1c})" if r1c else f"rank_1={fmt_rank(r1)}")
        if r2c:
            parts.append(f"rank_2={fmt_rank(r2)} ({r2c})")
        else:
            parts.append("rank_2=None")

        delta_parts = []
        if dr1 is not None:
            delta_parts.append(f"Δrank_1={dr1:+d}")
        if dr2 is not None:
            delta_parts.append(f"Δrank_2={dr2:+d}")
        if isinstance(drc, int):
            delta_parts.append(f"Δreviews={drc:+d}")

        lines.append(
            f"- **{ch['product_name']}** | " +
            ", ".join(parts) +
            f" | rating={t.get('rating')} | reviews={t.get('review_count')} | " +
            (" ".join(delta_parts) if delta_parts else "Δ=None")
        )

    return "\n".join(lines)


def render_review_block(review_products: List[Dict[str, Any]], review_reasons: List[str]) -> str:
    if not review_products:
        return "_리뷰 섹션 대상 제품이 없습니다._"

    blocks: List[str] = []
    blocks.append(f"- 리뷰 섹션 생성 사유: {', '.join(review_reasons)}")

    for p in review_products:
        blocks.append(f"\n**{p['product_name']}**")
        cs = p.get("customers_say")
        if cs:
            blocks.append(f"- customers_say(요약 근거): {cs[:500]}{'...' if len(cs) > 500 else ''}")
        else:
            blocks.append("- customers_say: None")

        aspects = p.get("aspects") or []
        if not aspects:
            blocks.append("- aspect 리스크 신호: (조건 충족 항목 없음)")
        else:
            blocks.append("- aspect 리스크 신호(조건: neg_ratio≥0.35 & mentions≥30, 최대 3개):")
            for a in aspects:
                blocks.append(
                    f"  - {a['aspect_name']}: {a['mention_total']} mentions "
                    f"({a['mention_positive']}+ / {a['mention_negative']}-), "
                    f"neg_ratio={a['neg_ratio']:.2f} — {a['summary'][:240]}{'...' if len(a['summary']) > 240 else ''}"
                )

    return "\n".join(blocks).strip()


# =========================
# Insight selection
# =========================
def choose_one_line_insight(category_sections: List[Dict[str, Any]], laneige_changes: Dict[str, Any]) -> str:
    for sec in category_sections:
        if sec["laneige"]["entered"]:
            return (
                f"{sec['category']['code']} 카테고리 TOP30 내 라네즈 제품이 어제 0개 → 오늘 {sec['laneige']['count_today']}개로 증가하며 "
                f"노출이 진입했습니다."
            )
        if sec["laneige"]["exited"]:
            return (
                f"{sec['category']['code']} 카테고리 TOP30 내 라네즈 제품이 어제 {sec['laneige']['count_yesterday']}개 → 오늘 0개로 감소하며 "
                f"노출이 이탈했습니다."
            )

    changes = laneige_changes.get("changes", [])
    best = None
    best_score = -1
    for ch in changes:
        d = ch.get("delta") or {}
        score = max(abs(d.get("rank_1") or 0), abs(d.get("rank_2") or 0))
        if score > best_score:
            best_score = score
            best = ch

    if best and best_score > 0:
        d = best.get("delta") or {}
        dr = d.get("rank_1") if d.get("rank_1") is not None else d.get("rank_2")
        if dr is not None:
            direction = "상승" if dr > 0 else "하락"
            return f"{best['product_name']}의 카테고리 랭킹이 어제 대비 {dr:+d} 변동하며({direction}) 변동 폭이 가장 컸습니다."

    best_cat = None
    best_diff = 0
    for sec in category_sections:
        diff = sec["laneige"]["count_today"] - sec["laneige"]["count_yesterday"]
        if abs(diff) > abs(best_diff):
            best_diff = diff
            best_cat = sec

    if best_cat and best_diff != 0:
        if best_diff > 0:
            return f"{best_cat['category']['code']} 카테고리 TOP30 내 라네즈 노출이 어제 대비 {best_diff}개 증가했습니다."
        else:
            return f"{best_cat['category']['code']} 카테고리 TOP30 내 라네즈 노출이 어제 대비 {abs(best_diff)}개 감소했습니다."

    return "오늘 데이터에서 라네즈 노출/랭킹의 뚜렷한 변화 신호가 제한적입니다."


# =========================
# LLM Writer
# =========================
def llm_write_final_report(
    rule_doc_md: str,
    report_day: date,
    target_hour_kst: int,
    category_tables_md: str,
    laneige_changes_md: str,
    review_md: Optional[str],
    one_line_insight: str,
) -> str:
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
    )

    system = f"""
You are InsightPocketAI. You must follow the RULE_DOC strictly.

<RULE_DOC>
{rule_doc_md}
</RULE_DOC>

Hard constraints:
- Output must be in Korean.
- Do NOT invent facts. If evidence is missing, say "근거 부족" or "데이터 없음(None)".
- Do NOT modify any markdown tables between <!--TOP30_TABLE_START--> and <!--TOP30_TABLE_END-->.
- The report MUST include the top line "**오늘의 인사이트:** ..." exactly once at the top.
- The report MUST end with a "<제안>" section (required).
""".strip()

    human = f"""
[REPORT_CONTEXT]
- report_date: {report_day.isoformat()}
- 기준 시각(KST): {target_hour_kst}:00
- 오늘의 인사이트 후보(이미 계산됨): {one_line_insight}

[SECTION_2_INPUT: MARKET & CATEGORY TOP30 TABLES]
{category_tables_md}

[SECTION_3_INPUT: LANEIGE PRODUCT RANK CHANGES]
{laneige_changes_md}

[SECTION_4_INPUT: REVIEW SIGNALS (CONDITIONAL)]
{review_md if review_md else "(리뷰 섹션: 조건 미충족으로 생략)"}

[YOUR TASK]
Using ONLY the inputs above, write the final DAILY report in Markdown.
Follow RULE_DOC's required section order.
- Keep the TOP30 tables unchanged.
- Section 2 should explain laneige exposure changes by category (do not deep dive into individual products here).
- Section 3 should summarize laneige product ranking changes (only changed products are given).
- Section 4 only if provided; link review signals to ranking movement/risks.
- End with <제안>: provide action items grounded in the evidence.
""".strip()

    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    return _to_str(resp.content).strip()


# =========================
# Save daily report
# =========================
def save_daily_report(report_day: date, body_md: str, target_hour_kst: int) -> Dict[str, Any]:
    """
    1) rag_docs 업서트 저장
    2) rag_doc_chunks 재생성 + 임베딩 저장
    """
    conn = get_oracle_conn()
    try:
        doc_id = doc_id_for_daily(report_day)
        title = f"{report_day.year}년 {report_day.month}월 {report_day.day}일 리포트"

        # 1) rag_docs 저장(업서트)
        upsert_report_doc(
            conn,
            doc_id=doc_id,
            doc_type_id=settings.DOC_TYPE_DAILY,
            title=title,
            body_md=body_md,
            report_date=report_day,
        )

        # 2) rag_doc_chunks 저장(기존 삭제 후 재삽입 + embedding)
        rag_result = ingest_doc_to_rag(
            conn,
            doc_id=doc_id,
            body_md=body_md,
            chunk_max_chars=1200,
            chunk_overlap=120,
            embedding_model="text-embedding-3-small",
        )

        return {"doc_id": doc_id, "chunk_count": rag_result["chunk_count"], "title": title}

    finally:
        try:
            conn.close()
        except Exception:
            pass
# =========================
# Main entry
# =========================
def run_daily_report(
    report_day: Optional[date] = None,
    target_hour_kst: int = TARGET_HOUR_KST_DEFAULT,
    save: bool = True
) -> Dict[str, Any]:
    """
    데일리 리포트 생성
    - report_day: None이면 KST 기준 오늘 날짜
    - target_hour_kst: 스냅샷 기준시각(기본 11시)
    - save=True면 rag_docs에 DAILY_REPORT로 저장(날짜별 1개 doc_id)
    """
    try:
        if report_day is None:
            report_day = today_kst_date()

        # RULE_DOC 없으면 여기서 예외 발생 -> 생성 중단
        rule = load_rule_doc()

        category_sections = build_category_sections(report_day, target_hour_kst)
        laneige_changes = build_laneige_changes()

        category_tables_md = render_category_tables(category_sections)
        laneige_changes_md = render_laneige_changes_block(laneige_changes, max_items=30)

        include_review, review_reasons = decide_review_include(category_sections, laneige_changes)

        review_md: Optional[str] = None
        if include_review:
            review_products = build_review_products(laneige_changes)
            review_md = render_review_block(review_products, review_reasons)

        one_line = choose_one_line_insight(category_sections, laneige_changes)

        final_md = llm_write_final_report(
            rule_doc_md=rule["body_md"],
            report_day=report_day,
            target_hour_kst=target_hour_kst,
            category_tables_md=category_tables_md,
            laneige_changes_md=laneige_changes_md,
            review_md=review_md,
            one_line_insight=one_line,
        )

        saved = None
        if save:
            saved = save_daily_report(report_day, final_md, target_hour_kst)

        doc_id = saved["doc_id"] if saved else None
        chunk_count = saved["chunk_count"] if saved else 0

        return {
            "ok": True,
            "doc_id": doc_id,
            "chunk_count": chunk_count,
            "report_date": report_day.isoformat(),
            "target_hour_kst": target_hour_kst,
            "rule_doc_id": rule.get("doc_id"),
            "one_line_insight": one_line,
            "final_md": final_md,
            "review_included": include_review,
            "review_reasons": review_reasons,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "doc_id": None,
            "report_date": report_day.isoformat() if report_day else None,
            "target_hour_kst": target_hour_kst,
            "final_md": "",
        }