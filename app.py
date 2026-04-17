import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    .stTable { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">정직이 최우선! 보상나라는 실제 보유 중인 재고만 투명하게 안내합니다. ✨</p>', unsafe_allow_html=True)

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

# --- [3] 세션 상태 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- [4] 사이드바 (등급 기준) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 정의
        grade_kw = ["등급", "기준", "상태"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        trade_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "금액", "가격", "있어", "있나요"]

        # 의도 분류
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in trade_kw)
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + trade_kw)) or st.session_state.waiting_for_purpose

        response = ""
        final_df = None

        # CASE 1: 순수 등급 문의
        if is_grade_query:
            response = "보상나라 등급 기준을 안내해 드립니다. 😊\n\n- **S 등급**: 신품급 선물용 🎁\n- **A 등급**: 가성비 최고 ✨\n- **B 등급**: 실속형 💯\n- **가성비/진열**: 가격 혜택 극대화 💪\n\n찾으시는 모델이 있으신가요?"
            st.session_state.waiting_for_purpose = False

        # CASE 2: 제품 추천 및 상담
        elif is_recommend_talk:
            with st.spinner("점장님이 장부를 확인 중입니다..."):
                # 카테고리 업데이트
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # "더 저렴한/가성비" 요청 시 정렬
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가', ascending=True).head(2)
                else:
                    search_word = user_input.split()[0] if not st.session_state.waiting_for_purpose else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [강화된 전문가 프롬프트 - 팩트 체크 및 멘트 정제]
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [상담 원칙]
                1. 팩트 기반 상담: 아이폰 17 등 출시된 모델에 대해 "출시 전"이라는 거짓말을 절대 하지 마. 
                   "현재 저희 매장 장부에는 해당 재고가 없습니다"라고 정직하게 말한 뒤, [실재고]에서 대안을 추천해.
                2. 기계적 멘트 금지: "관심 있으신가요?", "최고의 선택입니다" 같은 상투적인 문구를 남발하지 마. 
                   대신 제품의 특징(배터리 수명, 휴대성 등)을 짚어주며 점장으로서의 의견을 전달해.
                3. 일관성 유지: 텍스트로 추천하는 모델은 반드시 아래 [오늘의 실재고] 데이터에 있는 모델이어야 해.
                4. 가성비 요청 대응: 고객이 더 싼 걸 찾으면, 장부에서 가장 가격이 낮은 모델의 장점을 찾아 설득해.
                5. 필드명(카테고리:, 판매가:) 노출 절대 금지.
                
                [오늘의 실재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)

        # CASE 3: 무의미한 입력 가이드 (누락 복구)
        else:
            response = """고객님, 말씀하신 내용을 점장님이 이해하지 못했어요. 😅  
점장님에게 이렇게 물어보시면 딱 맞는 제품을 바로 찾아드릴 수 있습니다!
            
---
**💡 점장님 추천 질문 리스트**
1. "인강용 **저렴한 맥북** 있어?" 💻
2. "**아이폰 15 Pro** 재고 확인해줘" 📸
3. "보상나라 **등급 기준**이 뭐야?" 📋
---"""

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
