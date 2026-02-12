# Migration Guide: v1.0 → v2.0

## 📋 주요 변경사항

| 항목 | v1.0 | v2.0 |
|------|------|------|
| 아키텍처 | app.py에 모든 로직 | Core/Services/Chains 분리 |
| RAG | 저장만 함 | 검색 + 활용 |
| Vector Store | rag_store.py, vectorstore_oracle.py | core/vectorstore.py 통합 |
| Chat | RAG 미사용 | 과거 레포트 검색 |
| Custom Report | 단순 생성 | 유사 레포트 참조 |

---

## 🔧 Import 경로 변경

### Before (v1.0)
```python
from rag_store import upsert_report_doc, ingest_doc_to_rag
```

### After (v2.0)
```python
from core.vectorstore import VectorStore
from core.rag import RAGService

conn = get_oracle_conn()
vectorstore = VectorStore(conn)
rag_service = RAGService(conn)
```

---

## 📂 파일 구조

### 신규 파일
```
core/
├── embeddings.py      # 임베딩 생성
├── vectorstore.py     # Vector Store 통합
└── rag.py            # RAG 검색

services/
├── chat_service.py    # Chat 비즈니스 로직
└── report_service.py  # Report 비즈니스 로직

models/
└── schemas.py        # Pydantic 스키마

chains/
└── chat.py           # RAG 기반 채팅 (신규)
```

### 삭제/이동
- `rag_store.py` → `old/rag_store.py`
- `vectorstore_oracle.py` → `old/vectorstore_oracle.py`
- 기존 `app.py` → `old/app_old.py`

---

## 🔄 코드 마이그레이션

### Chat API

**Before:**
```python
# app.py
@app.post("/api/chat")
def chat(req: ChatRequest):
    messages = to_lc_messages(req)
    llm = ChatOpenAI(...)
    resp = llm.invoke(messages)
    return {"answer": resp.content}
```

**After:**
```python
# app.py (라우터만)
@app.post("/api/chat")
def chat(req: ChatRequest):
    conn = get_oracle_conn()
    chat_service = ChatService(conn)
    return chat_service.process_chat(req, use_rag=True)

# services/chat_service.py (비즈니스 로직)
def process_chat(self, req, use_rag=True):
    return generate_chat_response(req, self.rag_service, use_rag)
```

### Vector Store

**Before:**
```python
from rag_store import upsert_report_doc, ingest_doc_to_rag

upsert_report_doc(conn, doc_id=..., title=..., body_md=...)
ingest_doc_to_rag(conn, doc_id=..., body_md=...)
```

**After:**
```python
from core.vectorstore import VectorStore

vs = VectorStore(conn)
vs.upsert_document(doc_id=..., title=..., body_md=...)
vs.ingest_document(doc_id=..., body_md=...)
```

---

## 🧪 테스트

### 1. Health Check
```bash
curl http://localhost:8000/health
# {"ok": true, "version": "2.0.0"}
```

### 2. RAG 검색 테스트
```bash
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "립 슬리핑 마스크", "doc_types": ["DAILY"], "top_k": 3}'
```

### 3. Chat (RAG 포함)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "지난 주 순위 변화는?"}]}'
```

---

## 🐛 문제 해결

### Import Error
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### RAG 결과 없음
```sql
-- 임베딩 확인
SELECT COUNT(*) FROM rag_doc_chunks;

-- 최근 문서
SELECT doc_id, title FROM rag_docs ORDER BY created_at DESC FETCH FIRST 5 ROWS ONLY;
```

---

## ✅ 체크리스트

- [ ] 패키지 설치 확인 (`pip install -r requirements.txt`)
- [ ] 로컬 서버 실행 확인
- [ ] Health check 통과
- [ ] RAG 검색 테스트
- [ ] Chat API 동작 확인
- [ ] Custom Report 생성 확인
