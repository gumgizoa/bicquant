# CLAUDE.md

## 리포 구조

uv 워크스페이스: `backend`, `lsapi`(LS증권 OpenAPI 클라이언트), `dartapi`(전자공시 DART 클라이언트), `kofiaapi`(금융투자협회 FreeSIS 통계 클라이언트).

`backend/`는 세 개의 독립 서비스 + 공통 코드로 구성된다.

| 경로 | 역할 |
| --- | --- |
| `backend/app/` | FastAPI 서버 (routers, services) |
| `backend/bot/` | 텔레그램 봇 (`python -m bot.main`), 기능은 `bot/features/`. 정기 리포트(장 시작/마감의 시장 요약·관심종목)도 봇의 JobQueue가 담당한다 |
| `backend/monitor/` | 이벤트 감시/알림 (`python -m monitor.main`) — 사이드카·서킷브레이커(실시간 WS), DART 신규 공시 |
| `backend/shared/` | 세 서비스 공통 코드 (config, db, models, queries) |

docker-compose 서비스: frontend, backend, telegram-bot, monitor, postgres, migrate.
`archive/`와 `parallels/`는 린트/포맷 대상에서 제외된 보관용 디렉토리다.

## shared vs 서비스 로컬 (중요)

`backend/shared/`에는 **여러 서비스에 걸쳐 공통으로 쓰이면서, 성격상 shared에 둘 만한 코드만** 넣는다.

"2개 이상 서비스에서 쓰인다고 해서 반드시 shared로 분류되는 것은 아니다. 코드의 *성격*이 우선이며, 성격이 안 맞으면 여러 서비스가 쓰더라도 shared로 올리지 말고 **중복을 감수**한다.

실제 사례 — 텔레그램 메시지 포맷/발송은 `monitor/notifier.py`와 `bot/features/*_report.py` + `bot.main`에 **의도적으로 중복** 존재한다. 두 서비스가 모두 텔레그램으로 보내지만, 알림 문구는 각 서비스의 도메인에 밀착된 코드라 shared로 올리지 않는다.

- 서비스 전용 기능은 그 서비스 안에 둔다 (예: 봇 전용 기능 → `bot/features/<name>.py`).
- feature 모듈은 순수 도메인 로직만 담는다. 데이터 페치나 텔레그램 핸들러 같은 서비스 글루는 `bot/main.py`에 둔다 (feature에 client를 주입하는 식의 억지 결합 금지).
- 서비스 간 역방향 의존(예: `monitor` → `bot` import)은 금지.
- shared 후보가 생기면 "이게 shared에 둘 성격인가?"를 먼저 판단하고, 애매하면 서비스 로컬(+중복 허용) 쪽을 택하거나 유저에게 확인을 위한 질의를 한다.

## 설정과 자격증명

- 서비스 설정은 `shared.config.get_config(service)`로 로드한다. 이 함수가 `.env`를 `os.environ`에 올리고 `backend/config/properties.yaml` + `config/<service>/default.yaml` + `config/<service>/<APP_ENV>.yaml`을 OmegaConf로 머지한다.
- 비밀값은 `properties.yaml`에서 `${oc.env:VAR}` 인터폴레이션으로 주입한다 (예: `ls_api.app_key: ${oc.env:LS_OPENAPI_APP_KEY}`). **코드에 하드코딩하지 않는다.**
- `.env` 변수명 규칙: `LS_OPENAPI_APP_KEY` / `LS_OPENAPI_APP_SECRET` / `LS_OPENAPI_USER_ID`. lsapi의 `LSConfig.from_env`(`_ENV_NAMES`)도 같은 이름을 읽는다.
- 클라이언트에 키를 넘길 때는 `cfg.ls_api.app_key`처럼 config에서 꺼내 명시적으로 전달한다. 무인자 `LSClient()` 폴백에 의존하지 않는다.

## 테스트와 린트

```bash
uv run pytest                 # 전체 스위트 (pre-push 게이트와 동일, 라이브 포함)
uv run pytest -m "not slow"   # 오프라인 스위트 (CI 게이트와 동일)
uv run pytest -m slow         # 라이브 테스트만 (실 서비스 + 자격증명 필요)
PYTHONPATH=backend uv run python ...   # ad-hoc 스크립트 실행 시
```

- 라이브 테스트(LS API / DART / KOFIA / DB / 텔레그램)는 `@pytest.mark.slow`로 마킹한다. **pre-push는 전체를 돌리고**(로컬엔 `.env`가 있다), **CI는 `-m "not slow"`만 돌린다**(러너엔 자격증명이 없다). 즉 라이브가 자동으로 검증되는 지점은 pre-push 하나뿐이므로, `--no-verify`로 우회하면 라이브 커버리지가 통째로 사라진다.
- pre-push에서 라이브가 도는 대가로, push할 때마다 텔레그램 dev 챗에 리포트가 발송되고 실 DB에 테스트 행이 쓰인다. 외부 API 장애 시 코드가 멀쩡해도 push가 막힐 수 있다.
- 순수 로직 테스트는 외부 설정 없이 import/실행돼야 한다. `bot.main`은 import 시점에 Azure LLM·텔레그램 config를 초기화하므로, 파일 상단에서 import하지 말고 라이브 테스트 함수 안에서 **지연 import**한다.
- 라이브 테스트는 `conftest.py`의 픽스처(`ls_client`, `live_db`, `dart`, `telegram`)로 서비스 가용성을 게이트하고, 없으면 `pytest.skip`.
- 새 기능은 순수 함수 단위 테스트 + 라이브(slow) 테스트를 함께 추가한다.
- pytest는 `pythonpath` 설정으로 `backend`를 잡지만, 단독 스크립트 실행은 `PYTHONPATH=backend`가 필요하다.
- **pre-commit 훅(ruff, ruff-format)을 `--no-verify`로 우회하지 않는다.** ruff-format이 파일을 재정렬하면 다시 `git add` 후 재커밋. 라인 길이는 150(E501).

## 브랜치 전략

git-flow: `feature/*` → `develop` → (PR) → `main`.

- 새 작업은 항상 `feature/*`에서 시작한다. `develop`/`main`을 직접 수정하지 않는다 (hotfix 예외).
- feature에서 구현 + 테스트 통과 후 `develop`에 머지한다 (`/land`). 머지된 feature 브랜치는 삭제한다.
- `main` 반영은 PR 흐름으로 한다 (`/ship` = 현재 브랜치 → main via `gh pr create` + `gh pr merge`). main은 릴리스 라인이라 리뷰 흔적이 남아야 한다.
- **push는 명시적으로 지시할 때만 한다.**
