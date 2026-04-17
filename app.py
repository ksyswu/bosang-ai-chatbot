import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 제목 (유실 방지) ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">무엇이든 물어보세요! 점장님이 장부를 확인해 드립니다. ✨</p>', unsafe_allow_html=True)

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

# --- 3. 세션 상태 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 (대표님표 등급 기준 고정) ---
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
        product_kw = ["폰", "아이폰", "패드", "아이패드", "워치", "맥북"]
        trade_kw = ["추천", "가격", "재고", "얼마", "저렴", "싼", "있어"]
        purpose_kw = ["촬영", "유튜브", "게임", "인강", "세컨", "운동", "필기", "작업"]

        # 의도 분류
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in trade_kw)
        is_meaningful = any(kw in q_clean for kw in (product_kw + trade_kw + purpose_kw + grade_kw))
        is_recommend_talk = any(kw in q_clean for kw in (product_kw + trade_kw + purpose_kw))

        response = ""
        final_df = None

        # [CASE 1] 등급 문의 (대표님 요청사항 100% 반영)
        if is_grade_query:
            response = """보상나라의 자부심! 엄격한 등급 기준을 안내해 드립니다. 😊  
            
- **S 등급**: 신품급! 선물용으로 강추드려요! 🎁  
- **A 등급**: 깔끔한 외관에 미세 흔적 정도만 있어요. 가성비 최고! ✨  
- **B 등급**: 생활 기스가 좀 있지만, 기능은 꼼꼼히 검수해 완벽합니다. 💯  
- **가성비**: 찍힘 등 외관 흔적이 있지만 가격이 정말 착한 실속파용! 💪  
- **진열상품**: 매장에서 전시되었던 제품으로, 배터리 효율이 최상급입니다. 🚀  

찾으시는 모델이 있다면 말씀해 주세요. 점장님이 장부를 확인해 드릴게요!"""
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 의미 없는 입력 (ㅇㄹ 등) -> 가이드 제시
        elif not is_meaningful or len(q_clean) < 2:
            response = """고객님, 말씀하신 내용을 제가 잘 이해하지 못했어요. 😅  
            점장님에게 이렇게 물어보시면 딱 맞는 제품을 바로 찾아드릴 수 있습니다!
            
---
**💡 점장님 추천 질문 리스트**
1. "사진 잘 나오는 **아이폰 15 Pro** 재고 있어?" 📸
2. "인강용 **저렴한 아이패드** 추천해줘" 📝
3. "보상나라 **등급 기준**이 뭐야?" 📋
---"""
            st.session_state.waiting_for_purpose = False

        # [CASE 3] 제품 추천 및 상담
        elif is_recommend_talk:
            with st.spinner("점장님이 장부를 확인 중입니다..."):
                if "워치" in q_clean: st.session_state.last_category = "애플워치"
                elif "폰" in q_clean or "아이폰" in q_clean: st.session_state.last_category = "아이폰"
                elif "맥북" in q_clean: st.session_state.last_category = "맥북"
                elif "패드" in q_clean: st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                search_word = user_input.split()[0]
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)]
                
                has_actual_stock = not target_stock.empty
                stock_result = target_stock.head(2) if has_actual_stock else cat_df.head(2)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                # [점장님 큐레이션 로직 강화]
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [상담 가이드라인]
                1. 우리 등급은 [S, A, B, 가성비, 진열상품] 5가지만 존재해. 절대 C급이나 다른 등급을 지어내지 마.
                2. 엑셀의 '점장 큐레이션' 정보를 그대로 읽지 말고, 점장으로서 왜 추천하는지 전문적인 '이유'를 덧붙여서 문장으로 말해. 
                3. 재고 유무(has_actual_stock={has_actual_stock})에 따라 정직하게 안내하고 대안을 제시해.
                4. "카테고리:", "판매가:" 같은 필드명은 노출하지 말고 친절한 대화체로 풀어 써.
                
                [오늘의 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.2 # 정확도를 위해 온도 낮춤
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']]
                
                if not any(kw in q_clean for kw in purpose_kw):
                    response += "  \n\n**고객님, 구체적으로 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 더 딱 맞는 모델을 골라드릴게요!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # 결과 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
