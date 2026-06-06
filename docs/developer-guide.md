# MatchVision 개발자 가이드

## 프로젝트 구조

```text
Football-Game-Analyzer/
├─ Analyzer/              # OpenCV/YOLO 분석 파이프라인
│  ├─ detector/           # YOLO 탐지, 팀 색상 분류
│  ├─ tracker/            # track ID 유지 및 역할 잠금
│  ├─ topview/            # homography, 앵커 선택, 탑뷰 좌표 변환
│  ├─ pipeline/           # 프레임 단위 분석 실행
│  ├─ visualizer/         # 결과 영상 오버레이
│  └─ tests/              # 분석기 단위 테스트
├─ fotmob_cralwer/        # FotMob 경기 정보/통계/라인업 크롤러
├─ web/                   # Django 웹 애플리케이션
│  ├─ analyzer/           # 업로드, 분석 실행, 리포트 기능
│  └─ config/             # Django 설정
└─ docs/                  # 개발 문서
```

## 로컬 실행

```powershell
cd C:\Users\User\Football\Football-Game-Analyzer\web
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py runserver
```

분석기는 웹에서 실행할 수도 있고, CLI로 직접 실행할 수도 있습니다.

```powershell
cd C:\Users\User\Football\Football-Game-Analyzer
.\venv\Scripts\python.exe .\Analyzer\main.py .\web\media\videos\sample.mp4
```

CLI 실행 시에도 OpenCV 창에서 보정 프레임, 경기장 앵커, 홈팀/원정팀/심판 샘플을 선택해야 합니다.

## 분석 파이프라인

1. `Analyzer/main.py`
   - 영상 선택
   - 보정 프레임 선택
   - 경기장 앵커 포인트 선택
   - 홈팀/원정팀/심판 샘플 선택
   - `VideoPipeline` 실행

2. `Analyzer/pipeline/video_pipeline.py`
   - 프레임 읽기
   - YOLO 탐지
   - 필드 내부 객체 필터링
   - 팀/심판 분류
   - ByteTracker 업데이트
   - track 역할 잠금 및 후처리
   - 탑뷰 좌표 변환
   - 결과 영상 저장
   - 팀별 track ID JSON 저장

3. `web/analyzer/services/analyzer_runner.py`
   - 웹에서 `Analyzer/main.py`를 subprocess로 실행
   - 분석 로그 저장
   - 결과 영상을 `web/media/analysis_results/`로 복사/변환
   - `team_ids.json`을 리포트에 연결

## 주요 데이터 계약

탐지 결과 dict는 다음 형식을 유지합니다.

```python
{
    "bbox": [x1, y1, x2, y2],
    "class": "person" | "sports ball",
    "conf": float,
    "role": "our_team" | "opponent" | "referee" | "unknown" | "sports ball",
}
```

트래킹 결과 dict는 다음 필드를 추가로 가집니다.

```python
{
    "id": int,
    "locked_role": str | None,
    "role_confidence": float,
    "role_votes": dict,
    "lost": int,
    "hits": int,
    "predicted": bool,
}
```

리포트용 팀 ID 파일은 `Analyzer/result/{video_stem}_team_ids.json`에 저장됩니다.

```json
{
  "home_ids": [{"id": 1, "frames": 120}],
  "away_ids": [{"id": 2, "frames": 118}],
  "referee_ids": [{"id": 3, "frames": 80}],
  "unknown_ids": []
}
```

## FotMob 연동

`fotmob_cralwer/main.py`는 FotMob 경기 페이지에서 다음 정보를 수집합니다.

- 홈팀/원정팀 이름
- 스코어
- 점유율, xG, 슈팅, 패스, 코너킥, 오프사이드
- 홈팀/원정팀 선발 명단
- 홈팀/원정팀 교체 명단

웹 리포트에서는 `web/analyzer/services/fotmob_report.py`가 이 JSON을 읽어 홈팀 ID에는 홈팀 선수 목록만, 원정팀 ID에는 원정팀 선수 목록만 보여줍니다.

## 테스트와 검증

현재 `pytest`가 기본 venv에 없을 수 있으므로, 최소 검증은 다음 명령으로 수행합니다.

```powershell
cd C:\Users\User\Football\Football-Game-Analyzer
.\venv\Scripts\python.exe -m py_compile .\Analyzer\main.py .\Analyzer\pipeline\video_pipeline.py .\Analyzer\tracker\bytetrack.py .\Analyzer\detector\classifier.py
cd web
..\venv\Scripts\python.exe manage.py check
```

`pytest`를 설치한 환경에서는 다음 테스트를 실행합니다.

```powershell
cd C:\Users\User\Football\Football-Game-Analyzer
.\venv\Scripts\python.exe -m pytest .\Analyzer\tests
```

## Git 관리 기준

다음 파일은 실행 중 생성되는 산출물이므로 Git에 올리지 않습니다.

- `Analyzer/result/`
- `web/media/`
- `web/db.sqlite3`
- `Analyzer/data/`
- 모델 가중치 파일: `*.pt`, `*.pth`, `*.onnx`, `*.weights`

기능 변경은 가능한 작은 단위로 커밋합니다.

- 분석기 후처리 변경
- 탑뷰 보정 변경
- 웹 리포트 변경
- 문서 정리

이런 식으로 나누면 성능이 나빠졌을 때 되돌리기 쉽습니다.

## 알려진 한계

- 방송 카메라 컷 전환이 잦으면 homography 추적이 끊길 수 있습니다.
- 유니폼 색이 비슷하면 팀 분류가 흔들릴 수 있습니다.
- 선수 가림이 심하면 track ID가 바뀔 수 있습니다.
- 현재 평가는 주로 결과 영상 확인에 의존하며, 정량 지표는 아직 부족합니다.

향후 개선 우선순위는 ID switch 수, 팀 분류 정확도, 탑뷰 좌표 오차, 처리 FPS 같은 정량 평가 지표를 추가하는 것입니다.
