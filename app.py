import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #1E1E1E; }
    .sub-title { font-size: 15px; color: #666; margin-bottom: 20px; }
    .stTable { width: 100%; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">장부의 팩트만 정직하게 안내합니다. 확인되지 않은 정보는 절대 지어내지 않습니다. ✨</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 ---
@st.cache_data
def load_inventory():
    file_name = "inventory.xlsx" 
    try:
        df = pd.read_excel(file_name, sheet_name='Sheet1')
        df.columns = [str(c).strip() for c in df.columns]
        df['판매가'] = pd.to_numeric(df['판매가'], errors='coerce').fillna(0)
        df['판매가_표기'] = df['판매가'].apply(lambda x: "{:,}원".format(int(x)))
        if '배터리' in df.columns:
            df['배터리_표기'] = pd.to_numeric(df['배터리'], errors='coerce').apply(
                lambda x: f"{int(x * 100)}%" if pd.notnull(x) and x <= 1 else (f"{int(x)}%" if pd.notnull(x) else "정보없음")
            )
        return df
    except: return None

df = load_inventory()

# --- [3] 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

# --- [4] 사이드바 (등급 기준 원문) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨
- **B 등급**: 생활 기스 있음. 기능은 완벽 💯
- **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪
- **진열상품**: 매장 전시용. 배터리 효율 최상 🚀
    """)

# 이전 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        grade_kw = ["등급", "기준", "상태"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요"]
        context_kw = ["편집", "용도", "사용", "적합", "응", "더", "무게", "배터리", "인강", "학교", "사진", "카메라", "촬영", "영상", "가능", "돼", "어때", "크기", "화면", "인치", "차이", "장점"]

        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_grade_query:
            response = "등급 기준은 왼쪽 사이드바에서 상세히 확인하실 수 있습니다. 😊 찾으시는 기종이 있으신가요?"
            st.session_state.is_in_consult = False
            final_df = None
            
        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 1차 필터링 로직
                if any(kw in q_clean for kw in ["더", "큰", "대화면"]):
                    stock_result = cat_df[cat_df['상품명 (정제형)'].str.contains("12.9|16|15|14|pro", case=False, na=False)].head(2)
                    if stock_result.empty:
                        stock_result = cat_df.sort_values(by='판매가', ascending=False).head(2)
                elif any(kw in q_clean for kw in ["저렴", "싼", "가성비"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    search_word = user_input.split()[0] if len(user_input.split()) > 0 else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [강화된 정직성 지침]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 

                [지능형 답변 가이드라인]
                1. 숫자 거짓말 금지: 무게(kg), 포트 개수, 배터리 시간(시간) 등 장부 엑셀에 명시되지 않은 '구체적인 숫자'는 절대 지어내지 마.
                2. 비교 시 형용사 사용: 장부에 정보가 없는 스펙을 비교할 때는 "에어가 더 가볍다", "프로가 성능이 더 강력하다" 같이 검증된 상식 선에서 형용사로만 설명해.
                3. 재고 기반 상담: 답변의 중심은 언제나 오늘의 실제 재고여야 해. 재고가 없는 모델의 장점을 길게 늘어놓지 마.
                4. 빈말 금지: 예약이나 입고 알림 약속은 시스템상 불가능하므로 절대 언급 금지.
                5. 데이터 노출 금지: '카테고리', '상세모델' 필드명 노출 금지. '상품명 (정제형)'만 사용.
                6. 가독성: 줄바꿈과 이모지를 적절히 사용하여 읽기 쉽게 답해.

                [오늘의 실제 장부 데이터]: {stock_list}
                [상담 카테고리]: {st.session_state.last_category}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.0 # 창의성을 완전히 배제하고 팩트에만 집중
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            response = """찾으시는 제품이 있으신가요? 용도와 함께 말씀해 주시면 장부를 바로 확인해 드릴게요! 😊
            
**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 맥북** 있어?" 💻
- "**아이폰 15 Pro** 재고 확인해줘" 📸
- "보상나라 **등급 기준**이 뭐야?" 📋"""
            st.session_state.is_in_consult = False
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
