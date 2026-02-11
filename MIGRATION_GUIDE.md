# Migration Guide: v1.0 → v2.0

리팩토링된 v2.0으로 마이그레이션하는 가이드입니다.

---

## 📋 변경 사항 요약

### 주요 변경점

| 항목 | v1.0 | v2.0 |
|------|------|------|
| 아키텍처 | Monolithic (app.py) | Clean Architecture (Core/Services/Chains) |
| RAG | 저장만 함 | 검색 + 활용 |
| Vector Store | 2개 파일 분산 | 1개 통합 모듈 |
| Chat | RAG 미사용 | RAG 기반 컨텍스트 |
| Custom Report | 단순 생성 | 유사 레포트 참조 |

### 신규 기능

✅ **RAG 검색**
- 과거 레포트 시맨틱 검색
- 메타데이터 필터링
- 자동 컨텍스트 구성

✅ **클린 아키텍처**
- 계층 분리 (Core/Services/Chains)
- 재사용 가능한 모듈
- 테스트 용이성

✅ **향상된 로깅**
- 구조화된 로그
- RAG 검색 결과 추적
- 성능 모니터링

---

## 🔧 마이그레이션 단계

### 1. 코드 백업

```bash
# 기존 코드 백업
cp -r AiService AiService_v1_backup

# 또는 Git으로 관리 중이라면
git checkout -b backup-v1
git commit -am "Backup before v2.0 migration"
git checkout main
```

### 2. 의존성 업데이트

**requirements.txt 확인**

v2.0에 필요한 패키지들이 모두 포함되어 있는지 확인:

```bash
pip install -r requirements.txt
```

필요 시 추가:
```bash
pip install langchain-openai langchain-core langchain-community
```

### 3. Import 경로 변경

#### Before (v1.0)
```python
from rag_store import (
    upsert_report_doc,
    ingest_doc_to_rag,
    get_doc_body_by_id,
)
```

#### After (v2.0)
```python
from core.vectorstore import VectorStore
from core.rag import RAGService

# 사용
conn = get_oracle_conn()
vectorstore = VectorStore(conn)
rag_service = RAGService(conn)
```

### 4. 기존 코드 마이그레이션

#### 4-1. Chat 로직

**Before (v1.0)**:
```python
# app.py에 직접 구현
@app.post("/api/chat")
def chat(req: ChatRequest):
    messages = to_lc_messages(req)
    llm = ChatOpenAI(...)
    resp = llm.invoke(messages)
    return {"answer": resp.content}
```

**After (v2.0)**:
```python
# app.py: 라우터만
@app.post("/api/chat")
def chat(req: ChatRequest):
    conn = get_oracle_conn()
    chat_service = ChatService(conn)
    return chat_service.process_chat(req, use_rag=True)
```

#### 4-2. Custom Report

**Before (v1.0)**:
```python
# app.py
@app.post("/api/report/custom")
def report_custom(req: ChatRequest):
    rule_md = get_doc_body_by_id(conn, RULE_DOC_ID)
    body_md = generate_custom_report_md(
        lc_messages=lc_messages,
        rule_md=rule_md,
    )
    # ... 저장
```

**After (v2.0)**:
```python
# app.py: 라우터만
@app.post("/api/report/custom")
def report_custom(req: ChatRequest):
    conn = get_oracle_conn()
    report_service = ReportService(conn)
    return report_service.generate_custom_report(req, use_rag=True)

# services/report_service.py: 비즈니스 로직
class ReportService:
    def generate_custom_report(self, req, use_rag=True):
        # RAG 검색 포함
        rule_md = self.rag_service.get_rule_document()
        body_md = generate_custom_report_md(
            lc_messages=lc_messages,
            rule_md=rule_md,
            rag_service=self.rag_service,
            use_rag=use_rag,
        )
        # ...
```

#### 4-3. Daily Report

**변경 없음** - `chains/daily_report.py`는 그대로 사용 가능

단, VectorStore 사용 시:

**Before**:
```python
from rag_store import upsert_report_doc, ingest_doc_to_rag

upsert_report_doc(conn, ...)
ingest_doc_to_rag(conn, ...)
```

