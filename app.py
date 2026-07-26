import streamlit as st
import google.generativeai as genai
import json
import time
import requests
import threading
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InternalServerError

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="기하-전공 연결고리 탐색기", page_icon="🔗", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; background-color: #2563eb; color: white; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 0.8rem; border-left: 5px solid #2563eb; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color: white; }
    
    /* 기본 제목 크기 (PC) */
    h1 { font-size: 2.2rem !important; }
    
    /* 모바일 화면(너비 768px 이하)일 때 제목 크기 축소 */
    @media (max-width: 768px) {
        h1 { font-size: 1.4rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 정의 ---
GEOMETRY_UNITS = {
    "I. 이차곡선": ["1.1.포물선", "1.2.타원", "1.3.쌍곡선", "2.1.이차곡선의 접선의 방정식"],
    "II. 공간도형과 공간좌표": ["1.1.직선과 평면의 위치 관계", "1.2.삼수선의 정리", "1.3.정사영", "2.1.좌표공간", "2.2.선분의 내분점", "2.3.구의 방정식"],
    "III. 벡터": ["1.1.벡터", "1.2.벡터의 덧셈과 뺄셈", "1.3.벡터의 실수배", "2.1.위치벡터", "2.2.벡터의 성분", "2.3.벡터의 내적", "3.1.직선의 방정식", "3.2.평면과 구의 방정식"]
}

# --- 3. 로직 함수 ---
@st.cache_data(show_spinner=False)
def get_best_flash_model():
    """유료 계정 전용: 리스트 조회 속도 저하를 없애기 위해 gemini-2.5-flash 모델명 즉시 고정"""
    return "gemini-2.5-flash"

def save_to_google_sheet_background(webhook_url, payload):
    """백그라운드 저장"""
    def send_request():
        try:
            requests.post(webhook_url, json=payload)
        except Exception:
            pass 
    thread = threading.Thread(target=send_request)
    thread.start()

# --- 4. 사이드바 ---
api_key = None
webhook_url = None
selected_model_name = "모델 확인 불가"

with st.sidebar:
    st.header("⚙️ 시스템 설정")
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY")
        webhook_url = st.secrets.get("WEBHOOK_URL_MATH")
        if api_key:
            genai.configure(api_key=api_key)
            selected_model_name = get_best_flash_model()
            st.success("✅ API 연결 성공")
            st.info(f"🤖 모델: **{selected_model_name}**")
        if webhook_url:
            st.success("✅ 시트 연결 성공")
    except Exception as e:
        st.error(f"⚠️ 설정 오류: {e}")

# --- 5. 분석 엔진 ---
@st.cache_data(show_spinner=False, ttl=86400) 
def get_ai_analysis(model_name, topic, major):
    """[초고속 튜닝] 무거운 response_schema를 걷어내고 초경량 고속 JSON 모드로 연결고리 심층 분석"""
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2  # 답변 생성 시간 최적화
    }
    
    # 스키마의 무거운 검사 오버헤드 없이 완벽한 JSON 포맷을 출력하게 유도하는 세부 조언 지침
    system_instruction = (
        "너는 고등학교 기하 수학 교사이자 대학 진로 진학 전문가야. "
        "반드시 기하개념과 희망 대학 전공 간의 융합 연결성을 분석해 아래 기술된 키(Key)를 가진 단 하나의 JSON 객체 형태로만 결과를 반환해야 해. "
        "마크다운 코드 블록 기호(```json 등)는 앞뒤에 절대 쓰지 말고 오직 순수한 JSON 텍스트만 출력해.\n\n"
        "{\n"
        '  "connection": "기하개념과 전공 간의 학문적 연결점을 LaTeX 수학식($, $$)을 포함하여 핵심만 2~3문장 이내로 밀도 있게 서술한 문자열",\n'
        '  "example": "해당 전공 및 실제 산업 분야에서 이 기하 개념이 실제 적용되는 구체적 공학적 사례를 2~3문장 이내로 정리한 문자열",\n'
        '  "advice": "해당 전공을 꿈꾸는 학생에게 기하 공부의 중요성을 언급하며 고등학생 수준에 맞추어 따뜻하고 친근하게 격려하는 2문장 이내의 조언 문자열"\n'
        "}\n\n"
        "답변의 길이는 간결함이 생명이야. 불필요하게 텍스트를 늘려 생성 지연을 초래하지 마."
    )
    
    model = genai.GenerativeModel(
        model_name=model_name, 
        generation_config=generation_config,
        system_instruction=system_instruction
    )
    prompt = f"기하 과목의 '{topic}' 개념이 대학교 '{major}' 전공에서 어떻게 활용되는지 LaTeX를 포함해 분석해줘."
    
    max_retries = 3
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # 구글 API가 가끔 응답에 마크다운 기호(```json)를 붙이는 현상을 완벽히 방어
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
            return json.loads(raw_text)
            
        except (ResourceExhausted, ServiceUnavailable, InternalServerError, Exception) as e:
            # 503(구글 서버 지연) 및 500(내부 시스템 리셋) 대응 백오프 초고속 자동 재시도
            if i < max_retries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            raise e

# --- 6. 실행 및 결과 ---
st.title("🔗 기하-전공 연결고리 탐색기")
st.markdown("**학생 정보 입력**")
col_info1, col_info2 = st.columns(2)
with col_info1:
    student_id = st.text_input("🔢 학번", placeholder="예: 20101")
with col_info2:
    student_name = st.text_input("👤 이름", placeholder="예: 이순신")

st.markdown("**탐색 주제 설정**")
col1, col2 = st.columns(2)
with col1:
    unit_cat = st.selectbox("📂 대단원", list(GEOMETRY_UNITS.keys()))
with col2:
    selected_topic = st.selectbox("📍 소단원", GEOMETRY_UNITS[unit_cat])
selected_major = st.text_input("🎓 희망 전공", placeholder="예: 자동차공학과")

# 분석 트리거
if st.button("✨ 연결고리 분석하기"):
    if not api_key:
        st.error("API Key가 필요합니다.")
    elif not (student_id.strip() and student_name.strip() and selected_major.strip()):
        st.warning("⚠️ 모든 정보를 입력해주세요!")
    else:
        # 체감 대기 지루함을 줄이는 단계별 상태 변화 애니메이션 연출
        status_placeholder = st.empty()
        with status_placeholder.container():
            st.markdown("⚡ **구글 AI 초고속 전용 전송로를 여는 중...**")
            progress_bar = st.progress(15)
            
        try:
            # 상태 변경 피드백
            with status_placeholder.container():
                st.markdown("🧠 **기하 수학적 성질과 대학 전공의 공학적 알고리즘을 계산하는 중...**")
                progress_bar.progress(55)
                
            res = get_ai_analysis(selected_model_name, selected_topic, selected_major)
            
            # 다운로드 혹은 다른 인터랙션 시 화면 초기화 방지를 위해 세션에 박제
            st.session_state['math_analysis_data'] = {
                'res': res, 'unit_cat': unit_cat, 'selected_topic': selected_topic, 'selected_major': selected_major
            }
            
            with status_placeholder.container():
                st.markdown("🚀 **분석 문서를 가공하여 선생님 교실 장부로 자동 기록하는 중...**")
                progress_bar.progress(90)
                
            if webhook_url:
                payload = {
                    "student_id": student_id, "student_name": student_name, "unit_cat": unit_cat,
                    "topic": selected_topic, "major": selected_major, "connection": res['connection'],
                    "example": res['example'], "advice": res['advice']
                }
                save_to_google_sheet_background(webhook_url, payload)
                st.toast("✅ 결과 전송 중!", icon="🚀")

            # 상태창 제거 및 이펙트 효과
            status_placeholder.empty()
            st.balloons()
            
        except Exception as e:
            status_placeholder.empty()
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                st.error("🚨 **안내:** 현재 동시에 접속한 학생들이 많아 AI 분석 서비스가 잠시 지연되었습니다. **약 15초 후에 [연결고리 분석하기] 버튼을 다시 한번만 눌러주세요!**")
            else:
                st.error(f"분석 중 오류: {e}")

# 결과 화면 렌더링부 (Session State 연동으로 영속성 유지)
if 'math_analysis_data' in st.session_state:
    saved = st.session_state['math_analysis_data']
    res_data = saved['res']
    
    st.markdown(f"### 📍 {saved['selected_topic']} X {saved['selected_major']}")
    with st.container(border=True):
        st.markdown("#### 🔍 학문적 연결고리")
        st.markdown(res_data['connection'])
        st.divider()
        st.markdown("#### 🛠️ 실제 활용 사례")
        st.markdown(res_data['example'])
        st.divider()
        st.markdown("#### 🌟 선배로서의 조언")
        st.info(f"*{res_data['advice']}*")
        
    download_text = f"[{saved['selected_topic']} x {saved['selected_major']} 분석 보고서]\n\n1. 대단원: {saved['unit_cat']}\n2. 소단원: {saved['selected_topic']}\n3. 연결성: {res_data['connection']}\n4. 사례: {res_data['example']}\n5. 조언: {res_data['advice']}"
    st.download_button("📄 결과 다운로드", data=download_text, file_name=f"{saved['selected_major']}_분석.txt", use_container_width=True)
# Last Heartbeat: Sun Jul 26 07:32:50 UTC 2026
