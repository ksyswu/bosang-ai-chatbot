import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">전문 점장님이 장부를 확인하여 최적의 기기를 추천해 드립니다. ✨</p>', unsafe_allow_html=True)

# --- 2. 데이터 로드 ---
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

# --- 3. 세션 상태 관리 (맥락 유지의 핵심) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 (등급 기준) ---
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

# --- 5. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 정의
        grade_kw = ["등급", "기준", "상태", "s급", "a급", "b급", "가성비", "진열"]
        product_kw = ["폰", "아이폰", "패드", "아이패드", "워치", "맥북", "노트북"]
        trade_kw = ["추천", "가격", "재고", "얼마", "저렴", "싼", "있어", "팔아", "구매", "매물"]
        purpose_kw = ["촬영", "사진", "유튜브", "게임", "인강", "세컨", "서브", "운동", "필기", "작업", "일상", "들고", "용도"]

        # [의도 분류 로직 보완]
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in trade_kw)
        # 용도 답변 중이거나, 제품/매매/용도 관련 키워드가 하나라도 있으면 유효한 질문으로 판단
        is_meaningful = any(kw in q_clean for kw in (product_kw + trade_kw + purpose_kw + grade_kw)) or st.session_state.waiting_for_purpose
        is_recommend_talk = any(kw in q_clean for kw in (product_kw + trade_kw + purpose_kw)) or st.session_state.waiting_for_purpose

        response = ""
        final_df = None

        # [CASE 1] 등급 문의
        if is_grade_query:
            response = """보상나라의 등급 기준을 안내해 드립니다. 😊  
            
- **S 등급**: 신품급! 선물용 강추! 🎁  
- **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
- **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
- **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
- **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  

찾으시는 모델이 있다면 점장님에게 말씀해 주세요!"""
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 의미 없는 입력 (ㅇㄹ 등) -> 질문 가이드
        elif not is_meaningful:
            response = """고객님, 말씀하신 내용을 제가 잘 이해하지 못했어요. 😅  
            점장님에게 이렇게 물어보시면 재고를 바로 찾아드릴 수 있습니다!
            
---
**💡 점장님 추천 질문 리스트**
1. "사진 잘 나오는 **아이폰 15 Pro** 재고 있어?" 📸
2. "인강용 **저렴한 아이패드** 추천해줘" 📝
3. "보상나라 **등급 기준**이 뭐야?" 📋
---"""
            st.session_state.waiting_for_purpose = False

        # [CASE 3] 제품 추천 및 상담 (맥락 유지 강화)
        elif is_recommend_talk:
            with st.spinner("장부를 확인하고 있습니다..."):
                # 카테고리 고정 및 업데이트
                if any(kw in q_clean for kw in ["워치", "애플워치"]): st.session_state.last_category = "애플워치"
                elif any(kw in q_clean for kw in ["폰", "아이폰"]): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in ["맥북", "노트북"]): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in ["패드", "아이패드"]): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 검색어 추출 (단답형 용도 답변인 경우 이전 검색어 유지)
                search_word = user_input.split()[0] if not st.session_state.waiting_for_purpose else ""
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                
                has_actual_stock = not target_stock.empty
                stock_result = target_stock.head(2) if has_actual_stock else cat_df.head(2)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [상담 원칙]
                1. 고객이 "일상용" 같은 단답형 답변을 했다면, 이전 대화와 연결해서 제품을 계속 추천해.
                2. 우리 등급: S, A, B, 가성비, 진열상품 (이 외 절대 금지)
                3. 재고 정보({stock_list})를 기반으로, 전문가로서 왜 이 모델이 고객의 용도에 맞는지 '이유'를 덧붙여.
                4. 재고가 있다면(has_actual_stock={has_actual_stock}) 확실하게 안내하고, 없을 때만 대체제를 제안해.
                5. 대화체로 친절하게 답하고 필드명(카테고리 등)은 노출하지 마.
                
                [장부 데이터]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.2
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']]
                
                # 용도 질문을 이미 했고, 고객이 답했다면 더 이상 묻지 않음
                if not any(kw in q_clean for kw in purpose_kw) and not st.session_state.waiting_for_purpose:
                    response += "  \n\n**고객님, 구체적으로 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 딱 맞는 모델을 골라드릴게요!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
