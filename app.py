import streamlit as st
import google.generativeai as genai

# 페이지 설정
st.set_page_config(page_title="기하-전공 연결고리 탐색기", page_icon="🔗")

# --- 스타일 및 헤더 ---
st.title("🔗 기하-전공 연결고리 탐색기")
st.markdown("""
고등학교 기하 단원이 대학교 전공에서 어떻게 활용되는지 궁금한가요?  
단원과 희망 전공을 선택하고, 그 **놀라운 연결고리**를 확인해보세요!
""")

# --- 데이터 정의 ---
GEOMETRY_UNITS = {
    "I. 이차곡선": ["포물선의 방정식", "타원의 방정식", "쌍곡선의 방정식", "이차곡선의 접선"],
    "II. 평면벡터": ["벡터의 덧셈과 뺄셈", "벡터의 실수배", "위치벡터", "평면벡터의 성분", "평면벡터의 내적", "직선과 원의 방정식(벡터 활용)"],
    "III. 공간도형과 공간좌표": ["직선과 평면의 위치 관계", "삼수선의 정리", "정사영", "공간좌표", "구의 방정식"]
}

# --- 사이드바: 설정 ---
with st.sidebar:
    st.header("⚙️ 설정")
    
    # API 키 확인 (Streamlit Cloud Secrets에서 가져옴)
    api_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        st.error("API 키가 설정되지 않았습니다. Streamlit Secrets를 확인하세요.")
        st.stop()
    
    # 모델 목록 불러오기 함수
    @st.cache_data(ttl=3600) # 1시간마다 갱신
    def get_available_models(key):
        genai.configure(api_key=key)
        models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m)
            # 최신 버전 순 정렬 (버전 번호 내림차순)
            models.sort(key=lambda x: x.version, reverse=True)
            return models
        except Exception as e:
            st.error(f"모델 목록을 불러오는 중 오류 발생: {e}")
            return []

    models = get_available_models(api_key)
    model_names = [m.name.replace("models/", "") for m in models]
    
    # 기본값 설정 (gemini-1.5-flash가 있으면 그걸로, 아니면 첫 번째)
    default_index = 0
    for i, name in enumerate(model_names):
        if "gemini-1.5-flash" in name:
            default_index = i
            break
            
    selected_model = st.selectbox(
        "사용할 AI 모델", 
        model_names, 
        index=default_index if model_names else 0
    )

# --- 메인 입력 화면 ---
col1, col2 = st.columns(2)

with col1:
    unit_category = st.selectbox("대단원 선택", list(GEOMETRY_UNITS.keys()))

with col2:
    topic = st.selectbox("소단원 선택", GEOMETRY_UNITS[unit_category])

major = st.text_input("희망 학과 입력", placeholder="예: 컴퓨터공학과, 기계공학과, 의예과 등")

# --- 실행 버튼 및 결과 ---
if st.button("✨ 연결고리 찾기!", type="primary"):
    if not major:
        st.warning("⚠️ 희망 학과를 입력해주세요!")
    else:
        with st.spinner(f"AI({selected_model})가 연결고리를 분석 중입니다..."):
            try:
                # Gemini 설정 및 호출
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(selected_model)
                
                prompt = f"""
                고등학교 기하 단원 '{topic}'와 대학교 전공 '{major}'의 연관성을 설명해줘. 
                실제 전공에서 어떻게 활용되는지 구체적인 예시를 들어 200자 내외로 한 문단으로 설명해줘. 
                설명은 친절하고 격려하는 어조로 작성해줘.
                """
                
                response = model.generate_content(prompt)
                
                st.success(f"💡 {major} & {topic}")
                st.write(response.text)
                st.caption(f"Analyzed by {selected_model}")
                
            except Exception as e:
                st.error("오류가 발생했습니다.")
                st.error(e)