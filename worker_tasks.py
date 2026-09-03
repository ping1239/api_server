import os
import shutil
import time
import subprocess
import requests

BASE_CASE_DIR = "./base_case"
JOBS_DIR = "./jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

def modify_openfoam_dict(filepath: str, replacements: dict):
    """
    OpenFOAM 텍스트 파일을 열어서 딕셔너리의 키에 해당하는 문자열을 값으로 치환합니다.
    """
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    for key, value in replacements.items():
        content = content.replace(key, str(value))
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def run_simulation(job_id: str, parameters: dict, db: dict):
    """
    OpenFOAM 해석 파이프라인 뼈대 코드
    나중에 주석(TODO) 처리된 부분을 해제하고 실제 코드로 채워넣으시면 됩니다.
    """
    job_dir = os.path.join(JOBS_DIR, job_id)
    
    try:
        # 1. 준비 단계 (Base Case 복사 및 파라미터 적용)
        db[job_id]["status"] = "PREPARING"
        db[job_id]["progress"] = 10
        print(f"[{job_id}] 템플릿 복사 및 파라미터 적용 중...")
        
        # TODO 1: Base Case 복사 (주석 해제 완료)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        shutil.copytree(BASE_CASE_DIR, job_dir)
        
        # STL 파일 이동 로직
        temp_stl_path = parameters.get("_temp_stl_path")
        if temp_stl_path and os.path.exists(temp_stl_path):
            trisurface_dir = os.path.join(job_dir, "constant", "triSurface")
            os.makedirs(trisurface_dir, exist_ok=True)
            dest_stl_path = os.path.join(trisurface_dir, "product.stl")
            shutil.move(temp_stl_path, dest_stl_path)
            print(f"[{job_id}] STL 파일 저장 완료: {dest_stl_path}")
        
        # JSON 데이터를 OpenFOAM 플레이스홀더에 맞게 가공
        bounds = parameters.get("boundary_conditions", {})
        proc_cond = parameters.get("process_conditions", {})
        materials = parameters.get("materials", {})
        solver_ctrl = parameters.get("solver_control", {})
        
        # 🌟 속도 계산 로직 (유량 / 단면적)
        gate_info = bounds.get("gate", {})
        gate_shape = gate_info.get("shape", "circular")
        
        import math
        if gate_shape == "rectangular":
            w = gate_info.get("width_mm", 5.0) / 1000.0
            t = gate_info.get("thickness_mm", 1.5) / 1000.0
            gate_area = w * t
        else:
            gate_dia = gate_info.get("diameter_mm", 2.5)
            gate_area = math.pi * ((gate_dia / 1000.0) / 2.0)**2
            
        flow_rate_m3_s = proc_cond.get("flow_rate_cm3_s", 20) * 1e-6
        velocity_m_s = flow_rate_m3_s / gate_area if gate_area > 0 else 0
        
        # 기획서(PDF) 검증 조건: 계산된 단면적과 유속 로그 출력
        print(f"[{job_id}] Gate Shape: {gate_shape}, Area: {gate_area:.8f} m^2, Velocity: {velocity_m_s:.2f} m/s")
        
        # 벤트 크기 추출 (추후 snappyHexMesh 등 3D 바운더리 박스 설정 대비)
        vent_info = bounds.get("vent", {})
        vent_width = vent_info.get("width_mm", 5.0)
        vent_depth = vent_info.get("depth_mm", 0.02)
        
        resin = materials.get("resin", {}).get("properties", {})
        
        replacements = {
            # 0/T
            "REPLACE_MELT_TEMPERATURE_K": proc_cond.get("melt_temperature_C", 200) + 273.15,
            "REPLACE_MOLD_TEMPERATURE_K": proc_cond.get("mold_temperature_C", 50) + 273.15,
            # 0/U
            "REPLACE_INJECTION_SPEED_M_S": velocity_m_s,
            # 0/p
            "REPLACE_HOLDING_PRESSURE_PA": 0,
            
            # constant/thermophysicalProperties
            "REPLACE_DENSITY": resin.get("density_kg_m3", 1000),
            "REPLACE_SPECIFIC_HEAT": resin.get("specific_heat_J_kgK", 1500),
            "REPLACE_THERMAL_CONDUCTIVITY": resin.get("thermal_conductivity_W_mK", 0.2),
            
            # constant/transportProperties
            "REPLACE_TRANSITION_TEMPERATURE_K": resin.get("transition_temperature_C", 130) + 273.15,
            "REPLACE_NO_FLOW_TEMPERATURE_K": resin.get("no_flow_temperature_C", 110) + 273.15,
            "REPLACE_CROSS_WLF_N": resin.get("cross_wlf_n", 0.35),
            "REPLACE_CROSS_WLF_TAU_PA": resin.get("cross_wlf_tau_pa", 20000),
            
            # system/controlDict
            "REPLACE_END_TIME": solver_ctrl.get("end_time", 2.0),
            
            # system/snappyHexMeshDict (임시 Boundary 생성용)
            "REPLACE_GATE_X": bounds.get("gate", {}).get("position", {}).get("x", 0),
            "REPLACE_GATE_Y": bounds.get("gate", {}).get("position", {}).get("y", 0),
            "REPLACE_GATE_Z": bounds.get("gate", {}).get("position", {}).get("z", 0),
            "REPLACE_VENT_X": bounds.get("vent", {}).get("position", {}).get("x", 0),
            "REPLACE_VENT_Y": bounds.get("vent", {}).get("position", {}).get("y", 0),
            "REPLACE_VENT_Z": bounds.get("vent", {}).get("position", {}).get("z", 0),
            "REPLACE_VENT_WIDTH": vent_width,
            "REPLACE_VENT_DEPTH": vent_depth,
            "REPLACE_GATE_SHAPE": gate_shape,
        }
        
        # TODO 2: 파라미터에 맞게 파일 내용 수정 (주석 해제 완료)
        modify_openfoam_dict(os.path.join(job_dir, "0", "T"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "0", "U"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "0", "p"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "constant", "thermophysicalProperties"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "constant", "transportProperties"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "system", "controlDict"), replacements)
        modify_openfoam_dict(os.path.join(job_dir, "system", "snappyHexMeshDict"), replacements)
        
        time.sleep(2) # Mock 지연
        
        # 2. 메쉬(Mesh) 생성 단계
        db[job_id]["status"] = "RUNNING_MESH"
        db[job_id]["progress"] = 30
        print(f"[{job_id}] OpenFOAM blockMesh/snappyHexMesh 실행 중...")
        
        # TODO 3: 메쉬 생성 프로세스 호출
        # subprocess.run(["blockMesh"], cwd=job_dir, check=True)
        # subprocess.run(["snappyHexMesh", "-overwrite"], cwd=job_dir, check=True)
        
        time.sleep(3) # Mock 지연
        
        # 3. 솔버(Solver) 해석 단계
        db[job_id]["status"] = "RUNNING_SOLVER"
        db[job_id]["progress"] = 50
        print(f"[{job_id}] OpenFOAM 솔버 실행 중...")
        
        # TODO 4: 실제 솔버 실행 (예: simpleFoam)
        # subprocess.run(["simpleFoam"], cwd=job_dir, check=True)
        
        time.sleep(5) # Mock 지연
        
        # 4. 후처리 단계
        db[job_id]["status"] = "POST_PROCESSING"
        db[job_id]["progress"] = 90
        print(f"[{job_id}] ParaView / 후처리 데이터 추출 중...")
        
        # TODO 5: pvpython 등 후처리 스크립트 실행
        # subprocess.run(["pvpython", "extract_heatmap.py"], cwd=job_dir, check=True)
        
        time.sleep(2) # Mock 지연
        
        # 결과 파일 경로 모의 처리 (실제로는 후처리 스크립트가 생성)
        dummy_result_path = os.path.join(job_dir, "heatmap.png")
        with open(dummy_result_path, "w") as f:
            f.write("Dummy Image Content")
            
        # 5. 완료
        db[job_id]["status"] = "COMPLETED"
        
        # PDF 기획서에 맞춘 풍부한 더미 결과 데이터 생성
        result_data = {
            "simulation_id": job_id,
            "status": "completed",
            "summary": {
                "fill_percent": 98.4,
                "fill_time_s": 0.417,
                "max_pressure_mpa": 81.3,
                "min_temperature_c": 174.2,
                "max_temperature_c": proc_cond.get("melt_temperature_C", 220.0), # 입력값 연동
                "max_shear_rate_1_s": 11830
            },
            "heatmaps": {
                "fill": f"/results/{job_id}/fill.vtu",
                "pressure": f"/results/{job_id}/pressure.vtu",
                "temperature": f"/results/{job_id}/temperature.vtu",
                "shear": f"/results/{job_id}/shear.vtu"
            }
        }
        
        # 🌟 [웹훅 발송 부분] 메인 서버로 결과 전송!
        # JSON에 webhook_url이 없으면 기본 주소(프론트엔드 포트 등)로 쏘도록 fallback 설정
        webhook_url = parameters.get("webhook_url", "http://localhost:5174/api/webhook") 
        
        if webhook_url:
            try:
                requests.post(webhook_url, json=result_data, timeout=5)
                print(f"[{job_id}] 메인 서버({webhook_url})로 완료 알림(Webhook) 전송 성공!")
            except Exception as e:
                print(f"[{job_id}] 웹훅 전송 실패 (서버가 켜져있지 않거나 주소가 다름): {e}")
                
        db[job_id]["progress"] = 100
        db[job_id]["results"] = result_data
        print(f"[{job_id}] 전체 시뮬레이션 완료 및 결과 생성 끝!")

        
    except subprocess.CalledProcessError as e:
        # OpenFOAM 명령어 실행 실패 시 잡아내는 예외 처리
        db[job_id]["status"] = "FAILED"
        db[job_id]["error_log"] = f"Command Failed: {e.cmd}, Output: {e.output}"
        print(f"[{job_id}] 프로세스 오류 발생: {e}")
    except Exception as e:
        db[job_id]["status"] = "FAILED"
        db[job_id]["error_log"] = str(e)
        print(f"[{job_id}] 기타 오류 발생: {e}")