**After**:
```python
from core.vectorstore import VectorStore

vs = VectorStore(conn)
vs.upsert_document(...)
vs.ingest_document(...)
```

### 5. 레거시 파일 처리

v2.0에서는 다음 파일들이 `old/` 디렉토리로 이동되었습니다:

- `rag_store.py` → `core/vectorstore.py`로 통합
- `vectorstore_oracle.py` → `core/vectorstore.py`로 통합
- `app_old.py` → 백업용

**확인 사항**:
```bash
# 레거시 파일 확인
ls old/

# 새 파일 확인
ls core/
ls services/
ls models/
```

---

## 🧪 테스트

### 1. Health Check

```bash
curl http://localhost:8000/health

# 예상 응답:
# {"ok": true, "version": "2.0.0"}
```

### 2. Chat (RAG 없이)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "안녕하세요"}
    ]
  }'
```

### 3. Chat (RAG 포함)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "지난 주 베스트셀러 순위 변화는?"
      }
    ]
  }'
```

**확인**:
- 응답에 과거 레포트 내용이 반영되는지
- 로그에 `[RAG]` 관련 메시지가 있는지

### 4. RAG Search (새 기능)

```bash
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "립 슬리핑 마스크",
    "doc_types": ["DAILY"],
    "top_k": 3
  }'
```

**예상 응답**:
```json
{
  "results": [
    {
      "content": "...",
      "doc_id": "daily_2026-02-08",
      "title": "2026년 2월 8일 리포트",
      "similarity": 0.89
    }
  ],
  "query": "립 슬리핑 마스크",
  "total_found": 3
}
```

### 5. Custom Report

```bash
curl -X POST http://localhost:8000/api/report/custom \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "경쟁사 포지셔닝 분석",
        "attachedData": [
          {
            "title": "카테고리 TOP5",
            "lines": ["rank 1: Product A", "rank 2: Product B"]
          }
        ]
      }
    ]
  }'
```

**확인**:
- 유사한 과거 레포트를 참조했는지 (로그 확인)
- 일관된 형식의 레포트가 생성되는지

---

## 🔍 문제 해결

### 문제 1: Import Error

**증상**:
```
ModuleNotFoundError: No module named 'core'
```

**해결**:
```bash
# 올바른 디렉토리에서 실행하는지 확인
pwd  # /Users/.../AiService

# Python path 확인
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 또는 상대 import 사용
```

### 문제 2: Database Connection Error

**증상**:
```
DatabaseError: ORA-12154: TNS:could not resolve the connect identifier
```

**해결**:
```bash
# .env 파일 확인
cat .env | grep ORACLE

# 환경변수 로드 확인
python -c "import settings; print(settings.ORACLE_TLS_DSN)"
```

### 문제 3: RAG 검색 결과 없음

**증상**:
```json
{"results": [], "total_found": 0}
```

**해결**:
```sql
-- 1. 임베딩 데이터 확인
SELECT COUNT(*) FROM rag_doc_chunks;

-- 2. 최근 문서 확인
SELECT doc_id, title, created_at
FROM rag_docs
ORDER BY created_at DESC
FETCH FIRST 10 ROWS ONLY;

-- 3. 임베딩이 NULL인지 확인
SELECT COUNT(*)
FROM rag_doc_chunks
WHERE embedding IS NULL;
```

**재생성**:
```python
# 임베딩 재생성 스크립트
from core.vectorstore import VectorStore
from db import get_oracle_conn

conn = get_oracle_conn()
vs = VectorStore(conn)

# 특정 문서 재생성
doc_id = "daily_2026-02-08"
body_md = vs.get_document_by_id(doc_id)
vs.ingest_document(doc_id=doc_id, body_md=body_md)
```

### 문제 4: 성능 저하

**증상**:
- Chat 응답 시간 > 10초
- RAG 검색 시간 > 5초

**해결**:

1. **RAG 파라미터 조정**:
```python
# core/rag.py
max_context_chunks = 2  # 3 → 2로 감소
```

2. **Similarity 임계값 상향**:
```python
min_similarity = 0.8  # 0.7 → 0.8로 증가 (더 적은 결과)
```

