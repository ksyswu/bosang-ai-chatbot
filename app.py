import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 데이터 로드 함수 (캐싱 적용) ---
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
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return None

df = load_inventory()

# --- 3. 세션 상태 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 등급 가이드 ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# --- 5. 이전 대화 렌더링 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 6. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요! (예: 저렴한 아이폰 있어?)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [키워드 분류]
        watch_kw = ["워치", "시계", "수영", "운동", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰"]
        mac_kw = ["맥북", "노트북", "랩탑"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "사고", "구매", "저렴", "싼", "최저가"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]

        # 의도 분류
        is_grade_only = any(kw in q_clean for kw in grade_kw) and not any(kw in user_input for kw in trade_kw)
        is_recommend_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_reply = st.session_state.waiting_for_purpose and len(q_clean) >= 2

        response = ""
        final_df = None

        # [CASE 1] 등급 문의 (단순 정보 제공)
        if is_grade_only:
            response = """보상나라의 등급 기준을 안내해 드립니다! 😊  
            
            * **S 등급**: 신품급! 선물용으로 가장 인기가 많아요. 🎁  
            * **A 등급**: 미세한 흔적은 있지만 가성비가 훌륭해요. ✨  
            * **B 등급**: 생활 기스가 있지만 기능은 완벽히 작동합니다. 💯  
            * **가성비/진열**: 실속파 고객님들이 가장 선호하는 라인업이에요. 💪  
            
            궁금하신 제품이 있다면 말씀해 주세요!"""
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 추천/재고/가격 문의 (영업 모드)
        elif is_recommend_talk or is_reply:
            with st.spinner("장부를 확인하고 있습니다..."):
                # 카테고리 고정
                if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
                elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
                elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # "저렴" 키워드 시 가격 정렬 로직 추가
                if any(kw in user_input for kw in ["저렴", "싼", "최저가"]):
                    cat_df = cat_df.sort_values(by='판매가', ascending=True)

                # 검색어 필터링
                search_word = user_input.split()[0] if not is_reply else ""
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                
                stock_result = target_stock.head(3) if not target_stock.empty else cat_df.head(3)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라'의 장사 잘하는 베테랑 점장이야. 
                [영업 지침]
                1. 절대로 다른 브랜드(삼성, 갤럭시 등)를 언급하거나 추천하지 마.
                2. 우리 매장 재고 내에서 가장 적절한 모델을 제안해.
                3. "성능이 낮다"는 말 대신 "입문용/가성비로 훌륭하다"는 긍정적 표현을 써. 
                4. 한자를 절대 쓰지 마. 문장 끝에 공백 2개('  ')를 넣어 줄바꿈을 지켜.
                5. [재고 정보]에 있는 물건만 추천해. 리스트에 없는 걸 지어내지 마.

                [재고 정보]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]
                
                # 상담 마무리 질문 (용도를 모를 때만)
                if not any(kw in user_input for kw in ["유튜브", "게임", "작업", "인강", "일상", "촬영"]) and not is_reply:
                    response += "  \n\n**고객님, 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 딱 맞는 모델을 더 정밀하게 추천해 드릴 수 있습니다!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # [CASE 3] 답변 불가 (가이드 메뉴 노출)
        if not response:
            response = """어이쿠, 고객님! 그 부분은 제가 답변 드리기 어렵네요 😅  
용도에 맞는 제품 추천이나 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
**💡 이렇게 물어보시면 점장님이 잘 대답해드려요!**
1. "가장 저렴한 **아이폰** 보여줘" 💰
2. "인강용 가성비 **맥북** 있어?" 💻
3. "보상나라 **등급 기준**이 뭐야?" 📋
---"""

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
