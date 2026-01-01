import os
import oracledb
from dotenv import load_dotenv

# .env 로드
load_dotenv()

dsn = os.getenv("ORACLE_TLS_DSN")
user = os.getenv("ORACLE_USER")
password = os.getenv("ORACLE_PASSWORD")

print("DSN:", dsn)

try:
    conn = oracledb.connect(
        user=user,
        password=password,
        dsn=dsn
    )
    print("✅ Oracle DB 연결 성공!")

    cursor = conn.cursor()
    cursor.execute("SELECT SYSDATE FROM dual")
    row = cursor.fetchone()
    print("서버 시간:", row[0])

    cursor.close()
    conn.close()

except Exception as e:
    print("❌ Oracle DB 연결 실패")
    print(e)