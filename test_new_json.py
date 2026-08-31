import requests
import time
import json

url = "http://127.0.0.1:8000/api/simulate"
payload = {
  "job_id": "REQ-003",
  "stl_file_name": "sample_product.stl",
  
  "boundary_conditions": {
    "gate": {
      "position": {"x": 10.5, "y": -5.2, "z": 0.0},
      "diameter_mm": 2.5
    },
    "vent": {
      "position": {"x": -15.0, "y": 8.0, "z": 2.1},
      "diameter_mm": 1.0
    }
  },

  "process_conditions": {
    "flow_rate_cm3_s": 20,
    "melt_temperature_C": 220,
    "mold_temperature_C": 50
  },

  "materials": {
    "resin": {
      "name": "Custom",
      "properties": {
        "density_kg_m3": 780,
        "specific_heat_J_kgK": 2800,
        "thermal_conductivity_W_mK": 0.25,
        "transition_temperature_C": 130,
        "no_flow_temperature_C": 110,
        "cross_wlf_n": 0.35,
        "cross_wlf_tau_pa": 20000
      }
    }
  },

  "solver_control": {
    "end_time": 5.0
  }
}

try:
    print("서버에 시뮬레이션 요청 중...")
    
    # 더미 STL 파일 생성
    dummy_stl_path = "dummy_test.stl"
    with open(dummy_stl_path, "w") as f:
        f.write("solid dummy\n  facet normal 0 0 0\n  endfacet\nendsolid dummy")
        
    with open(dummy_stl_path, "rb") as f:
        files = {"stl_file": ("dummy_test.stl", f, "model/stl")}
        data = {"config_json": json.dumps(payload)}
        
        response = requests.post(url, files=files, data=data)
    
    print("응답 코드:", response.status_code)
    print("응답 내용:", response.json())
    
    if response.status_code == 202:
        for _ in range(5):
            time.sleep(3)
            status_res = requests.get(f"http://127.0.0.1:8000/api/status/REQ-003")
            print("현재 상태:", status_res.json()["status"])
            if status_res.json()["status"] == "COMPLETED":
                break
except Exception as e:
    print("서버가 켜져 있지 않거나 오류 발생:", e)
