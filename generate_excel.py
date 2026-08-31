import csv

data = [
    ["분류", "항목", "상세 내용"],
    ["작업 내역", "워커 에이전트 구축", "FastAPI를 활용하여 메인 서버의 요청을 비동기적으로 처리하는 워커 서버(main.py)의 기본 뼈대를 구축함."],
    ["작업 내역", "가상 시뮬레이션 파이프라인", "OpenFOAM 실행을 모방하는 상태 업데이트 파이프라인 작성 (PREPARING -> RUNNING_MESH -> RUNNING_SOLVER -> COMPLETED)."],
    ["작업 내역", "OpenFOAM 템플릿 세팅", "base_case 내부에 주요 템플릿(T, U, p, thermophysicalProperties 등) 파일 생성 및 JSON 파라미터 텍스트 치환 로직 구현."],
    ["작업 내역", "인코딩 오류 수정", "Windows 환경에서 텍스트 파일 읽기/쓰기 시 발생하는 인코딩 충돌(cp949)을 방지하기 위해 utf-8 인코딩 명시."],
    ["작업 내역", "웹훅(Webhook) 기능 추가", "시뮬레이션 완료 시 워커 PC가 메인 서버로 결과를 역방향으로 전송(POST)하도록 requests 패키지를 활용한 콜백 기능 구현."],
    ["API 통신 원리", "통신 기본 개념", "메인 서버(Client)와 워커 PC(Server)가 네트워크를 통해 규격화된 방식으로 데이터를 주고받기 위한 소프트웨어 간의 연결 창구."],
    ["API 통신 원리", "IP 주소와 포트", "메인 서버가 워커 PC를 찾아가기 위해 워커 PC의 고유 IP 주소와 열려있는 통신 채널(포트, 예: 8000)을 목적지로 접근함."],
    ["API 통신 원리", "엔드포인트(URL 경로)", "워커 PC 내의 특정 기능들을 구분하는 상세 주소. (예: 시뮬레이션 시작 요청은 /api/simulate, 상태 조회는 /api/status)"],
    ["API 통신 원리", "데이터 포맷 (JSON)", "두 시스템이 소통할 수 있도록 시뮬레이션 설정값(온도, 속도 등)을 기계가 파싱하기 쉬운 표준화된 텍스트 양식(JSON)으로 구성하여 전송함."],
    ["API 통신 원리", "HTTP 메서드", "- POST: 메인 서버가 워커 PC에 데이터를 포함하여 새로운 작업을 생성(지시)할 때 사용.\n- GET: 메인 서버가 워커 PC에 현재 진행 상태 데이터를 단순 조회(요청)할 때 사용.\n- 웹훅(POST): 작업이 끝난 워커 PC가 메인 서버로 완료 신호와 결과를 능동적으로 역발송할 때 사용."]
]

# 엑셀(Windows)에서 한글이 깨지지 않도록 utf-8-sig (BOM) 인코딩 사용
file_path = 'C:/Users/a0102/OneDrive/Desktop/advancedfactory/worker_agent/오늘의_작업_요약.csv'
with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("CSV 파일이 성공적으로 생성되었습니다.")
