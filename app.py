import streamlit as st
import google.generativeai as genai
import json
import time
import requests
import threading

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
@st.cache_data(show_spinner=False, ttl=86400)
def get_best_flash_model():
    """최신 모델 탐색 및 기억"""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_models = sorted([
            m.replace("models/", "") 
            for m in available_models 
            if 'flash' in m.lower() and 'lite' not in m.lower() and 'exp' not in m.lower()
        ])
        if flash_models:
            return flash_models[-1]
        return "gemini-1.5-flash-latest"
    except Exception:
        return "gemini-1.5-flash-latest"

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
    generation_config = {
        "response_mime_type": "application/json",
        "response_schema": {
            "type": "object",
            "properties": {
                "connection": {"type": "string"}, "example": {"type": "string"}, "advice": {"type": "string"}
            },
            "required": ["connection", "example", "advice"]
        }
    }
    model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
    prompt = f"기하 과목의 '{topic}' 개념이 대학교 '{major}' 전공에서 어떻게 활용되는지 LaTeX를 포함해 분석해줘."
    
    max_retries = 3
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
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

if st.button("✨ 연결고리 분석하기"):
    if not api_key:
        st.error("API Key가 필요합니다.")
    elif not (student_id.strip() and student_name.strip() and selected_major.strip()):
        st.warning("⚠️ 모든 정보를 입력해주세요!")
    else:
        with st.spinner("학문적 연결고리를 분석 중..."):
            try:
                res = get_ai_analysis(selected_model_name, selected_topic, selected_major)
                if webhook_url:
                    payload = {
                        "student_id": student_id, "student_name": student_name, "unit_cat": unit_cat,
                        "topic": selected_topic, "major": selected_major, "connection": res['connection'],
                        "example": res['example'], "advice": res['advice']
                    }
                    save_to_google_sheet_background(webhook_url, payload)
                    st.toast("✅ 결과 전송 중!", icon="🚀")

                st.markdown(f"### 📍 {selected_topic} X {selected_major}")
                with st.container(border=True):
                    st.markdown("#### 🔍 학문적 연결고리")
                    st.markdown(res['connection'])
                    st.divider()
                    st.markdown("#### 🛠️ 실제 활용 사례")
                    st.markdown(res['example'])
                    st.divider()
                    st.markdown("#### 🌟 선배로서의 조언")
                    st.info(f"*{res['advice']}*")
                
                # 풍선 효과
                st.balloons()
                
                download_text = f"[{selected_topic} x {selected_major} 분석 보고서]\n\n1. 대단원: {unit_cat}\n2. 소단원: {selected_topic}\n3. 연결성: {res['connection']}\n4. 사례: {res['example']}\n5. 조언: {res['advice']}"
                st.download_button("📄 결과 다운로드", data=download_text, file_name=f"{selected_major}_분석.txt")
                
            except Exception as e:
                st.error(f"분석 중 오류: {e}")
