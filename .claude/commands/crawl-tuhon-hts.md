Run the HTS crawl script on the Parallels Windows VM.

```bash
conda run -n bicquant python parallels/src/crawl_tuhon_hts.py $ARGUMENTS
```

## Arguments
- (no args): test mode — 360일 전 단일 날짜
- `--start N --end M`: N일 전부터 M일 전까지 (예: `--start 360 --end 301`)
- `--all`: 360일 전 ~ 오늘 전체
- `--kill`: VM에서 실행 중인 스크립트 강제 종료
- `--diagnose`: 창 구조 디버깅
