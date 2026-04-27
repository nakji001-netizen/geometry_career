import streamlit as st
import google.generativeai as genai
import json
import time
import requests
import threading
import streamlit.components.v1 as components  # 폭죽 효과를 위한 컴포넌트

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="기하-전공 연결고리 탐색기", page_icon="🔗", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; background-color: #2563eb; color: white; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 0.8rem; border-left: 5px solid #2563eb; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 정의 ---
GEOMETRY_UNITS = {
    "I. 이차곡선": ["1.1.포물선", "1.2.타원", "1.3.쌍곡선", "2.1.이차곡선의 접선의 방정식"],
    "II. 공간도형과 공간좌표": ["1.1.직선과 평면의 위치 관계", "1.2.삼수선의 정리", "1.3.정사영", "2.1.좌표공간", "2.2.선분의 내분점", "2.3.구의 방정식"],
    "III. 벡터": ["1.1.벡터", "1.2.벡터의 덧셈과 뺄셈", "1.3.벡터의 실수배", "2.1.위치벡터", "2.2.벡터의 성분", "2.3.벡터의 내적", "3.1.직선의 방정식", "3.2.평면과 구의 방정식"]
}

# --- 3. 로직 함수 ---

def throw_confetti():
    """자바스크립트를 활용한 화려한 폭죽 효과"""
    components.html(
        """
        <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
        <script>
            confetti({
                particleCount: 150,
                spread: 80,
                origin: { y: 0.6 }
            });
        </script>
        """,
        height=0,
    )

@st.cache_data(show_spinner=False, ttl=86400)
def get_best_flash_model():
    """매번 검색하지 않고 하루에 한 번만 최신 모델을 탐색하여 기억함"""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 'flash' 포함, 'lite' 제외, 'exp' 제외하여 검증된 일반 모델 필터링
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
    """결과를 구글 시트로 전송 (화면 멈춤 없이 백그라운드에서 실행)"""
    def send_request():
        try:
            requests.post(webhook_url, json=payload)
        except Exception:
            pass 
    thread = threading.Thread(target=send_request)
    thread.start()

# --- 4. 사이드바: 시스템 설정 ---
api_key = None
webhook_url = None
selected_model_name = "모델 확인 불가"

with st.sidebar:
    st.header("⚙️ 시스템 설정")
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY")
        webhook_url = st.secrets.get("WEBHOOK_URL_MATH")
        
        if not api_key:
            st.error("⚠️ Secrets에 API 키가 없습니다.")
        else:
            genai.configure(api_key=api_key)
            selected_model_name = get_best_flash_model()
            
            st.success("✅ API 연결 성공")
            st.info(f"🤖 사용 모델: **{selected_model_name}**")
            
        if not webhook_url:
            st.warning("⚠️ 구글 시트 웹훅 URL이 없습니다.")
        else:
            st.success("✅ 구글 시트 연결 성공")
            
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
                "connection": {"type": "string"},
                "example": {"type": "string"},
                "advice": {"type": "string"}
            },
            "required": ["connection", "example", "advice"]
        }
    }
    
    model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
    
    prompt = f"""
    고등학교 수학 '기하' 과목의 '{topic}' 개념이 대학교 '{major}' 전공 분야에서 어떻게 활용되는지 분석해줘.
    수식이나 전문 용어가 포함될 경우 반드시 LaTeX 형식을 사용해줘.
    
    1. connection: 전공과의 학문적 연결성 설명 (한 문단)
    2. example: 실제 전공 도서나 실무에서 쓰이는 구체적인 사례
    3. advice: 해당 전공을 꿈꾸는 고등학생에게 주는 따뜻한 격려
    """
    
    max_retries = 3
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            if not response.text:
                raise ValueError("AI가 콘텐츠를 생성하지 못했습니다.")
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI 응답 분석 오류가 발생했습니다. ({e})")
        except Exception as e:
            if "429" in str(e) and i < max_retries - 1:
                time.sleep(3 * (i + 1))
                continue
            else:
                raise e

# --- 6. UI 레이아웃 및 실행 ---
st.title("🔗 기하-전공 연결고리 탐색기")
st.info("선택한 기하 개념이 희망 전공에서 어떻게 살아 움직이는지 확인해보세요!")

st.markdown("**학생 정보 입력**")
col_info1, col_info2 = st.columns(2)
with col_info1:
    student_id = st.text_input("🔢 학번", placeholder="예: 20101")
with col_info2:
    student_name = st.text_input("👤 이름", placeholder="예: 이순신")

st.markdown("**탐색 주제 설정**")
col1, col2 = st.columns(2)
with col1:
    unit_cat = st.selectbox("📂 대단원 선택", list(GEOMETRY_UNITS.keys()))
with col2:
    selected_topic = st.selectbox("📍 소단원 선택", GEOMETRY_UNITS[unit_cat])

selected_major = st.text_input("🎓 희망 전공", placeholder="예: 자동차공학과, AI학과, 건축학과")

if st.button("✨ 연결고리 분석하기"):
    if not api_key:
        st.error("API Key 설정이 필요합니다. 좌측 사이드바를 확인해주세요.")
    elif not (student_id.strip() and student_name.strip() and selected_major.strip()):
        st.warning("⚠️ 학번, 이름, 희망 전공을 모두 정확히 입력해주세요!")
    else:
        with st.spinner(f"AI({selected_model_name})가 학문적 연결고리를 분석 중..."):
            try:
                res = get_ai_analysis(selected_model_name, selected_topic, selected_major)
                
                # 구글 시트에 자동 저장 로직 (백그라운드)
                if webhook_url:
                    payload = {
                        "student_id": student_id,
                        "student_name": student_name,
                        "unit_cat": unit_cat,  
                        "topic": selected_topic,
                        "major": selected_major,
                        "connection": res['connection'],
                        "example": res['example'],
                        "advice": res['advice']
                    }
                    save_to_google_sheet_background(webhook_url, payload)
                    st.toast("✅ 분석 완료! (결과는 선생님 시트로 안전하게 전송 중입니다)", icon="🚀")

                st.markdown(f"### 📍 {selected_topic} <small>X</small> {selected_major}", unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.markdown("#### 🔍 학문적 연결고리")
                    st.markdown(res['connection'])
                    st.divider()
                    
                    st.markdown("#### 🛠️ 실제 활용 사례")
                    st.markdown(res['example'])
                    st.divider()
                    
                    st.markdown("#### 🌟 선배로서의 조언")
                    st.info(f"*{res['advice']}*")
                
                download_text = f"[{selected_topic} x {selected_major} 분석 보고서]\n\n" \
                                f"1. 대단원: {unit_cat}\n" \
                                f"2. 소단원: {selected_topic}\n\n" \
                                f"3. 연결성: {res['connection']}\n\n" \
                                f"4. 활용사례: {res['example']}\n\n" \
                                f"5. 조언: {res['advice']}"
                
                st.download_button("📄 결과 텍스트 다운로드", data=download_text, file_name=f"{selected_major}_분석.txt")
                
                # 축하 효과: 폭죽 터뜨리기
                throw_confetti()
                
            except ValueError as ve:
                st.error(f"⚠️ {ve}")
            except Exception as e:
                if "429" in str(e):
                    st.error("🚀 현재 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
                else:
                    st.error(f"분석 중 오류가 발생했습니다: {e}")

st.divider()
st.caption("본 서비스는 Google Gemini AI를 활용하여 생성된 답변을 제공하며, 수식에는 LaTeX가 사용될 수 있습니다.")
