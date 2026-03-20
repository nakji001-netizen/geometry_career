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
        # Fallback 버전을 1.5에서 최신 2.5로 상향 조정
        return results if results else ["gemini-
