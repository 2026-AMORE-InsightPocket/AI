# GitHub Actions

## 활성화된 Workflows

### 1. `deploy.yml`

**API 서버 자동 배포**

- **트리거**: `main` 브랜치에 push 시 자동 실행
- **실행 위치**: EC2 (`/home/ubuntu/AI`)
- **배포 방식**: Docker Compose
- **동작**:
  1. EC2에 SSH 접속
  2. Git pull (최신 코드)
  3. Docker Compose down
  4. Docker Compose up --build (재빌드 & 재시작)

### 2. `daily-report.yml`

**Daily Report 자동 생성**

- **스케줄**: 매일 오전 6시 (KST) / 오후 9시 (UTC)
- **실행 위치**: EC2 (`/home/ubuntu/AI`)
- **환경**: venv (`.venv`)
- **실행 스크립트**: `generate_daily_report.py`
- **동작**:
  1. EC2에 SSH 접속
  2. Git pull (최신 코드)
  3. venv 생성/활성화
  4. 패키지 설치
  5. Daily Report 생성 & DB 저장 (임베딩 포함)

---

## 수동 실행

GitHub Actions 탭에서:
- **Deploy**: `Deploy to EC2` → `Run workflow`
- **Daily Report**: `Daily Report` → `Run workflow`
