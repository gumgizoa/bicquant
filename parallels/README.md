## 목표
LS증권 HTS "투혼"의 [1892] (KRX)조건검색 화면에서, 과거 360일치 거래일(주말 제외)의 조건검색 결과를 날짜별 xlsx 파일로 자동 저장한다. Open API 미지원이라 GUI 자동화 필요.

## 기본 유저 프로파일
- Mac 환경에서 Parallels Desktop (스탠다드 에디션)으로 Windows 11 VM 운용
- Windows VM에서 LS증권 HTS "투혼" 실행 중
- Python 개발 환경: Mac에 `bicquant` conda 환경, VM에도 동일 경로에 venv 존재
- VM 접속: SSH (paramiko), IP는 prlctl로 동적으로 가져옴
- Parallels 스탠다드 에디션 → `prlctl exec` 명령 사용 불가

## 자동화 플로우 (1날짜 기준)
1. 날짜 필드 옆 ▼ 버튼 클릭 → "오늘기준 N일 전" 입력창 팝업
2. 입력창에 N(= 오늘로부터 며칠 전) 입력 → Enter
3. 빨간 **검색** 버튼 클릭 → 결과 로드 대기 ("검색결과 : X개" 표시 확인)
4. **종목전송** 버튼 클릭 → dropdown에서 **EXCEL** 클릭
5. "다른 이름으로 저장" dialog → 파일명을 `YYYY-MM-DD.xlsx`로 입력 → 저장(S)
6. 다음 날짜로 반복

## 날짜 범위
- 기준일: 2026-05-10 (오늘)
- 시작: 360일 전 = 2025-05-15 (N=360)
- 종료: 오늘 (N=0)
- 주말(토/일) 제외, 약 250 거래일
- 공휴일은 일단 skip (에러 발생 시 그때 처리)
- 초기 테스트: 360일 전 단일 날짜만

## 파일 저장 위치
- Windows VM의 Downloads 폴더
- 기본 파일명 `임시저장.xlsx` → `YYYY-MM-DD.xlsx`로 변경해서 저장

## 현재 상태 (2026-05-10 기준)
- `parallels/src/crawl_tuhon_hts.py` 구현 완료 (실행 가능)
- `parallels/src/bridge.py` 구현 완료
- **diagnose 모드**: [1892] 창 컨트롤 트리 파악 완료
- **다음 단계**: ▼ 클릭 후 나타나는 팝업의 Edit 컨트롤 auto_id 확인 필요
  - diagnose 코드가 ▼를 클릭하고 팝업 구조를 출력하도록 수정됨
  - 출력 결과를 보고 `set_date()` 함수의 edit field 찾는 로직 확정 예정

## 핵심 문제
SSH 세션은 Windows Session 0에서 실행 → 데스크탑(Session 1)의 GUI 창 접근 불가.
pywinauto/pyautogui가 Session 0에서는 아무 창도 못 찾음.

## 시도하고 실패한 방법들
1. **OpenSSH 서비스 로그온 계정 변경** → 오류 1297 (권한 부족), 복잡한 권한 설정 필요
2. **schtasks /create /it + schtasks /run** → "Element not found" 에러
3. **schtasks /create + Start-ScheduledTask** → task 생성은 되나 Python 스크립트가 실행 안 됨 (log 파일 미생성)
4. **prlctl exec** → Parallels 스탠다드 에디션 미지원

## 현재 채택된 방식: Bridge Script
```
Mac (src/crawl_tuhon_hts.py)
  │
  ├─ SSH로 스크립트 파일 작성 (base64 → PowerShell → 파일 저장)
  ├─ SSH로 trigger 파일 작성 (hts_trigger.txt)
  │
  └─ [폴링] SSH로 log/done 파일 읽기 (2초마다)

Windows VM (src/bridge.py) — 인터랙티브 세션에서 수동 실행 중
  │
  └─ trigger 파일 감지 → hts_automation.py 실행 → pywinauto로 HTS 조작
```

## 파일 경로 (VM)
```
VENV_PYTHON    = C:\Users\cho-eungi\eungizoa\bicquant\Scripts\python.exe
REMOTE_SCRIPT  = C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.py
REMOTE_LOG     = C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.log
REMOTE_DONE    = C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.done
REMOTE_TRIGGER = C:\Users\cho-eungi\AppData\Local\Temp\hts_trigger.txt
bridge.py      = C:\Users\cho-eungi\eungizoa\bicquant\parallels\src\bridge.py
```

## 실행 방법
1. VM에서 CMD 열고 bridge 실행 (1회, 세션 유지):
   ```
   C:\Users\cho-eungi\eungizoa\bicquant\Scripts\python.exe C:\Users\cho-eungi\eungizoa\bicquant\parallels\src\bridge.py
   ```
2. Mac에서:
   ```bash
   conda run -n bicquant python parallels/src/crawl_tuhon_hts.py             # 테스트 ('360일 전' 1일 테스트)
   conda run -n bicquant python parallels/src/crawl_tuhon_hts.py --all       # 전체 실행
   conda run -n bicquant python parallels/src/crawl_tuhon_hts.py --diagnose  # 디버그
   ```

## SSH 연결 정보
- IP: prlctl로 동적 조회 (`/usr/local/bin/prlctl list --info "Windows 11"`)
- 인증: .env의 PRL_USERNAME / PRL_PASSWORD
- 현재 확인된 IP: 172.30.1.47 (변경될 수 있음)

## write_script_to_vm 동작 방식
Python 코드를 UTF-8 base64로 인코딩 → PowerShell -EncodedCommand로 VM에 파일 저장
(stdout/stderr를 log 파일로 redirect + finally에서 done 파일 생성하는 wrapper 포함)


## 창 계층 구조
```
Application("LS증권 투혼")  # class='E*Trade XingQ SMart'
  └── main_win = app.window(title="LS증권 투혼")
       └── child = main_win.child_window(title_re=r"\[1892\].*조건검색", control_type="Window")
            # auto_id="65280"
```

## [1892] 창 내부 주요 컨트롤

| 용도 | 타입 | auto_id | 비고 |
|------|------|---------|------|
| 과거시점검색 체크박스 | CheckBox | 4010 | title="과거시점검색" |
| 날짜 컨테이너 Pane | Pane | 10695 | 날짜 Edit + ▼ Button 포함 |
| 날짜 ▼ 드롭다운 버튼 | Button | 20001 | Pane(10695) 자식 |
| 날짜 Edit 필드 | Edit | (미확인) | Pane(10695) 자식, 'Edit2' |
| 종가 컨테이너 Pane | Pane | 10696 | 종가 Edit + ▼ Button 포함 |
| 종가 ▼ 버튼 | Button | 20001 | Pane(10696) 자식 |
| 종가 Edit | Edit | 20000 | Pane(10696) 자식 |
| 빨간 검색 버튼 (섹션3) | Button | 4040 | title="검색", 'Button11' |
| 검색결과 ComboBox | ComboBox | 6390 | "(검색결과 : N개)" 텍스트 표시 |
| 종목전송 버튼 | Button | 4100 | title="종목전송" |
| API보내기 버튼 | Button | 4123 | |
| 전략명 표시 Static | Text | 4120 | title="BIC" |

## 주의사항
- `검색` 버튼이 두 개 존재:
  - auto_id="257": 전략 트리 검색용 (스마트 검색) — 사용 안 함
  - auto_id="4040": 섹션3 빨간 검색 버튼 — 이것을 사용
- win32 backend: RemoteMemoryBlock 관련 pywinauto 버그 발생 → uia backend만 사용
