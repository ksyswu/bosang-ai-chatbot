import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 데이터 로드 ---
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

# --- 2. 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 3. 사이드바 ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("- **S 등급**: 신품급! 🎁  \n- **A 등급**: 미세 흔적 ✨  \n- **B 등급**: 생활 기스 💯")

# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 4. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # 키워드 분류
        watch_kw, phone_kw = ["워치", "애플워치"], ["폰", "아이폰"]
        mac_kw, pad_kw = ["맥북", "노트북"], ["패드", "아이패드"]
        trade_kw = ["추천", "가성비", "가격", "있어", "재고", "얼마", "저렴", "싼"]
        purpose_kw = ["유튜브", "게임", "작업", "인강", "일상", "촬영", "세컨", "운동", "필기"]

        user_already_stated_purpose = any(kw in user_input for kw in purpose_kw)
        is_recommend_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_reply = st.session_state.waiting_for_purpose and len(q_clean) >= 2

        response = ""
        final_df = None

        if is_recommend_talk or is_reply or len(q_clean) >= 2:
            with st.spinner("점장님이 장부를 확인 중입니다..."):
                if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
                elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
                elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                search_word = user_input.split()[0]
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)]
                
                has_actual_stock = not target_stock.empty
                stock_result = target_stock.head(3) if has_actual_stock else cat_df.head(3)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                # [전문가용 프롬프트: 큐레이션 강화]
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [상담 원칙]
                1. 엑셀의 '점장 큐레이션' 문구를 그대로 복사해서 나열하지 마. 그 내용을 바탕으로 왜 추천하는지 "전문가적인 이유"를 덧붙여서 문장으로 말해.
                2. 답변에 "카테고리: ", "상품명 (정제형): " 같은 데이터 필드명을 절대 노출하지 마. 자연스러운 대화문으로 작성해.
                3. 모델명, 등급, 가격 정보는 문장 중간에 자연스럽게 언급하거나 마지막에 요약해줘.
                4. 재고가 없으면(has_actual_stock={has_actual_stock}) 솔직하게 말하고 대체제를 추천해.
                5. 한자 금지, 줄바꿈 공백 2개 준수.
                
                [재고 정보]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.3 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                # 표에 들어갈 정보는 정제해서 보여줌
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']]
                
                if not user_already_stated_purpose and not is_reply:
                    response += "  \n\n**고객님, 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 더 딱 맞는 모델을 추천해 드릴게요!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        if not response:
            response = "어이쿠 고객님! 제가 답변 드리기 어렵네요 😅 제품 추천이나 등급이 궁금하시면 말씀해 주세요!"

        st.markdown(response)
        if final_df is not None:
            # 상세 정보는 표로 깔끔하게 정리 (텍스트 중복 방지)
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df) 
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
