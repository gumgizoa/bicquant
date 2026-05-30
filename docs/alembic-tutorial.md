# Alembic 가이드

## 1. Alembic이 뭐냐

**SQLAlchemy 공식 마이그레이션 도구.** 코드(ORM 모델)와 DB 스키마가 동기화돼 있어야 하는데, 코드는 `git`으로 관리되지만 DB는 그 자체로 "상태"라서 관리가 까다로워. Alembic은 그 사이를 메우는 **버전 관리 시스템**이야 — Git이 코드 변경을 commit으로 추적하듯, Alembic은 스키마 변경을 **revision**으로 추적해.

```
모델 변경  →  revision 파일 생성  →  upgrade로 DB에 적용
   ↑                                       ↓
   (git처럼 versioned)                 (실제 SQL 실행)
```

## 2. 핵심 개념 4개만 알면 됨

| 용어 | 뜻 |
|------|---|
| **revision** | 스키마 변경 하나. `alembic/versions/0001_baseline.py` 같은 파일. |
| **head** | 가장 최신 revision (= git의 `HEAD`와 같은 개념). |
| **upgrade** | DB를 한 단계(또는 head까지) 앞으로 굴림 — `upgrade()` 함수 실행. |
| **downgrade** | 한 단계(또는 특정 revision까지) 되돌림 — `downgrade()` 함수 실행. |

각 revision 파일은 두 함수만 있어:

```python
def upgrade():    # 이 revision으로 가는 방법 (ADD/CREATE)
    op.add_column("watchlist", sa.Column("memo", sa.String(200)))

def downgrade():  # 되돌리는 방법 (DROP/REMOVE)
    op.drop_column("watchlist", "memo")
```

## 3. 우리 프로젝트 구조

```
backend/
  alembic.ini                  ← 설정 파일 (script_location, 로깅 등)
  alembic/
    env.py                     ← "어떤 DB에 / 어떤 모델로 연결할지" 정의
    script.py.mako             ← 새 revision 만들 때 쓰는 템플릿
    versions/
      0001_baseline.py         ← 첫 번째 revision (현재 3개 테이블)
```

- `env.py`는 `shared.models.Base`를 import해서 Base.metadata에 모든 ORM 모델 등록 → autogenerate가 모델과 DB 스키마를 비교할 수 있게 해줌
- `versions/`에 revision 파일이 시간순으로 쌓이고, 각 파일은 `down_revision`으로 이전 파일을 가리켜서 사슬 형성

## 4. 일상 워크플로우 — "모델에 컬럼 추가하고 싶어"

**Step 1.** ORM 모델 수정

```python
# shared/models/watchlist.py
class Watchlist(Base):
    ...
    memo: Mapped[str | None] = mapped_column(String(200))   # 새 컬럼
```

**Step 2.** revision 자동 생성

```bash
cd backend
uv run alembic revision --autogenerate -m "add memo to watchlist"
```

`alembic/versions/0002_add_memo_to_watchlist.py`가 생기는데, 모델과 현재 DB를 비교해서 diff를 `upgrade()`/`downgrade()`에 채워줘. **꼭 열어서 확인할 것** — autogenerate는 완벽하지 않아서 가끔 이상한 걸 만들어내거든 (특히 server_default 변경, type 변경, rename).

**Step 3.** DB에 적용

```bash
uv run alembic upgrade head
```

**Step 4.** revision 파일을 git에 commit. 다음 사람은 pull 받고 `alembic upgrade head`만 돌리면 끝.

## 5. 자주 쓰는 명령어

```bash
alembic current                        # 지금 DB가 어느 revision인지
alembic history                        # 전체 revision 목록
alembic upgrade head                   # 최신까지 진행
alembic upgrade +1                     # 한 단계만 진행
alembic downgrade -1                   # 한 단계 되돌림
alembic downgrade base                 # 전부 되돌림 (DROP all)
alembic stamp 0001_baseline            # 실제로 실행은 안 하고 "이 revision 적용된 걸로 치자" 표시만
alembic revision -m "name"             # 빈 revision 생성 (수동 작성용)
alembic revision --autogenerate -m ""  # 모델 diff로 채워서 생성
```

## 6. 처음 한 번 — 어느 명령을 써야 하나

DB에 이미 데이터/테이블 있어? 두 갈래야:

### (A) 이미 watchlist/sidecar_events/deviation_alerts 테이블이 있고 데이터도 있다

→ baseline 마이그레이션을 **실행하지 말고 stamp만** 해. 안 그러면 "테이블이 이미 존재합니다" 에러.

```bash
cd backend
uv run alembic stamp 0001_baseline
```

이 명령은 DB에 `alembic_version`이라는 테이블을 만들고 `0001_baseline` 값을 넣어 — 즉 "이 시점부터 추적 시작" 표시.

### (B) DB가 비어 있거나 처음부터 다시 가도 됨

→ 그냥 적용.

```bash
cd backend
uv run alembic upgrade head
```

3개 테이블이 새로 만들어지고 `alembic_version`에 `0001_baseline` 저장됨.

## 7. 한 번 더 체크할 만한 것들

- **`alembic_version` 테이블**은 Alembic이 자동으로 만들어 — DB의 현재 revision을 저장하는 작은 테이블 한 개. 절대 수동으로 건드리지 마.
- **autogenerate는 신뢰하지 말고 항상 review해.** Postgres ENUM, server_default, index 이름 등은 잘 못 잡아.
- **운영 적용 타이밍** — 우리는 컨테이너 3개(app/bot/monitor)가 같이 뜨는 구조라, 마이그레이션은 **앱 시작 직전 한 번**만 돌려야 함. 예) docker-compose에 별도 `migrate` 일회성 service를 추가하거나 entrypoint에서 lock 잡고 1번만 실행. 일단은 **수동으로** `alembic upgrade head` 돌리는 걸 추천 — 자동화는 나중에.
- **production downgrade는 거의 안 함** — `downgrade()`는 로컬 개발/CI에서나 쓰지, prod에선 forward-only가 안전. 데이터 손실 위험이 크니까.
