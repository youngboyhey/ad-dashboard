import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 設定頁面
st.set_page_config(page_title="全通路電商戰情室", layout="wide")
st.title("📊 全通路電商戰情室 (Ads + Official Site)")

# 2. Google Sheet 設定
sheet_id = "17EYeSds7eV-eX4qFt3_gS8ttL-aw-ARzVJ1rwveqTZ4"
gid_google = "0" 
gid_meta = "1891939344"  # [⚠️請確認] Meta 分頁 GID
gid_site = "1703192625" # [✅新加入] 官網後台數據 GID

url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"
url_site = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_site}"

# === 🎨 定義品牌顏色 ===
color_map = {
    'Google': '#EA4335',  # Google 紅
    'Meta': '#4267B2',    # Meta 藍
    'Organic/Direct': '#34A853', # 自然流量 綠
    'Ads': '#FBBC05'      # 廣告加總 黃
}

# 3. 數據處理核心
@st.cache_data(ttl=600)
def load_data():
    try:
        df_g = pd.read_csv(url_google)
        df_m = pd.read_csv(url_meta)
        df_s = pd.read_csv(url_site) # 讀取官網數據
    except Exception as e:
        st.error(f"無法讀取資料，請檢查 GID 或權限。錯誤: {e}")
        return pd.DataFrame(), pd.DataFrame()

    # --- A. 處理廣告數據 ---
    df_g['Platform'] = 'Google'
    df_m['Platform'] = 'Meta'
    
    def clean_currency(x):
        if isinstance(x, str): return float(x.replace('NT$', '').replace(',', '').strip())
        return float(x) if x else 0.0
    
    def clean_num(x):
        if isinstance(x, str): return float(x.replace(',', '').strip())
        return float(x) if x else 0.0

    cols_money = ['費用', 'CPC', '單次轉換費用', '轉換金額']
    cols_num = ['曝光次數', '點擊數', '轉換']

    for df in [df_g, df_m]:
        for c in cols_money:
            if c in df.columns: df[c] = df[c].apply(clean_currency)
        for c in cols_num:
            if c in df.columns: df[c] = df[c].apply(clean_num)
        
        df['廣告期間(起)'] = pd.to_datetime(df['廣告期間(起)'], errors='coerce')
        if '轉換金額' in df.columns: df['轉換金額'] = df['轉換金額'].fillna(0)
    
    # 合併廣告數據
    common = ['Platform', '廣告活動', '廣告期間(起)', '費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    existing = [c for c in common if c in df_g.columns and c in df_m.columns]
    df_ads = pd.concat([df_g[existing], df_m[existing]], ignore_index=True)

    # --- B. 處理官網後台數據 ---
    # 欄位: 日期, 流量, 轉換率(%), 訂單數, 平均客單價, 營業額, 註冊會員數
    site_cols_money = ['平均客單價', '營業額']
    site_cols_num = ['流量', '訂單數', '註冊會員數']

    for c in site_cols_money:
        if c in df_s.columns: df_s[c] = df_s[c].apply(clean_currency)
    for c in site_cols_num:
        if c in df_s.columns: df_s[c] = df_s[c].apply(clean_num)
        
    df_s['日期'] = pd.to_datetime(df_s['日期'], errors='coerce')
    
    return df_ads, df_s

df_ads, df_site = load_data()

if df_ads.empty or df_site.empty:
    st.warning("數據讀取中或部分數據缺失，請確認 GID 設定。")
    st.stop()

# 4. 側邊欄過濾器
st.sidebar.header("🎯 數據篩選")
# 取兩個數據源日期的交集或聯集，這裡取 min/max
min_date = min(df_ads['廣告期間(起)'].min(), df_site['日期'].min())
max_date = max(df_ads['廣告期間(起)'].max(), df_site['日期'].max())

date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])
selected_platform = st.sidebar.multiselect("📱 廣告平台", df_ads['Platform'].unique(), default=df_ads['Platform'].unique())

# 應用過濾
start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

# 過濾廣告數據
mask_ads = (df_ads['Platform'].isin(selected_platform)) & \
           (df_ads['廣告期間(起)'] >= start) & (df_ads['廣告期間(起)'] <= end)
df_ads_f = df_ads[mask_ads].copy()

# 過濾官網數據
mask_site = (df_site['日期'] >= start) & (df_site['日期'] <= end)
df_site_f = df_site[mask_site].copy()

# ==========================================
# 📊 第一部分：全站營運總覽 (整合視角)
# ==========================================
st.markdown("### 🌐 全站營運與廣告貢獻分析")

# 1. 準備合併數據 (按日聚合)
# 廣告日報表
daily_ads = df_ads_f.groupby('廣告期間(起)')[['費用', '轉換金額', '點擊數', '轉換']].sum().reset_index()
daily_ads.rename(columns={'廣告期間(起)': '日期', '費用': '廣告花費', '轉換金額': '廣告營收', '點擊數': '廣告點擊', '轉換': '廣告訂單'}, inplace=True)

