import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# ==========================================
# 1. 系統與頁面設定
# ==========================================
st.set_page_config(page_title="雲端題庫系統", page_icon="📚", layout="wide")

# 🚨 記得把這裡替換成您自己的 Google 試算表完整網址 🚨
SHEET_URL = "請在此貼上您的_Google_試算表完整網址"

# ==========================================
# 2. 功能函數：上傳圖片至 ImgBB
# ==========================================
def upload_to_imgbb(file_bytes, api_key):
    """將圖片上傳至 ImgBB 並回傳直連網址"""
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": api_key}
    files = {"image": file_bytes}
    
    try:
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            return response.json()["data"]["url"]
        else:
            st.error("圖片上傳圖床失敗，請檢查 API Key 或稍後再試！")
            return ""
    except Exception as e:
        st.error(f"上傳發生錯誤：{e}")
        return ""

# ==========================================
# 3. 資料庫連線初始化
# ==========================================
# 自動讀取 secrets.toml 中的 [connections.gsheets] 設定
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10) # 設定快取時間，避免頻繁讀取消耗 API 額度
def load_db():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="Questions")
        return df
    except Exception:
        # 若發生錯誤或表單不存在，建立一個預設的空資料表結構
        return pd.DataFrame(columns=["id", "grade", "unit", "content", "answer", "image_url"])

df = load_db()

# ==========================================
# 4. 側邊欄：功能導覽
# ==========================================
st.sidebar.title("📚 題庫管理選單")
menu = st.sidebar.radio("請選擇功能", ["📥 新增題目", "📋 題庫瀏覽與組卷"])
st.sidebar.divider()
st.sidebar.caption("提示：在手機上可點擊左上角「>」展開選單")

# ==========================================
# 功能一：新增題目 (包含文字與圖片)
# ==========================================
if menu == "📥 新增題目":
    st.title("📥 新增題目至雲端")
    
    # 使用欄位排版節省空間
    col1, col2 = st.columns(2)
    grade = col1.selectbox("適用年級", ["七年級", "八年級", "九年級", "高中", "其他"])
    unit = col2.text_input("單元名稱", placeholder="例如：1-1 數與數線")
    
    # 題目內容與選項一併貼入
    content = st.text_area(
        "題目內容 (請將題目敘述與 ABCD 選項一併貼上)", 
        height=180,
        placeholder="例如：\n計算 5 × (3 + 2) 的值為何？\n(A) 15\n(B) 17\n(C) 25\n(D) 30"
    )
    
    # 獨立解答區與圖片上傳
    col3, col4 = st.columns(2)
    answer = col3.text_input("正確解答", placeholder="例如：C")
    uploaded_file = col4.file_uploader("上傳題目截圖或附圖 (非必填)", type=["png", "jpg", "jpeg"])

    # 送出按鈕與儲存邏輯
    if st.button("💾 儲存至雲端題庫", use_container_width=True):
        if not content.strip() or not answer.strip():
            st.error("⚠️ 請確保填寫「題目內容」與「解答」！")
        elif SHEET_URL == "請在此貼上您的_Google_試算表完整網址":
            st.error("⚠️ 請先在程式碼第 12 行設定您的 Google 試算表網址！")
        else:
            with st.spinner("🚀 正在將資料與圖片同步至雲端，請稍候..."):
                image_url = ""
                # 如果有上傳圖片，先打 API 傳到 ImgBB
                if uploaded_file:
                    api_key = st.secrets["imgbb"]["api_key"]
                    image_url = upload_to_imgbb(uploaded_file.getvalue(), api_key)
                
                # 自動產生新題目的 ID
                new_id = 1
                if not df.empty and pd.notna(df["id"].max()):
                    new_id = int(df["id"].max() + 1)
                
                # 建立要寫入的新資料
                new_row = pd.DataFrame([{
                    "id": new_id,
                    "grade": grade,
                    "unit": unit,
                    "content": content,
                    "answer": answer,
                    "image_url": image_url
                }])
                
                # 將新資料加進舊資料表，並更新回 Google Sheets
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, worksheet="Questions", data=updated_df)
                
                # 清除快取以抓取最新資料
                st.cache_data.clear()
                st.success("✅ 題目已成功存入雲端資料庫！")

