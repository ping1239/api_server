# RMS OpenFOAM Reference Result API

이 서버는 완료된 OpenFOAM `dogbone` 케이스를 **읽기 전용**으로 후처리하여 RMS API에 실제 이미지, 동영상, KPI를 제공합니다. 현재 지원 범위는 `reference_result` 모드뿐이며 메쉬 생성과 솔버 실행은 하지 않습니다.

## 처리 흐름

```text
POST /api/simulate
  -> REFERENCE_SELECTED
  -> POST_PROCESSING
  -> VALIDATING_RESULTS
  -> COMPLETED | FAILED
```

- 기준 케이스: `/home/kkwon/rms-injection-sim-cpu/tutorials/demo/dogbone`
- WSL 작업 공간: `/home/kkwon/rms-api-runtime/<simulation_id>`
- Windows 공개 결과: `runtime/results/<simulation_id>`
- 정적 URL: `/results/<simulation_id>/<artifact>`
- 충전 영역: `alpha.poly > 0.5`

서버가 UUID 형식의 `simulation_id`를 생성합니다. `client_job_id`와 업로드 파일명은 경로에 사용하지 않습니다. multipart STL은 기존 클라이언트 호환 목적으로 선택적으로 받을 수 있지만 이 모드에서는 저장하거나 사용하지 않습니다. 요청에서 임의 webhook을 지정하는 기능도 비활성화되어 있습니다.

## 설치와 실행

Windows PowerShell에서:

```powershell
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

WSL `Ubuntu-20.04`에는 다음 실행 파일과 완료된 dogbone 케이스가 있어야 합니다.

- `/opt/openfoam7/etc/bashrc`
- `/opt/paraviewopenfoam56/bin/pvpython`
- `xvfb-run`
- `ffmpeg`, `ffprobe`

환경 변수로 `RMS_RESULTS_ROOT`, `RMS_WSL_DISTRIBUTION`, `RMS_WSL_RUNTIME_ROOT`, `RMS_POST_PROCESS_TIMEOUT_SECONDS`를 조정할 수 있습니다. 기본 후처리 제한 시간은 1800초입니다.

## 요청

`POST /api/simulate`는 `config_json` form 필드를 받으며 202를 반환합니다.

```json
{
  "mode": "reference_result",
  "reference_case": "dogbone",
  "client_job_id": "REQ-001"
}
```

PowerShell 예시:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/simulate `
  -F 'config_json={"mode":"reference_result","reference_case":"dogbone","client_job_id":"REQ-001"}'
```

응답의 `simulation_id`로 상태를 조회합니다.

```text
GET /api/simulation/status/<simulation_id>
```

완료 응답의 `results.heatmaps`, `results.animations`와 전체 목록인 `results.artifacts`에는 다음 HTTP 경로가 들어갑니다.

- `fill_final.png`
- `fill_animation.mp4`
- `pressure_final.png`
- `temperature_final.png`
- `shear_rate_final.png`

`results.summary`의 값은 solver 로그, `checkMesh` 로그, ParaView가 실제 필드에서 계산한 전 시간 범위로부터 생성됩니다. 사용할 수 없는 값은 `null`이며 이유는 `unavailable_reasons`에 기록됩니다. 내부 source case 경로와 체크섬은 공개 상태 응답이 아니라 서버 측 `manifest.json`에만 남습니다.

## 검증

빠른 격리 테스트는 실제 렌더링을 실행하지 않습니다.

```powershell
pytest -q
```

실제 WSL/ParaView 통합 테스트는 약간 오래 걸리므로 명시적으로 켭니다.

```powershell
$env:RMS_RUN_INTEGRATION = '1'
pytest -q -m integration
```

통합 파이프라인은 PNG signature, MP4 container와 양수 duration, 필수 파일 크기, KPI 메타데이터를 모두 검증한 뒤 결과 디렉터리를 원자적으로 공개합니다. 모든 검증이 끝난 뒤에만 상태가 `COMPLETED`로 바뀝니다.
