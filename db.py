# db.py
import os
from pathlib import Path

import oracledb
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # AiService/.env

def get_oracle_conn():
    """
    .env에서 아래 값을 읽어 Oracle Autonomous DB(TCPS) 연결
    - ORACLE_USER
    - ORACLE_PASSWORD
    - ORACLE_TLS_DSN  (너가 넣어둔 (description=...tcps...) 문자열)
    """
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_TLS_DSN")

    if not user or not password or not dsn:
        raise RuntimeError("env 값 누락: ORACLE_USER / ORACLE_PASSWORD / ORACLE_TLS_DSN 확인")

    # 필요하면 세션 타임존을 KST로 강제(원하면 유지/삭제 가능)
    conn = oracledb.connect(user=user, password=password, dsn=dsn)

    # DB 자체 timezone 바꾸는 게 아니라 "현재 세션"을 KST로 맞추는 가장 안전한 방법
    # (Autonomous에서 DB 전체 timezone 변경은 권한/제약으로 막힌 경우가 많음)
    try:
        cur = conn.cursor()
        cur.execute("ALTER SESSION SET TIME_ZONE = 'Asia/Seoul'")
        cur.close()
    except Exception:
        # 권한/환경에 따라 실패할 수 있으니 연결은 유지
        pass

    return conn