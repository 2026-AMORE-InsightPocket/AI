# AiService/sql.py
# NOTE: Oracle은 대소문자 컬럼명이 기본적으로 대문자로 반환될 수 있어.
# fetch 결과는 dict로 받을 때도 키가 대문자일 가능성이 높음.

# ---------------------------
# RULE / RAG DOCS
# ---------------------------

Q_RULE_DOC_LATEST = """
SELECT doc_id, title, body_md, created_at
FROM rag_docs
WHERE doc_type_id = :doc_type_rule
ORDER BY created_at DESC
FETCH FIRST 1 ROWS ONLY
"""
#kst로 변환
Q_UPSERT_DAILY_REPORT = """
MERGE INTO rag_docs t
USING ( SELECT :doc_id AS doc_id FROM dual ) s
ON (t.doc_id = s.doc_id)
WHEN MATCHED THEN UPDATE SET
  t.doc_type_id = :doc_type_daily,
  t.title = :title,
  t.body_md = :body_md,
  t.report_date = :report_date,
  t.created_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (
  doc_id, doc_type_id, title, body_md, report_date, created_at
) VALUES (
  :doc_id, :doc_type_daily, :title, :body_md, :report_date, CURRENT_TIMESTAMP
)
"""

# ---------------------------
# Categories
# ---------------------------

Q_CATEGORIES = """
SELECT id, code, name, sort_order
FROM categories
ORDER BY sort_order ASC
"""

# ---------------------------
# Ranking snapshots / items
# - target_time <= snapshot_time 중 "가장 최신" 스냅샷 1개 선택
# ---------------------------

Q_RANKING_SNAPSHOT_AT_OR_BEFORE = """
SELECT id, snapshot_time
FROM ranking_snapshots
WHERE category_id = :category_id
  AND snapshot_time <= :target_time
ORDER BY snapshot_time DESC
FETCH FIRST 1 ROWS ONLY
"""

Q_TOP30_BY_SNAPSHOT = """
SELECT rank, product_name, price, is_laneige
FROM ranking_items
WHERE snapshot_id = :snapshot_id
ORDER BY rank ASC
"""

# ---------------------------
# Laneige runs / snapshots
# ---------------------------

Q_LANEIGE_LATEST_RUN = """
SELECT snapshot_id, snapshot_time
FROM laneige_snapshot_runs
ORDER BY snapshot_time DESC
FETCH FIRST 1 ROWS ONLY
"""

Q_LANEIGE_PREV_RUN = """
SELECT snapshot_id, snapshot_time
FROM laneige_snapshot_runs
WHERE snapshot_time < :latest_run_time
ORDER BY snapshot_time DESC
FETCH FIRST 1 ROWS ONLY
"""

# 오늘 run 기준으로 라네즈 제품 스냅샷 + 제품 마스터 join
Q_LANEIGE_PRODUCT_SNAPSHOTS_BY_RUN = """
SELECT
  lps.product_snapshot_id,
  lps.snapshot_id,
  lps.product_id,
  lp.product_name,
  lp.customers_say_current,
  lps.price,
  lps.review_count,
  lps.rating,
  lps.last_month_sales,
  lps.rank_1,
  lps.rank_1_category,
  lps.rank_2,
  lps.rank_2_category,
  lps.customers_say
FROM laneige_product_snapshots lps
JOIN laneige_products lp ON lp.product_id = lps.product_id
WHERE lps.snapshot_id = :run_id
ORDER BY lp.product_name
"""

Q_ASPECT_DETAILS_BY_PRODUCT_SNAPSHOT = """
SELECT
  aspect_name,
  mention_total,
  mention_positive,
  mention_negative,
  summary
FROM laneige_aspect_details
WHERE product_snapshot_id = :product_snapshot_id
"""