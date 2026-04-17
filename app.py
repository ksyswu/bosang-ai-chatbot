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

# --- 3. 세션 상태 관리 (대화 문맥 유지용) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 등급 가이드 (상시 노출) ---
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
if user_input := st.chat_input("질문을 입력하세요! (예: 인강용 아이패드 추천해줘)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [키워드 사전 분류]
        watch_kw = ["워치", "시계", "수영", "운동", "런닝", "심박수", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰", "셀카", "카메라", "전화"]
        mac_kw = ["맥북", "노트북", "랩탑"]
        pad_kw = ["패드", "아이패드", "태블릿", "필기", "드로잉"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "사고", "구매", "저렴", "싼"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]

        # 의도 분류
        is_grade_only = any(kw in q_clean for kw in grade_kw) and not any(kw in user_input for kw in trade_kw)
        is_recommend_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_reply = st.session_state.waiting_for_purpose and len(q_clean) >= 2

        response = ""
        final_df = None

        # --- 상황분석 및 답변 생성 ---
        
        # [CASE 1] 등급 문의 (깔끔한 정보 제공, 용도 질문 생략)
        if is_grade_only:
            response = """보상나라의 등급 기준을 안내해 드립니다! 😊  
            
            * **S 등급**: 신품급! 선물용으로 가장 인기가 많아요. 🎁  
            * **A 등급**: 아주 미세한 사용감만 있는 가성비 원탑! ✨  
            * **B 등급**: 생활 기스가 있지만 기능은 완벽히 작동해요. 💯  
            * **가성비**: 외관 흔적은 좀 있지만 가격이 정말 착해요. 💪  
            
            궁금하신 특정 모델이 있다면 언제든 물어봐 주세요!"""
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 추천/재고/용도 답변 (AI 큐레이션 진행)
        elif is_recommend_talk or is_reply:
            with st.spinner("점장님이 장부를 확인하고 있습니다..."):
                # 카테고리 업데이트
                if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
                elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
                elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 모델명 검색 (용도 답변 시에는 카테고리 전체에서 추천)
                search_word = user_input.split()[0] if not is_reply else ""
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                
                # 결과 제한 (가독성을 위해 3개까지만)
                stock_result = target_stock.head(3) if not target_stock.empty else cat_df.head(3)
                stock_list = stock_result.to_dict('records')
                
                # AI 호출
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 한자를 절대 쓰지 마.
                고객의 말: "{user_input}"
                [지침]
                1. [재고] 리스트에 없는 물건은 추천하지 마.
                2. 찾는 모델이 없으면 "현재 장부에는 없지만 비슷한 대안을 찾아드릴게요"라고 정중히 답해.
                3. 문장 끝에 반드시 공백 2개('  ')를 넣어 강제 줄바꿈을 적용해.
                4. 점장 큐레이션에는 고객의 목적에 맞는 이유를 구체적으로 덧붙여.
                
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
                if not any(kw in user_input for kw in ["용도", "유튜브", "게임", "작업", "인강", "일상"]) and not is_reply:
                    response += "  \n\n**고객님, 주로 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 딱 맞는 모델을 더 정밀하게 추천해 드릴 수 있습니다!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # [CASE 3] 답변 불가 (가이드 메뉴 노출)
        if not response:
            response = """어이쿠, 고객님! 제가 그 부분은 답변이 어려워요 😅  
용도에 맞는 제품 추천이나 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
**💡 이렇게 물어보시면 점장님이 잘 대답해드려요!**
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 뭐야?" 📋
---"""

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
