import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 設定頁面
st.set_page_config(page_title="廣告成效儀表板", layout="wide")
st.title("📊 Google & Meta 廣告成效雲端戰情室")

# 2. Google Sheet 設定
# 您的試算表 ID
sheet_id = "17EYeSds7eV-eX4qFt3_gS8ttL-aw-ARzVJ1rwveqTZ4"

# === 設定分頁 ID (GID) ===
# Google 分頁通常是第一個，ID 預設為 "0"
gid_google = "0" 

# [請修改這裡] Meta 分頁的 ID，請查看您 Google Sheet 網址列上的 gid=數字
# 為了避免錯誤，我先預設為 "0" (即讀取第一頁)，請您確認後修改
gid_meta = "1891939344"  # <--- 請將這裡的數字改成 Meta 分頁真正的 gid

# 組合 CSV 下載連結
url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"

# 3. 處理數據函數
@st.cache_data(ttl=600)  # 設定 600秒 (10分鐘) 快取過期，自動重新抓取
def load_and_clean_data():
    try:
        # 讀取 CSV
        df_g = pd.read_csv(url_google)
        df_m = pd.read_csv(url_meta)
    except Exception as e:
        st.error(f"讀取 Google Sheet 失敗，請確認 GID 是否正確或是權限是否公開。錯誤訊息: {e}")
        return pd.DataFrame() # 回傳空表避免當機

    df_g['Platform'] = 'Google'
    df_m['Platform'] = 'Meta'
    
    # 清理邏輯
    def clean_currency(x):
        if isinstance(x, str) and x:
            return float(x.replace('NT$', '').replace(',', '').strip())
        return 0.0
    
    def clean_numeric(x):
        # 修正後的邏輯：先轉字串再處理，避免純數字被誤判
        if x is None or str(x).strip() == '':
            return 0.0
        return float(str(x).replace(',', ''))
    
    cols_currency = ['費用', 'CPC', '單次轉換費用', '轉換金額']
    cols_num = ['曝光次數', '點擊數', '轉換']
    
    for df in [df_g, df_m]:
        for col in cols_currency:
            if col in df.columns: 
                df[col] = df[col].apply(clean_currency)
        for col in cols_num:
            if col in df.columns: 
                df[col] = df[col].apply(clean_numeric)
        
        # 日期轉換
        df['廣告期間(起)'] = pd.to_datetime(df['廣告期間(起)'], errors='coerce')
        if '轉換金額' in df.columns: 
            df['轉換金額'] = df['轉換金額'].fillna(0)
        if 'ROAS' in df.columns: 
            df['ROAS'] = df['ROAS'].fillna(0)

    # 合併
    common = ['Platform', '廣告活動', '廣告期間(起)', '費用', '曝光次數', '點擊數', 'CPC', '轉換', '轉換金額', 'ROAS']
    # 確保欄位存在才合併，避免不同步錯誤
    common_exist = [c for c in common if c in df_g.columns and c in df_m.columns]
    
    return pd.concat([df_g[common_exist], df_m[common_exist]], ignore_index=True)

df = load_and_clean_data()

# 若數據讀取失敗則中止程式
if df.empty:
    st.stop()

# 4. 側邊欄控制與過濾
st.sidebar.header("🎯 分析過濾器")
platforms = st.sidebar.multiselect("選擇平台", df['Platform'].unique(), default=df['Platform'].unique())
campaigns = st.sidebar.multiselect("選擇廣告活動", df['廣告活動'].unique(), default=df['廣告活動'].unique())

min_date = df['廣告期間(起)'].min()
max_date = df['廣告期間(起)'].max()

# 避免日期為 NaT 的錯誤處理
if pd.isnull(min_date) or pd.isnull(max_date):
    st.sidebar.warning("日期格式有誤或無數據")
    df_filtered = df
else:
    date_range = st.sidebar.date_input("選擇日期區間", [min_date, max_date])
    # 應用過濾
    if len(date_range) == 2:
        start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        mask = (df['Platform'].isin(platforms)) & (df['廣告活動'].isin(campaigns)) & (df['廣告期間(起)'] >= start_d) & (df['廣告期間(起)'] <= end_d)
        df_filtered = df[mask]
    else:
        df_filtered = df

# 5. 核心指標 (KPIs)
col1, col2, col3, col4 = st.columns(4)
total_cost = df_filtered['費用'].sum()
total_rev = df_filtered['轉換金額'].sum()
avg_roas = total_rev / total_cost if total_cost > 0 else 0
total_clicks = df_filtered['點擊數'].sum()

col1.metric("💰 總花費 (Cost)", f"${total_cost:,.0f}")
col2.metric("💵 總營收 (Revenue)", f"${total_rev:,.0f}")
col3.metric("📈 整體 ROAS", f"{avg_roas:.2f}")
col4.metric("👆 總點擊數", f"{total_clicks:,.0f}")

st.divider()

# 6. 可視化圖表
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("📅 雙平台趨勢分析 (Weekly Trend)")
    if not df_filtered.empty:
        # 根據週次聚合數據
        df_filtered['Week'] = df_filtered['廣告期間(起)'].dt.to_period('W').apply(lambda r: r.start_time)
        df_weekly = df_filtered.groupby(['Platform', 'Week'])[['費用', '轉換金額', 'ROAS']].mean().reset_index()
        
        metric_select = st.selectbox("選擇趨勢指標", ['ROAS', '費用', '轉換金額'], index=0)
        fig_line = px.line(df_weekly, x='Week', y=metric_select, color='Platform', markers=True, title=f"{metric_select} 週走勢")
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("無數據可顯示趨勢")

with c2:
    st.subheader("📊 廣告效益散佈圖")
    if not df_filtered.empty:
        # 每個廣告活動的表現
        df_agg = df_filtered.groupby(['Platform', '廣告活動'])[['費用', '轉換金額', 'ROAS']].sum().reset_index()
        fig_scat = px.scatter(df_agg, x='費用', y='轉換金額', color='Platform', size='ROAS', hover_name='廣告活動', 
                              title="花費 vs 營收 (點越大 ROAS 越高)")
        st.plotly_chart(fig_scat, use_container_width=True)
    else:
        st.info("無數據可顯示散佈圖")

with st.expander("📄 查看詳細數據報表"):
    st.dataframe(df_filtered.sort_values(by='廣告期間(起)', ascending=False))
