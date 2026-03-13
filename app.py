import streamlit as st
import google.generativeai as genai
import time

# 1. 페이지 설정
st.set_page_config(page_title="기하-전공 연결고리 탐색기", page_icon="🔗", layout="centered")

# --- 스타일 설정 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 데이터 정의 ---
GEOMETRY_UNITS = {
    "I. 이차곡선": ["포물선의 방정식", "타원의 방정식", "쌍곡선의 방정식", "이차곡선의 접선"],
    "II. 평면벡터": ["벡터의 덧셈과 뺄셈", "벡터의 실수배", "위치벡터", "평면벡터의 성분", "평면벡터의 내적", "직선과 원의 방정식(벡터 활용)"],
    "III. 공간도형과 공간좌표": ["직선과 평면의 위치 관계", "삼수선의 정리", "정사영", "공간좌표", "구의 방정식"]
}

# --- 로직 함수 ---

def setup_genai():
    """API 키 설정 및 구성"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("🔑 API 키가 설정되지 않았습니다. Streamlit Secrets를 확인해주세요.")
        st.stop()
    genai.configure(api_key=api_key)
    return api_key

@st.cache_data(ttl=3600)
def get_valid_models(_api_key):
    """사용 가능한 최신 모델 목록을 동적으로 가져옴 (버전 변화 대응)"""
    try:
        # 생성 가능한 전체 모델 목록 불러오기
        models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 'flash' 모델 중 실험버전(exp)을 제외하고, 최신 버전이 앞에 오도록 내림차순 정렬
        flash_models = sorted([m for m in models if "flash" in m.lower() and "exp" not in m.lower()], reverse=True)
        # 나머지 모델 (pro 등)도 정렬
        other_models = sorted([m for m in models if "flash" not in m.lower() and "exp" not in m.lower()], reverse=True)
        
        # Flash 최신 모델이 리스트의 맨 첫 번째(기본값)가 되도록 합치기
        return flash_models + other_models
    except Exception:
        # 에러 시 기본 안전망 반환
        return ["gemini-2.5-flash"] 

@st.cache_data(show_spinner=False)
def get_ai_analysis(model_name, topic, major):
    """
    AI 분석 요청 (캐싱 적용: 동일한 질문은 API를 다시 쓰지 않음)
    429 에러 발생 시 지수 백오프(재시도) 로직 포함
    """
    model = genai.GenerativeModel(model_name)
    prompt = f"""
    고등학교 수학 '기하' 과목의 '{topic}' 개념이 대학교 '{major}' 전공 과목이나 연구 분야에서 어떻게 활용되는지 설명해줘.
    1. 실제 전공 도서나 실무에서 쓰이는 구체적인 사례를 들어줘.
    2. 고등학생이 이해하기 쉽게 친절하고 격려하는 어조로 작성해줘.
    3. 300자 내외의 한 문단으로 작성해줘.
    """
    
    max_retries = 3
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) and i < max_retries - 1:
                time.sleep(5 * (i + 1))  # 재시도 대기 시간 증가
                continue
            else:
                raise e

# --- UI 레이아웃 ---

st.title("🔗 기하-전공 연결고리 탐색기")
st.info("선택한 기하 개념이 희망 전공에서 어떻게 살아 움직이는지 확인해보세요!")

# API 세팅 및 모델 목록 가져오기
api_key = setup_genai()
available_models = get_valid_models(api_key)

with st.sidebar:
    st.header("⚙️ 설정")
    selected_model = st.selectbox(
        "AI 모델 선택", 
        available_models, 
        help="목록의 첫 번째 모델이 현재 사용 가능한 가장 최신 Flash 모델입니다."
    )
    st.caption("※ 429 오류 발생 시 Flash 모델 사용을 권장합니다.")

# 입력 섹션
col1, col2 = st.columns(2)
with col1:
    unit_cat = st.selectbox("대단원", list(GEOMETRY_UNITS.keys()))
with col2:
    selected_topic = st.selectbox("소단원", GEOMETRY_UNITS[unit_cat])

selected_major = st.text_input("희망 전공 (예: 자동차공학과, AI학과, 건축학과)", placeholder="전공명을 입력하세요")

# 결과 출력
if st.button("✨ 연결고리 분석하기"):
    if not selected_major:
        st.warning("먼저 희망 전공을 입력해주세요!")
    else:
        with st.spinner(f"AI({selected_model})가 학문적 연결고리를 찾는 중..."):
            try:
                result = get_ai_analysis(selected_model, selected_topic, selected_major)
                
                st.subheader(f"📍 {selected_topic} × {selected_major}")
                st.success(result)
                
                st.divider()
                st.balloons()
                
            except Exception as e:
                if "429" in str(e):
                    st.error("🚀 현재 사용자가 많아 API 요청 한도를 초과했습니다. 잠시 후 다시 시도하시거나, 왼쪽 사이드바에서 다른 모델을 선택해 보세요.")
                else:
                    st.error(f"알 수 없는 오류가 발생했습니다: {e}")

st.caption("본 서비스는 Google Gemini AI를 활용하여 생성된 답변을 제공합니다.")