3. **Vector Index 확인**:
```sql
-- Index 존재 확인
SELECT index_name
FROM user_indexes
WHERE table_name = 'RAG_DOC_CHUNKS';

-- Index 생성 (없으면)
CREATE VECTOR INDEX idx_rag_chunks_embedding
ON rag_doc_chunks(embedding)
ORGANIZATION NEIGHBOR PARTITIONS
WITH DISTANCE COSINE;
```

---

## 📊 성능 비교

### Before (v1.0)

| 작업 | 시간 | RAG 활용 |
|------|------|----------|
| Chat | 1-2s | ❌ |
| Custom Report | 3-5s | ❌ |
| Daily Report | 30-60s | 저장만 |

### After (v2.0)

| 작업 | 시간 | RAG 활용 |
|------|------|----------|
| Chat | 2-4s | ✅ (과거 레포트 검색) |
| Custom Report | 5-10s | ✅ (유사 레포트 참조) |
| Daily Report | 30-60s | ✅ (저장 + 검색 가능) |

**트레이드오프**:
- 응답 시간 약간 증가 (+1-2s)
- 답변 품질 크게 향상 (일관성, 정확성)

---

## ✅ 마이그레이션 체크리스트

### 사전 준비
- [ ] v1.0 코드 백업
- [ ] 데이터베이스 백업
- [ ] 환경변수 확인 (.env)
- [ ] 의존성 설치 확인

### 코드 변경
- [ ] Import 경로 변경
- [ ] app.py 리팩토링
- [ ] 서비스 레이어 적용
- [ ] RAG 기능 활성화

### 테스트
- [ ] Health check 통과
- [ ] Chat API 동작 확인
- [ ] Custom Report 생성 확인
- [ ] RAG 검색 결과 확인
- [ ] Daily Report 자동화 확인

### 배포
- [ ] 로컬 테스트 완료
- [ ] 스테이징 환경 배포
- [ ] 프로덕션 배포
- [ ] 모니터링 설정

### 사후 확인
- [ ] 응답 시간 모니터링
- [ ] 에러 로그 확인
- [ ] RAG 검색 품질 확인
- [ ] 사용자 피드백 수집

---

## 🎓 학습 리소스

### 코드베이스 이해

1. **아키텍처 다이어그램**: `README.md` → Architecture 섹션
2. **RAG 설계**: `RAG_DESIGN.md`
3. **API 문서**: `http://localhost:8000/docs`

### 주요 파일 위치

- **RAG 로직**: `core/rag.py`
- **Vector Store**: `core/vectorstore.py`
- **Chat 서비스**: `services/chat_service.py`
- **Report 서비스**: `services/report_service.py`

### 디버깅 팁

**로그 확인**:
```bash
# RAG 관련 로그만 필터
grep "RAG" logs/insightpocket.log

# 최근 에러
tail -f logs/insightpocket.log | grep ERROR
```

**DB 쿼리 확인**:
```sql
-- 최근 생성된 문서
SELECT * FROM rag_docs ORDER BY created_at DESC FETCH FIRST 5 ROWS ONLY;

-- 청크 개수 확인
SELECT doc_id, COUNT(*) as chunk_count
FROM rag_doc_chunks
GROUP BY doc_id
ORDER BY chunk_count DESC;
```

---

## 🆘 Support

문제가 발생하면:

1. **로그 확인**: `logs/insightpocket.log`
2. **Issue 생성**: GitHub Issues
3. **개발자 문의**: [@dolmaroyujinpark](https://github.com/dolmaroyujinpark)

---

## 🎉 마이그레이션 완료 후

축하합니다! v2.0 마이그레이션이 완료되었습니다.

**다음 단계**:
1. RAG 검색 품질 모니터링
2. 사용자 피드백 수집
3. 성능 최적화 (필요 시)
4. 추가 기능 개발 (Roadmap 참고)

**참고 문서**:
- `README.md`: 전체 프로젝트 가이드
- `RAG_DESIGN.md`: RAG 설계 상세
- `/docs`: API 문서 (실행 중일 때)
