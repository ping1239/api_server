# OpenFOAM Worker Agent 🚀

이 프로젝트는 RMS(Recipe Management System) 메인 서버의 지시를 받아 **OpenFOAM 기반 유체역학(사출) 시뮬레이션**을 수행하는 워커(Worker) PC용 API 서버의 뼈대(Skeleton) 코드입니다.

현재는 실제 OpenFOAM 명령어 대신 **시간 지연(Mock)**을 통해 상태 변화를 흉내 내고 있으며, 메인 서버와의 비동기 통신(S2S) 파이프라인 테스트를 위해 즉시 사용할 수 있습니다.

---

## 1. 폴더 구조 설명

```text
worker_agent/
├── main.py                  # FastAPI 웹 서버 진입점 (API 라우터)
├── worker_tasks.py          # 백그라운드 작업 파이프라인 (템플릿 복사 및 치환 로직)
├── requirements.txt         # 파이썬 패키지 종속성 목록
├── README.md                # 현재 문서
│
├── base_case/               # OpenFOAM 원본 템플릿 폴더 (수정하지 않는 마스터 파일)
│   ├── 0/                   # 초기 및 경계 조건 (T, U, p 등)
│   ├── constant/            # 물성치 및 메쉬 정보
│   └── system/              # 솔버 제어 (controlDict 등)
│
└── jobs/                    # (자동 생성) API 요청 시 생성되는 격리된 작업 폴더
    ├── REQ-001/
    └── REQ-002/
```

---

## 2. 설치 및 실행 방법

워커 PC (해석을 수행할 로컬 또는 클라우드 서버)에 파이썬(3.8 이상 권장)이 설치되어 있어야 합니다.

1. **라이브러리 설치**
   터미널에서 `worker_agent` 폴더로 이동한 후 아래 명령어를 입력합니다.
   ```bash
   pip install -r requirements.txt
   ```

2. **서버 실행**
   FastAPI 서버를 구동합니다.
   ```bash
   uvicorn main:app --reload
   # 기본적으로 http://127.0.0.1:8000 에서 실행됩니다.
   ```

---

## 3. API 사용 방법 (메인 서버 연동 규격)

브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하시면 Swagger UI를 통해 아래 API들을 직접 테스트해 볼 수 있습니다.

### 3.1. 시뮬레이션 시작 요청 `[POST] /api/simulate`
메인 서버에서 워커로 해석을 지시할 때 호출합니다. (비동기로 즉시 202 응답을 반환합니다)

* **Request Body (JSON):**
  ```json
  {
    "job_id": "REQ-002",
    "recipe_id": "RCP-9942",
    "parameters": {
      "process_conditions": {
        "melt_temperature_C": 230,
        "mold_temperature_C": 60,
        "injection_speed_mm_s": 50
      },
      "material_properties": {
        "density": 1050,
        "viscosity_n": 0.3
      },
      "solver_control": {
        "end_time": 2.5
      }
    }
  }
  ```

### 3.2. 상태 조회 `[GET] /api/status/{job_id}`
메인 서버에서 주기적(Polling)으로 시뮬레이션 진행 상황을 물어볼 때 호출합니다.

* **Response (JSON):**
  ```json
  {
    "status": "RUNNING_SOLVER",
    "progress": 50,
    "results": null,
    "error_log": null
  }
  ```
  *(상태 변화 흐름: `PENDING` ➔ `PREPARING` ➔ `RUNNING_MESH` ➔ `RUNNING_SOLVER` ➔ `POST_PROCESSING` ➔ `COMPLETED` 또는 `FAILED`)*

---

> [!TIP]
> **실제 OpenFOAM 환경으로의 전환 가이드**
> 현재는 `worker_tasks.py` 내부에서 `time.sleep()`을 이용해 실제 해석 시간을 흉내 내고 있습니다. 워커 PC에 OpenFOAM 및 ParaView(pvpython)가 설치 완료되었다면 다음 단계를 따르세요.
> 1. `worker_tasks.py` 파일을 엽니다.
> 2. `# TODO 1` ~ `# TODO 5` 로 마킹된 주석 블록을 찾습니다.
> 3. 해당 블록의 `time.sleep()` 코드를 지우고, 주석 처리되어 있는 `subprocess.run(...)` 명령어들의 주석을 해제합니다.
> 4. 필요시 실행 환경(Docker 사용 여부, WSL2 등)에 맞춰 `subprocess.run` 배열 안의 명령어 문자열을 수정합니다.