# 官網日報表
daily_site = df_site_f[['日期', '營業額', '流量', '訂單數', '註冊會員數']].copy()
daily_site.rename(columns={'營業額': '全站營收', '流量': '全站流量', '訂單數': '全站訂單'}, inplace=True)

# 合併 (Merge)
df_merge = pd.merge(daily_site, daily_ads, on='日期', how='left').fillna(0)

# 計算衍生指標
df_merge['自然流量營收'] = df_merge['全站營收'] - df_merge['廣告營收']
# 避免負數 (若廣告追蹤歸因不同步可能發生)
df_merge['自然流量營收'] = df_merge['自然流量營收'].apply(lambda x: x if x > 0 else 0)
df_merge['廣告貢獻率(%)'] = (df_merge['廣告營收'] / df_merge['全站營收'] * 100).fillna(0)
df_merge['自然流量'] = df_merge['全站流量'] - df_merge['廣告點擊']
df_merge['自然流量'] = df_merge['自然流量'].apply(lambda x: x if x > 0 else 0)

# KPI 卡片
k1, k2, k3, k4, k5 = st.columns(5)
total_site_rev = df_merge['全站營收'].sum()
total_ad_rev = df_merge['廣告營收'].sum()
organic_rev = df_merge['自然流量營收'].sum()
total_members = df_merge['註冊會員數'].sum()
ad_contrib_rate = (total_ad_rev / total_site_rev * 100) if total_site_rev > 0 else 0

k1.metric("🏠 全站總營收", f"${total_site_rev:,.0f}")
k2.metric("📢 廣告帶來營收", f"${total_ad_rev:,.0f}", delta=f"佔比 {ad_contrib_rate:.1f}%")
k3.metric("🌳 自然/其他營收", f"${organic_rev:,.0f}")
k4.metric("👥 新增會員數", f"{total_members:,.0f} 人")
k5.metric("💰 廣告花費", f"${daily_ads['廣告花費'].sum():,.0f}")

st.divider()

# 圖表區：營收構成 與 流量構成
c_main1, c_main2 = st.columns(2)

with c_main1:
    st.subheader("💰 營收來源堆疊圖 (Ads vs Organic)")
    # 轉換為長格式以便繪圖
    df_rev_stack = df_merge[['日期', '廣告營收', '自然流量營收']].melt(id_vars='日期', var_name='來源', value_name='金額')
    
    fig_rev = px.bar(df_rev_stack, x='日期', y='金額', color='來源', 
                     title="每日營收組成：廣告 vs 自然",
                     color_discrete_map={'廣告營收': color_map['Google'], '自然流量營收': color_map['Organic/Direct']})
    st.plotly_chart(fig_rev, use_container_width=True)

with c_main2:
    st.subheader("👥 會員註冊趨勢")
    fig_mem = px.bar(df_merge, x='日期', y='註冊會員數', 
                     title="每日新增會員數",
                     color_discrete_sequence=['#FF9900']) # 橘色代表會員
    # 疊加廣告花費趨勢線，看花費是否帶動會員
    fig_mem.add_trace(go.Scatter(x=df_merge['日期'], y=df_merge['廣告花費'], 
                                 mode='lines', name='廣告花費', yaxis='y2', line=dict(color='gray', dash='dot')))
    
    fig_mem.update_layout(yaxis2=dict(title='廣告花費', overlaying='y', side='right', showgrid=False))
    st.plotly_chart(fig_mem, use_container_width=True)


# ==========================================
# 📈 第二部分：廣告平台深入分析 (原有的 Ads Dashboard)
# ==========================================
st.markdown("### 📢 廣告平台成效細節 (Google & Meta)")

# (原有的 KPI 計算)
c1, c2, c3, c4 = st.columns(4)
ad_cost = df_ads_f['費用'].sum()
ad_rev = df_ads_f['轉換金額'].sum()
ad_roas = ad_rev / ad_cost if ad_cost > 0 else 0
ad_clicks = df_ads_f['點擊數'].sum()

c1.metric("廣告總花費", f"${ad_cost:,.0f}")
c2.metric("廣告總營收", f"${ad_rev:,.0f}")
c3.metric("廣告 ROAS", f"{ad_roas:.2f}")
c4.metric("廣告總點擊", f"{ad_clicks:,.0f}")

col_p1, col_p2 = st.columns(2)

# 平台成效圖
with col_p1:
    st.subheader("平台預算佔比")
    df_platform_cost = df_ads_f.groupby('Platform')['費用'].sum().reset_index()
    fig_pie = px.pie(df_platform_cost, values='費用', names='Platform', 
                     color='Platform', color_discrete_map=color_map, hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_p2:
    st.subheader("Top 10 廣告活動 (依營收)")
    df_camp = df_ads_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額', 'ROAS']].sum().reset_index()
    df_top = df_camp.sort_values('轉換金額', ascending=True).tail(10)
    
    fig_bar = px.bar(df_top, x='轉換金額', y='廣告活動', orientation='h', color='Platform',
                     title="營收最高的 10 個廣告",
                     color_discrete_map=color_map)
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

with st.expander("📄 查看合併詳細報表 (全站 + 廣告)"):
    st.dataframe(df_merge.sort_values('日期', ascending=False))
