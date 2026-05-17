import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client

# --- 1. セキュリティ設定 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("塾の合言葉", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        return False
    return st.session_state.get("password_correct", False)

if not check_password():
    st.stop()

# --- 2. クライアント初期化 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"初期化エラー: {e}")
    st.stop()

# --- 3. 【重要】利用可能なモデルを自動特定する関数 ---
def get_available_model():
    try:
        # 使用可能なモデルをリストアップ
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 1. 1.5-flash を探す
        for m in models:
            if 'gemini-1.5-flash' in m: return m
        # 2. なければ 1.0-pro を探す
        for m in models:
            if 'gemini-pro' in m: return m
        # 3. それでもなければ最初に見つかったものを使う
        return models[0] if models else None
    except Exception as e:
        st.error(f"モデル一覧の取得に失敗しました: {e}")
        return 'models/gemini-1.5-flash' # フォールバック

# 適切なモデル名を決定
target_model = get_available_model()

# --- 4. チャット画面 ---
tab1, tab2 = st.tabs(["💬 AIチャット", "📝 マニュアル管理"])

with tab1:
    st.title("🤖 塾バイト・マニュアルAI")
    st.caption(f"使用中モデル: {target_model}") # デバッグ用

    # マニュアル取得
    try:
        res = supabase.table("manual").select("*").execute()
        manual_text = "\n".join([f"・{i['keyword']}: {i['content']}" for i in res.data]) if res.data else "マニュアルなし"
    except:
        manual_text = "マニュアル取得失敗"

    # システム命令（古いバージョン対策で通常のプロンプトに結合する準備）
    instruction = f"あなたは塾の先輩です。以下のマニュアルに基づき回答してください。\n{manual_text}\n\n"

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
                # モデルの初期化（system_instructionを使わない安全な方法）
                model = genai.GenerativeModel(model_name=target_model)
                
                # 入力に命令を合体させる
                combined_query = f"{instruction}ユーザーの質問: {user_input}"
                
                response = model.generate_content(combined_query, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"エラー発生: {e}")

# --- 5. マニュアル追加（Tab2） ---
with tab2:
    st.header("📝 マニュアルの追加")
    with st.form("add_form"):
        k = st.text_input("キーワード")
        c = st.text_area("内容")
        if st.form_submit_button("登録"):
            if k and c:
                supabase.table("manual").insert({"keyword": k, "content": c}).execute()
                st.success("登録完了！")
                st.rerun()