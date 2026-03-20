import streamlit as st
import google.generativeai as genai
import json
import time

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="기하-전공 연결고리 탐색기", page_icon="🔗", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; background-color: #2563eb; color: white; }
    /* 기존 HTML 카드 대신 Streamlit 기본 컨테이너의 테두리를 꾸미는 CSS */
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 0.8rem; border-left: 5px solid #2563eb; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 정의 ---
GEOMETRY_UNITS = {
    "I. 이차곡선": ["포물선의 방정식", "타원의 방정식", "쌍곡선의 방정식", "이차곡선의 접선"],
    "II. 평면벡터": ["벡터의 덧셈과 뺄셈", "벡터의 실수배", "위치벡터", "평면벡터의 성분", "평면벡터의 내적", "직선과 원의 방정식(벡터 활용)"],
    "III. 공간도형과 공간좌표": ["직선과 평면의 위치 관계", "삼수선의 정리", "정사영", "공간좌표", "구의 방정식"]
}

# --- 3. 로직 함수 ---

def setup_genai():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("🔑 API 키가 설정되지 않았습니다. Streamlit Secrets를 확인해주세요.")
        st.stop()
    genai.configure(api_key=api_key)
    return api_key

@st.cache_data(ttl=3600)
def get_valid_models(_api_key):
    """모델 목록을 가져오고 최신 Flash 모델을 우선순위로 정렬"""
    try:
        models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_models = sorted([m for m in models if "flash" in m.lower() and "exp" not in m.lower()], reverse=True)
        other_models = sorted([m for m in models if "flash" not in m.lower() and "exp" not in m.lower()], reverse=True)
        
        results = flash_models + other_models
        # 잘림(Syntax Error) 오류 해결 및 Fallback 최신화 완료
        return results if results else ["gemini-2.5-flash"]
    except Exception:
        return ["gemini-2.5-flash"]

# 동일한 전공/소단원 검색 시 API 호출 낭비를 막는 캐싱 기능
@st.cache_data(show_spinner=False, ttl=86400) 
def get_ai_analysis(model_name, topic, major):
    """응답 스키마를 적용하여 일관된 JSON 출력 보장"""
    
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
            # 안전 필터에 걸려 텍스트가 없을 경우 예외 처리
            if not response.text:
                raise ValueError("AI가 콘텐츠 정책에 의해 답변 생성을 차단했습니다.")
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e) and i < max_retries - 1:
                time.sleep(3 * (i + 1))
                continue
            else:
                raise e

# --- 4. UI 레이아웃 ---

st.title("🔗 기하-전공 연결고리 탐색기")
st.info("선택한 기하 개념이 희망 전공에서 어떻게 살아 움직이는지 확인해보세요!")

api_key = setup_genai()
available_models = get_valid_models(api_key)

with st.sidebar:
    st.header("⚙️ 설정")
    selected_model = st.selectbox(
        "AI 모델 선택", 
        available_models, 
        help="목록 상단의 모델이 최신 Flash 모델입니다."
    )
    st.caption("※ 응답 속도가 빠른 Flash 모델을 권장합니다.")

col1, col2 = st.columns(2)
with col1:
    unit_cat = st.selectbox("📂 대단원 선택", list(GEOMETRY_UNITS.keys()))
with col2:
    selected_topic = st.selectbox("📍 소단원 선택", GEOMETRY_UNITS[unit_cat])

selected_major = st.text_input("🎓 희망 전공 (예: 자동차공학과, AI학과, 건축학과)", placeholder="전공명을 입력하세요")

# --- 5. 결과 출력 ---
if st.button("✨ 연결고리 분석하기"):
    if not selected_major:
        st.warning("먼저 희망 전공을 입력해주세요!")
    else:
        with st.spinner(f"AI({selected_model})가 학문적 연결고리를 분석 중..."):
            try:
                res = get_ai_analysis(selected_model, selected_topic, selected_major)
                
                st.markdown(f"### 📍 {selected_topic} <small>X</small> {selected_major}", unsafe_allow_html=True)
                
                # HTML 렌더링 대신 Streamlit 컨테이너를 사용하여 LaTeX 수식 깨짐 방지
                with st.container(border=True):
                    st.markdown("#### 🔍 학문적 연결고리")
                    st.markdown(res['connection'])
                    st.divider()
                    
                    st.markdown("#### 🛠️ 실제 활용 사례")
                    st.markdown(res['example'])
                    st.divider()
                    
                    st.markdown("#### 🌟 선배로서의 조언")
                    st.info(f"*{res['advice']}*")
                
                # 다운로드 텍스트 준비
                download_text = f"[{selected_topic} x {selected_major} 분석 보고서]\n\n" \
                                f"1. 연결성: {res['connection']}\n\n" \
                                f"2. 활용사례: {res['example']}\n\n" \
                                f"3. 조언: {res['advice']}"
                
                st.download_button("📄 결과 텍스트 다운로드", data=download_text, file_name=f"{selected_major}_분석.txt")
                st.balloons()
                
            except ValueError as ve:
                st.error(f"⚠️ {ve}")
            except Exception as e:
                if "429" in str(e):
                    st.error("🚀 현재 요청이 너무 많습니다. 잠시 후 다시 시도하시거나 다른 모델을 선택해 주세요.")
                else:
                    st.error(f"분석 중 오류가 발생했습니다: {e}")

st.divider()
st.caption("본 서비스는 Google Gemini AI를 활용하여 생성된 답변을 제공하며, 수식에는 LaTeX가 사용될 수 있습니다.")
