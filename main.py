from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
import os
import json
import shutil
from fastapi.middleware.cors import CORSMiddleware
from worker_tasks import run_simulation

app = FastAPI(title="OpenFOAM Worker Agent")

# CORS 설정 (프론트엔드 포트 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 메모리 DB (간단한 테스트용)
job_status_db = {}

os.makedirs("temp_uploads", exist_ok=True)

@app.post("/api/simulate", status_code=202)
async def start_simulation(
    background_tasks: BackgroundTasks,
    stl_file: UploadFile = File(...),
    config_json: str = Form(...)
):
    try:
        parameters = json.loads(config_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid config_json")

    job_id = parameters.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id missing in config_json")

    if job_id in job_status_db:
        raise HTTPException(status_code=400, detail="Job ID already exists")

    # 업로드된 STL 파일을 임시 폴더에 저장
    temp_stl_path = f"temp_uploads/{job_id}_{stl_file.filename}"
    with open(temp_stl_path, "wb") as buffer:
        shutil.copyfileobj(stl_file.file, buffer)

    # 1. 상태 초기화
    job_status_db[job_id] = {
        "status": "PENDING",
        "progress": 0,
        "results": None
    }
    
    # 워커에 STL 파일 경로 전달
    parameters["_temp_stl_path"] = temp_stl_path
    
    # 2. 백그라운드 태스크로 해석 작업 던지기 (비동기)
    background_tasks.add_task(run_simulation, job_id, parameters, job_status_db)
    
    return {"message": "Simulation started", "job_id": job_id, "status": "PENDING"}

@app.get("/api/simulation/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in job_status_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status_db[job_id]

@app.get("/")
async def root():
    return {"message": "Worker API is running. Check /docs for Swagger UI."}
