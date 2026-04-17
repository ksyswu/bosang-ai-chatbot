import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 (기존 유지) ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    .stTable { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">정직한 점장님이 끝까지 책임지는 상담! 장부의 실재고만 정확히 추천합니다. ✨</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 (기존 유지) ---
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

# --- [3] 세션 상태 관리 (맥락 유지의 핵심) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False # 상담 중인지 여부

# --- [4] 사이드바 (등급 기준 고정) ---
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
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 (보완 완료) ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 체계화
        grade_kw = ["등급", "기준", "상태"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        # 상담 지속 및 구체화 키워드
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "금액", "가격", "있어", "있나요"]
        context_kw = ["편집", "용도", "사용", "적합", "맞아", "응", "어", "괜찮", "좋아", "가능", "수도", "더", "무게", "배터리"]

        # [의도 판단 로직]
        # 1. 등급만 묻는 경우
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        
        # 2. 제품 추천 또는 대화 지속 상황
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        response = ""
        final_df = None

        if is_grade_query:
            response = "보상나라의 등급 기준입니다! 😊\n\n- **S 등급**: 신품급\n- **A 등급**: 가성비 최고\n- **B 등급**: 실속형\n- **가성비/진열**: 실속파 최선택\n\n원하시는 모델이 있으신가요?"
            st.session_state.is_in_consult = False

        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부를 확인하고 있습니다..."):
                # 카테고리 고정 및 업데이트
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 정렬 및 필터링
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    search_word = user_input.split()[0] if len(user_input.split()) > 0 else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라' 점장이야. 
                [상담 절대 원칙]
                1. 팩트 중시: 출시된 제품(아이폰 17 등)은 "매장 장부에 없다"고 정직하게 말해. 절대 "출시 전"이라 거짓말하지 마.
                2. 맥락 유지: 고객이 "편집도 가능해?"라고 물으면, 이전 대화에서 말한 {st.session_state.last_category}를 주어로 삼아 답변해.
                3. 자연스러운 문체: "~은 적합합니다" 같은 로봇 말투 금지. "편집도 거뜬하죠", "가벼워서 들고 다니기 딱입니다" 같은 구어체를 써.
                4. 기계적 마무리 삭제: "관심 있으신가요?" 멘트를 매 답변마다 붙이지 마. 
                5. 재고 일치: 추천하는 기기는 반드시 아래 [실재고 데이터]에 있는 것이어야 해.
                6. 필드명(카테고리:, 판매가:) 노출 금지.
                
                [오늘의 실제 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.4
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)

        else:
            response = """고객님, 말씀하신 내용을 점장님이 이해하지 못했어요. 😅  
            
**💡 점장님에게 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 맥북** 있어?" 💻
- "**아이폰 15 Pro** 재고 확인해줘" 📸
- "보상나라 **등급 기준**이 뭐야?" 📋"""
            st.session_state.is_in_consult = False

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
