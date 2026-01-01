# test_oracle.py
from db import get_oracle_conn

conn = get_oracle_conn()
cur = conn.cursor()
cur.execute("select sysdate from dual")
print(cur.fetchone())
conn.close()