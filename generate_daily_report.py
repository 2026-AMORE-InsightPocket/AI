# generate_daily_report.py
from db import get_oracle_conn
from chains.daily_report import run_daily_report

def debug_db_identity():
    conn = get_oracle_conn()
    cur = conn.cursor()
    cur.execute("""
      SELECT
        SYS_CONTEXT('USERENV','DB_NAME') AS DB_NAME,
        SYS_CONTEXT('USERENV','SERVICE_NAME') AS SERVICE_NAME,
        SYS_CONTEXT('USERENV','SESSION_USER') AS SESSION_USER,
        SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AS CURRENT_SCHEMA
      FROM dual
    """)
    print("[DB_IDENTITY]", cur.fetchone())
    cur.close()
    conn.close()

def main():
    debug_db_identity()

    result = run_daily_report(report_day=None, target_hour_kst=11, save=True)

    print("OK:", result.get("ok"))
    print("error:", result.get("error"))
    print("doc_id:", result.get("doc_id"))
    print("report_date:", result.get("report_date"))
    print("chunk_count:", result.get("chunk_count"))

if __name__ == "__main__":
    main()