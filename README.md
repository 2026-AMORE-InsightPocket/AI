# 💡 Insight Pocket AI Service

LANEIGE 아마존 데이터 기반 AI 인사이트 생성 서비스

> **v2.0.0** - RAG 기반 아키텍처 리팩토링 완료

---

## 👩‍💻 Developer

| Developer |
| :--: |
| <a href="https://github.com/dolmaroyujinpark"><img src="https://avatars.githubusercontent.com/dolmaroyujinpark" width="120px" alt="Park Yujin"/></a><br/>박유진 |

---

## 🛠 Tech Stack

| 역할 | 기술 |
| --- | --- |
| Framework | **FastAPI** |
| Language | **Python 3.11+** |
| LLM | **OpenAI GPT-4o-mini + LangChain** |
| Database | **Oracle Autonomous DB (Vector Search)** |
| Embedding | **OpenAI text-embedding-3-small** |
| Deployment | **Docker + AWS EC2** |

---

## ✨ Key Features

### 🎯 RAG (Retrieval-Augmented Generation)

**과거 레포트를 검색하여 일관되고 정확한 답변 생성**

- 시맨틱 검색 (Oracle Vector Search)
- 메타데이터 필터링 (문서 타입, 날짜)
- 자동 컨텍스트 구성

### 💬 Chat API

**RAG 기반 대화형 인사이트**

```http
POST /api/chat
```

- 과거 레포트 검색하여 트렌드 분석
- 사용자 첨부 데이터 인식
- 자연스러운 대화 톤

### 📊 Custom Report

**유사 과거 레포트 참조하여 일관된 분석**

```http
POST /api/report/custom
```

- 유사 레포트 자동 검색
- 일관된 분석 프레임워크
- Markdown 자동 생성

### 📅 Daily Report

**매일 자동 랭킹/리뷰 분석 레포트 생성**

- Amazon 랭킹 변동 분석
- 리뷰 감정 분석
- 자동 임베딩 생성 및 RAG 저장
- GitHub Actions 자동 실행 (매일 오전 6시 KST)

---

## 🏗 Architecture

### Clean Architecture

```
┌─────────────────────────────────────┐
│     FastAPI Routes (app.py)         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Service Layer                │
│  (chat_service, report_service)     │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌──▼──┐  ┌───▼───┐
│ Core  │  │Chain│  │Models │
│ - RAG │  │- Chat│  │Schemas│
│ - VS  │  │- Rpt│  │       │
└───────┘  └─────┘  └───────┘
```

### 프로젝트 구조

```
AiService/
├── core/                  # RAG, VectorStore, Embeddings
├── services/              # ChatService, ReportService
├── chains/                # Chat, Report, Daily
├── models/                # Pydantic Schemas
├── app.py                 # FastAPI App
└── generate_daily_report.py
```

---

## 🚀 로컬 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd AiService

# Conda 환경 활성화 (또는 venv 사용)
conda activate langchain

# 패키지 설치
pip install -r requirements.txt

# .env 설정
cp .env.example .env
# .env 파일 편집 (OPENAI_API_KEY, ORACLE 설정 등)
```

### 2. 서버 실행

```bash
# 개발 모드 (auto-reload)
uvicorn app:app --reload

# 또는 포트 지정
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

서버 접속: `http://localhost:8000`
API 문서: `http://localhost:8000/docs`

### 3. Daily Report 실행

```bash
python generate_daily_report.py
```

---

## 📡 API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

### Chat (RAG 포함)

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

### Custom Report

```bash
curl -X POST http://localhost:8000/api/report/custom \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "경쟁사 포지셔닝 분석",
        "attachedData": [...]
      }
    ]
  }'
```

### RAG Search (디버깅)

```bash
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "립 슬리핑 마스크",
    "doc_types": ["DAILY"],
    "top_k": 3
  }'
```

---

## ⚙️ 환경 변수

`.env` 파일 설정:

```env
# OpenAI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2

# Oracle Database
ORACLE_USER=your_username
ORACLE_PASSWORD=your_password
ORACLE_TLS_DSN=(description=...)

# Document Types
DOC_TYPE_RULE=0
DOC_TYPE_DAILY=1
DOC_TYPE_CUSTOM=2

RULE_DOC_ID=RULE_CUSTOM_V1
APP_TIMEZONE=Asia/Seoul
```

---

## 🗄 Database Schema

### rag_docs
문서 메타데이터

| Column | Type | Description |
|--------|------|-------------|
| doc_id | VARCHAR2(100) | Document ID (PK) |
| doc_type_id | NUMBER | 0=RULE, 1=DAILY, 2=CUSTOM |
| title | VARCHAR2(500) | 제목 |
| body_md | CLOB | Markdown 본문 |
| report_date | DATE | 레포트 날짜 |

### rag_doc_chunks
문서 청크 + 임베딩

| Column | Type | Description |
|--------|------|-------------|
| chunk_id | VARCHAR2(100) | Chunk ID (PK) |
| doc_id | VARCHAR2(100) | Document ID (FK) |
| content | CLOB | 청크 텍스트 |
| embedding | VECTOR | 임베딩 벡터 |

---

## 🧪 테스트

### RAG 검색 테스트

```bash
# 과거 레포트 검색
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "립 슬리핑 마스크", "doc_types": ["DAILY"], "top_k": 3}'
```

### 채팅 테스트 (RAG 포함)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "지난 2주 순위 변화는?"}]}'
```

---

## 📊 성능

| 작업 | 응답 시간 |
|------|----------|
| Chat (RAG 없음) | ~1-2s |
| Chat (RAG 포함) | ~2-4s |
| Custom Report | ~5-10s |
| Daily Report | ~30-60s |

---

## 🐛 Troubleshooting

### Import Error

```bash
# PYTHONPATH 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### RAG 검색 결과 없음

```sql
-- 임베딩 데이터 확인
SELECT COUNT(*) FROM rag_doc_chunks;

-- 최근 문서 확인
SELECT doc_id, title FROM rag_docs ORDER BY created_at DESC FETCH FIRST 5 ROWS ONLY;
```

### Oracle Vector Error (ORA-01484)

```python
# core/vectorstore.py
use_safe_insert=True  # 이미 설정됨
```

---

## 📚 추가 문서

- **RAG_DESIGN.md** - RAG 아키텍처 상세 설계
- **MIGRATION_GUIDE.md** - v1.0 → v2.0 마이그레이션 가이드

---

## 🗺 Roadmap

- ✅ RAG 통합
- ✅ Clean Architecture
- 🚧 Hybrid Search (키워드 + 시맨틱)
- 🚧 Query Expansion
- 📅 Fine-tuned Embeddings

---

## 📄 License

Proprietary - LANEIGE InsightPocket (2026 AMORE)

---

## 📞 Contact

[@dolmaroyujinpark](https://github.com/dolmaroyujinpark)
