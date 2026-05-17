import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client

# --- セキュリティ設定（合言葉） ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("塾の合言葉を入力してください", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("合言葉が違います。もう一度入力してください", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        st.error("😕 パスワードが正しくありません")
        return False
    return True

if not check_password():
    st.stop()

# --- 各種クライアントの初期化 ---
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"初期化エラー: {e}")
    st.stop()

# --- タブ切り替え ---
tab1, tab2 = st.tabs(["💬 AIチャット", "📝 マニュアル追加・一覧"])

with tab1:
    st.title("🤖 塾バイト・マニュアルAI")
    try:
        response = supabase.table("manual").select("*").execute()
        db_data = response.data
        manual_items = [f"・{item['keyword']}: {item['content']}" for item in db_data]
        MANUAL_TEXT = "\n".join(manual_items) if manual_items else "現在マニュアルは登録されていません。"
    except Exception as e:
        st.error(f"DB連携エラー: {e}")
        st.stop()

    SYSTEM_INSTRUCTION = f"あなたは塾の先輩です。以下のマニュアルに基づき回答してください。\n【塾のマニュアル】\n{MANUAL_TEXT}"

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です！何か分からないことがあれば聞いてくださいね。"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_input := st.chat_input("質問を入力..."):
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            # ここを最新の 2.0-flash に固定！
            res = client.models.generate_content_stream(
                model='gemini-2.0-flash',
                contents=user_input,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
            )
            for chunk in res:
                full_response += chunk.text
                response_placeholder.write(full_response + "▌")
            response_placeholder.write(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

with tab2:
    st.header("📝 マニュアルの追加")
    with st.form("add_form", clear_on_submit=True):
        new_keyword = st.text_input("キーワード")
        new_content = st.text_area("説明文")
        if st.form_submit_button("登録"):
            if new_keyword and new_content:
                supabase.table("manual").insert({"keyword": new_keyword, "content": new_content}).execute()
                st.success("登録完了！")
                st.rerun()