# AiService/generate_daily_report.py
from chains.daily_report import run_daily_report

def main():
    result = run_daily_report(report_day=None, target_hour_kst=11, save=True)

    print("OK:", result.get("ok"))
    print("error:", result.get("error"))
    print("doc_id:", result.get("doc_id"))
    print("report_date:", result.get("report_date"))
    print("chunk_count:", result.get("chunk_count"))
    print("rule_doc_id:", result.get("rule_doc_id"))
    print("review_included:", result.get("review_included"))
    print("review_reasons:", result.get("review_reasons"))

    print("\n--- preview ---\n")
    print((result.get("final_md") or "")[:1500])

if __name__ == "__main__":
    main()