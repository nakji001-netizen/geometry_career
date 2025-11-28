import streamlit as st
import google.generativeai as genai
import json
import time

# 1. 페이지 설정 (제목, 아이콘, 레이아웃)
st.set_page_config(
    page_title="AI 진로 탐색기",
    page_icon="🎓",
    layout="centered"
)

# 2. 스타일링 (CSS 주입 - 카드 디자인 등)
st.markdown("""
<style>
    .header-box {
        background-color: #2563eb;
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .card {
        background-color: #f8fafc;
        border-left: 5px solid #3b82f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .tag {
        display: inline-block;
        background-color: #dcfce7;
        color: #166534;
        padding: 0.2rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.85rem;
        margin-right: 0.3rem;
        margin-bottom: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

# 3. 헤더 영역
st.markdown("""
<div class="header-box">
    <h1 style='margin:0; font-size:2rem; font-weight:bold;'>🎓 고등학생 진로 탐색기</h1>
    <p style='margin-top:0.5rem; opacity:0.9;'>AI가 당신의 관심사와 적성을 분석해 딱 맞는 학과를 추천해드립니다.</p>
</div>
""", unsafe_allow_html=True)

# 4. 입력 폼 생성
with st.form("career_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        job = st.text_input("희망 직업", placeholder="예: 데이터 분석가, PD")
        hobby = st.text_input("취미 및 특기", placeholder="예: 유튜브 시청, 수학 문제 풀기")
        
    with col2:
        interest = st.text_input("관심 분야", placeholder="예: 인공지능, 영상 편집")
        subject = st.text_input("선호 과목", placeholder="예: 확률과 통계, 영어")
    
    st.markdown("---")
    
    # API 키 입력 (비밀번호 형태)
    api_key_input = st.text_input(
        "Google Gemini API 키", 
        type="password", 
        placeholder="여기에 API 키를 입력하세요 (저장되지 않습니다)",
        help="https://aistudio.google.com/app/apikey 에서 발급 가능"
    )
    
    submit_btn = st.form_submit_button("✨ AI에게 학과 추천받기", use_container_width=True)

# 5. 로직 처리
if submit_btn:
    if not api_key_input:
        st.error("⚠️ API 키를 입력해주세요!")
    elif not (job and interest and hobby and subject):
        st.warning("⚠️ 모든 항목을 입력해주세요!")
    else:
        # Gemini 설정
        try:
            genai.configure(api_key=api_key_input)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # [수정됨] 프롬프트 구성: JSON 구조를 명확히 지정
            user_prompt = f"""
            학생 정보:
            - 희망 직업: {job}
            - 관심 분야: {interest}
            - 취미/특기: {hobby}
            - 선호 과목: {subject}
            
            이 학생에게 적합한 대학교 학과 3개를 추천해줘.
            
            [중요] 응답은 반드시 'recommendations'라는 최상위 키를 가진 JSON 객체여야 해.
            'recommendations' 리스트 안의 각 항목은 다음 필드를 가져야 함:
            - majorName (학과명)
            - introduction (한 줄 소개)
            - reason (추천 이유)
            - curriculum (주요 과목 3~4개 문자열 배열)
            - career (진출 분야 3~4개 문자열 배열)
            """
            
            # JSON 응답을 강제하기 위한 설정
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json"
            )

            with st.spinner("AI가 당신의 진로를 분석하고 있습니다... 🧠"):
                response = model.generate_content(
                    user_prompt, 
                    generation_config=generation_config
                )
                
                # [수정됨] 결과 파싱 로직 강화
                try:
                    parsed_json = json.loads(response.text)
                    
                    # 1. 딕셔너리이고 'recommendations' 키가 있는 경우 (정상 케이스)
                    if isinstance(parsed_json, dict) and "recommendations" in parsed_json:
                        result_data = parsed_json["recommendations"]
                    # 2. 리스트 자체가 반환된 경우
                    elif isinstance(parsed_json, list):
                        result_data = parsed_json
                    # 3. 딕셔너리지만 키 이름이 다른 경우 (내부 값에서 리스트 탐색)
                    elif isinstance(parsed_json, dict):
                        found_list = False
                        for val in parsed_json.values():
                            if isinstance(val, list):
                                result_data = val
                                found_list = True
                                break
                        if not found_list:
                            result_data = [] # 리스트를 못 찾음
                    else:
                        result_data = []

                except json.JSONDecodeError:
                    st.error("AI 응답을 해석하는 데 실패했습니다. 다시 시도해주세요.")
                    result_data = []

            # 6. 결과 화면 출력
            if result_data:
                st.subheader("🔍 분석 결과")
                
                # 텍스트 저장용 변수
                txt_content = "[AI 고등학생 진로 탐색 결과]\n\n"
                
                for idx, item in enumerate(result_data):
                    # 데이터 안전하게 가져오기 (.get 사용)
                    major_name = item.get('majorName', '학과명 없음')
                    intro = item.get('introduction', '')
                    reason = item.get('reason', '')
                    curriculum = item.get('curriculum', [])
                    career = item.get('career', [])

                    # 텍스트 파일 내용 추가
                    txt_content += f"====================================\n"
                    txt_content += f"NO.{idx + 1}  {major_name}\n"
                    txt_content += f"====================================\n"
                    txt_content += f"1. 학과 소개: {intro}\n"
                    txt_content += f"2. 추천 이유: {reason}\n"
                    txt_content += f"3. 주요 과목: {', '.join(curriculum)}\n"
                    txt_content += f"4. 졸업 후 진로: {', '.join(career)}\n\n"

                    # 화면에 카드 형태로 표시
                    curriculum_tags = "".join([f"<span class='tag'>{c}</span>" for c in curriculum])
                    career_text = ", ".join(career)
                    
                    st.markdown(f"""
                    <div class="card">
                        <div style="display:flex; align-items:center; margin-bottom:10px;">
                            <span style="background:#dbeafe; color:#1e40af; padding:2px 8px; border-radius:4px; font-size:0.8em; font-weight:bold; margin-right:10px;">추천 {idx + 1}</span>
                            <h3 style="margin:0; color:#1e293b;">{major_name}</h3>
                        </div>
                        <p style="color:#4b5563; font-style:italic; margin-bottom:15px;">"{intro}"</p>
                        
                        <div style="background:white; padding:15px; border-radius:5px; border:1px solid #e2e8f0; margin-bottom:10px;">
                            <strong style="color:#2563eb;">💡 추천 이유</strong>
                            <p style="margin-top:5px; color:#334155;">{reason}</p>
                        </div>
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                            <div style="background:white; padding:15px; border-radius:5px; border:1px solid #e2e8f0;">
                                <strong style="color:#16a34a;">📚 주요 커리큘럼</strong>
                                <div style="margin-top:8px;">{curriculum_tags}</div>
                            </div>
                            <div style="background:white; padding:15px; border-radius:5px; border:1px solid #e2e8f0;">
                                <strong style="color:#9333ea;">🚀 졸업 후 진로</strong>
                                <p style="margin-top:5px; font-size:0.9em; color:#334155;">{career_text}</p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # 7. 다운로드 버튼
                st.download_button(
                    label="📥 결과 저장하기 (.txt)",
                    data=txt_content,
                    file_name=f