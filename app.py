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

# --- 3. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # [의도 분석 키워드]
        category_kw = ["폰", "아이폰", "패드", "아이패드", "워치", "맥북", "노트북"]
        action_kw = ["추천", "가성비", "가격", "재고", "얼마", "저렴", "싼", "있어", "보여줘", "등급"]
        purpose_kw = ["촬영", "유튜브", "게임", "인강", "세컨", "운동", "필기", "공부", "업무"]
        
        # 1. 의미 있는 질문인지 판단 (핵심 로직)
        is_meaningful = any(kw in q_clean for kw in (category_kw + action_kw + purpose_kw))
        # 2. 너무 짧거나 자음뿐인 경우 제외
        is_too_short = len(q_clean) < 2 and not any(kw in q_clean for kw in category_kw)

        response = ""
        final_df = None

        # [상황 A] 못 알아들을 말인 경우 -> 가이드 제시
        if not is_meaningful or is_too_short:
            response = """고객님, 죄송하지만 말씀하신 내용을 제가 잘 이해하지 못했어요. 😅  
            보상나라 점장님에게 **이렇게 물어보시면** 딱 맞는 제품을 찾아드릴 수 있습니다!
            
            ---
            **💡 점장님 추천 질문 리스트**
            1. "입문용으로 좋은 **저렴한 아이패드** 있어?" 📝
            2. "사진 잘 나오는 **아이폰 15 Pro** 재고 확인해줘" 📸
            3. "운동할 때 쓸 **가성비 애플워치** 추천해줘" ⌚
            4. "보상나라 **등급 기준**이 어떻게 돼?" 📋
            ---
            찾으시는 모델이나 용도를 조금 더 자세히 말씀해 주시겠어요?"""
            st.session_state.waiting_for_purpose = False

        # [상황 B] 제대로 된 질문인 경우 -> 제품 추천 진행
        else:
            with st.spinner("장부를 확인하고 있습니다..."):
                # 카테고리 업데이트
                if any(kw in q_clean for kw in ["워치", "애플워치"]): st.session_state.last_category = "애플워치"
                elif any(kw in q_clean for kw in ["폰", "아이폰"]): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in ["맥북", "노트북"]): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in ["패드", "아이패드"]): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 재고 검색
                search_word = user_input.split()[0]
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)]
                
                has_actual_stock = not target_stock.empty
                stock_result = target_stock.head(2) if has_actual_stock else cat_df.head(2)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라' 점장이야. 
                [규칙]
                1. 엑셀 정보를 그대로 읽지 말고 전문가로서 '이유'를 덧붙여 추천해.
                2. 재고 유무(has_actual_stock={has_actual_stock})를 정확히 반영해.
                3. 고객이 이미 말한 용도는 다시 묻지 마. 
                4. "카테고리:", "상품명:" 같은 단어 쓰지 마. 자연스러운 대화문으로 답해.
                
                [재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']]
                
                # 용도 질문 여부
                user_stated_purpose = any(kw in q_clean for kw in purpose_kw)
                if not user_stated_purpose:
                    response += "  \n\n**고객님, 생각하시는 용도를 말씀해 주시면 더 정확한 추천이 가능합니다!**"
                    st.session_state.waiting_for_purpose = True

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