# ==========================================
# 功能二：題庫瀏覽、組卷與下載
# ==========================================
elif menu == "📋 題庫瀏覽與組卷":
    st.title("📋 雲端題庫與組卷清單")
    
    # 基礎資料清理：移除完全空白的資料列
    if df.empty or len(df.dropna(subset=['id'])) == 0:
        st.info("💡 目前題庫空空如也，請切換至「新增題目」開始建立您的專屬題庫。")
    elif SHEET_URL == "請在此貼上您的_Google_試算表完整網址":
         st.error("⚠️ 請先在程式碼第 12 行設定您的 Google 試算表網址！")
    else:
        df_clean = df.dropna(subset=['id'])
        
        # 篩選器區塊
        st.subheader("🔍 題目篩選")
        f_col1, f_col2 = st.columns(2)
        
        # 取得資料庫中現有的年級與單元清單
        available_grades = df_clean["grade"].dropna().unique().tolist()
        f_grade = f_col1.multiselect("篩選年級", available_grades)
        
        # 如果有選年級，單元清單就跟著連動
        if f_grade:
            df_filtered = df_clean[df_clean["grade"].isin(f_grade)]
        else:
            df_filtered = df_clean
            
        available_units = df_filtered["unit"].dropna().unique().tolist()
        f_unit = f_col2.multiselect("篩選單元", available_units)
        
        # 執行最終篩選
        if f_unit:
            df_filtered = df_filtered[df_filtered["unit"].isin(f_unit)]
            
        st.caption(f"共找到 **{len(df_filtered)}** 題符合條件的題目")
        st.divider()

        # 顯示題目並提供勾選
        selected_questions = []
        
        for index, row in df_filtered.iterrows():
            with st.expander(f"📌 [ID: {int(row['id'])}] {row['grade']} - {row['unit']}", expanded=False):
                # 題目文字
                st.markdown(str(row['content']).replace('\n', '  \n')) 
                
                # 若有圖片則顯示圖片
                if pd.notna(row.get('image_url')) and str(row['image_url']).strip():
                    st.image(str(row['image_url']), use_container_width=True)
                
                # 勾選框與解答並排顯示
                c1, c2 = st.columns([1, 4])
                is_checked = c1.checkbox("✅ 加入試卷", key=f"chk_{row['id']}")
                c2.success(f"🔑 解答：{row['answer']}")
                
                if is_checked:
                    selected_questions.append(row)

        # 底部：生成試卷預覽與下載
        if selected_questions:
            st.divider()
            st.subheader("📝 試卷預覽與下載")
            
            # 1. 在背景將勾選的題目整理成一大串純文字
            paper_content = "【專屬客製化試卷】\n"
            paper_content += "=" * 40 + "\n\n"
            
            for idx, sq in enumerate(selected_questions):
                paper_content += f"第 {idx+1} 題 [{sq['grade']} - {sq['unit']}]\n"
                paper_content += f"{sq['content']}\n"
                
                # 若有圖片，將圖片網址附在文字檔中
                if pd.notna(sq.get('image_url')) and str(sq['image_url']).strip():
                    paper_content += f"[附圖連結請見網頁版: {sq['image_url']}]\n"
                
                paper_content += f"\n解答： {sq['answer']}\n"
                paper_content += "-" * 40 + "\n\n"

            # 2. 顯示網頁版預覽
            with st.expander("👀 點此展開網頁版試卷預覽", expanded=True):
                for idx, sq in enumerate(selected_questions):
                    st.write(f"**第 {idx+1} 題**")
                    st.markdown(str(sq['content']).replace('\n', '  \n'))
                    if pd.notna(sq.get('image_url')) and str(sq['image_url']).strip():
                        st.image(str(sq['image_url']), width=300)
                    st.markdown(f"**解答： {sq['answer']}**")
                    st.write("---")

            # 3. 建立下載按鈕
            st.download_button(
                label="📥 下載這份試卷 (純文字檔 .txt)",
                data=paper_content,
                file_name="客製化試卷.txt",
                mime="text/plain",
                use_container_width=True
            )
