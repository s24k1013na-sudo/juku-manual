import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client

# --- 1. セキュリティ設定 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("塾の合言葉を入力してください", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("合言葉が違います。", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        st.error("😕 パスワードが正しくありません")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. クライアント初期化 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"初期化エラー: {e}")
    st.stop()

tab1, tab2 = st.tabs(["💬 AIチャット", "📝 マニュアル管理"])

with tab1:
    st.title("🤖 塾バイト・マニュアルAI")
    
    try:
        res = supabase.table("manual").select("*").execute()
        manual_content = "\n".join([f"・{i['keyword']}: {i['content']}" for i in res.data]) if res.data else "マニュアルは未登録です。"
    except:
        manual_content = "マニュアル取得に失敗しました。"

    # 【重要】通信エラーを避けるため、システム命令を普通のテキストとして定義
    prompt_header = f"あなたは塾の先輩です。以下のマニュアルに従って回答してください。\n\n{manual_content}\n\n質問に対して、マニュアルに基づき回答を開始してください。\n"

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です！何かあれば聞いてください。"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_input := st.chat_input("質問を入力..."):
        st.chat_message("user").write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            try:
                # 通信エラー（404 v1beta）を避けるための最もシンプルな設定
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # システム命令をユーザーの質問の直前に「合体」させて送る（これなら古いSDKでも動く）
                combined_input = f"{prompt_header}\n\nユーザーの質問: {user_input}"
                
                # 履歴を使わず、毎回マニュアルを含めて送る（確実性を優先）
                response = model.generate_content(combined_input, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"AI応答エラーが発生しました。GoogleのAPIキーや設定を確認してください。\nエラー詳細: {e}")

# --- Tab2 のマニュアル追加処理 ---
with tab2:
    st.header("📝 マニュアルの追加")
    with st.form("add_manual"):
        k = st.text_input("キーワード")
        c = st.text_area("内容")
        if st.form_submit_button("登録"):
            if k and c:
                supabase.table("manual").insert({"keyword": k, "content": c}).execute()
                st.success("登録しました！")
                st.rerun()