import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 設定頁面
st.set_page_config(page_title="電商廣告戰情室 Pro", layout="wide")
st.title("📊 電商廣告戰情室 Pro (Google & Meta)")

# 2. Google Sheet 設定
sheet_id = "17EYeSds7eV-eX4qFt3_gS8ttL-aw-ARzVJ1rwveqTZ4"
gid_google = "0" 
# [⚠️請確認] Meta 分頁 GID (請填入您 Meta 分頁網址後的 gid=數字)
gid_meta = "1891939344"  

url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"

# 3. 數據處理核心 (加入快取)
@st.cache_data(ttl=600)
def load_data():
    try:
        df_g = pd.read_csv(url_google)
        df_m = pd.read_csv(url_meta)
    except Exception as e:
        st.error(f"無法讀取資料，請檢查 GID 或權限。錯誤: {e}")
        return pd.DataFrame()

    df_g['Platform'] = 'Google'
    df_m['Platform'] = 'Meta'
    
    # 數值清理函數
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
    
    # 統一欄位合併
    common = ['Platform', '廣告活動', '廣告期間(起)', '費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    existing = [c for c in common if c in df_g.columns and c in df_m.columns]
    
    return pd.concat([df_g[existing], df_m[existing]], ignore_index=True)

df = load_data()
if df.empty: st.stop()

# 4. 側邊欄過濾器
st.sidebar.header("🎯 數據篩選")
min_date, max_date = df['廣告期間(起)'].min(), df['廣告期間(起)'].max()
date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])
selected_platform = st.sidebar.multiselect("📱 平台", df['Platform'].unique(), default=df['Platform'].unique())
selected_campaign = st.sidebar.multiselect("📢 廣告活動", df['廣告活動'].unique(), default=df['廣告活動'].unique())

# 應用過濾
if len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    mask = (df['Platform'].isin(selected_platform)) & \
           (df['廣告活動'].isin(selected_campaign)) & \
           (df['廣告期間(起)'] >= start) & (df['廣告期間(起)'] <= end)
    df_f = df[mask].copy()
else:
    df_f = df.copy()

# 5. 全局 KPI (加入 CPA 與 CVR)
c1, c2, c3, c4, c5 = st.columns(5)
total_cost = df_f['費用'].sum()
total_rev = df_f['轉換金額'].sum()
total_conv = df_f['轉換'].sum()
avg_roas = total_rev / total_cost if total_cost > 0 else 0
avg_cpa = total_cost / total_conv if total_conv > 0 else 0

c1.metric("💰 總花費", f"${total_cost:,.0f}")
c2.metric("💵 總營收", f"${total_rev:,.0f}")
c3.metric("📈 整體 ROAS", f"{avg_roas:.2f}")
c4.metric("🛒 總轉換數", f"{total_conv:,.0f}")
c5.metric("📉 平均 CPA", f"${avg_cpa:,.0f}")

st.divider()

# 6. 進階分析區塊

# --- 第一層：平台戰略 (餅圖) ---
st.subheader("🆚 平台戰略版圖：錢花在哪？營收從哪來？")
col_p1, col_p2 = st.columns(2)

df_platform = df_f.groupby('Platform')[['費用', '轉換金額']].sum().reset_index()

with col_p1:
    fig_pie1 = px.pie(df_platform, values='費用', names='Platform', title='💸 預算消耗佔比 (Share of Wallet)', hole=0.4)
    st.plotly_chart(fig_pie1, use_container_width=True)

with col_p2:
    fig_pie2 = px.pie(df_platform, values='轉換金額', names='Platform', title='💰 營收貢獻佔比 (Share of Revenue)', hole=0.4)
    st.plotly_chart(fig_pie2, use_container_width=True)

# --- 第二層：效率趨勢 (修正聚合邏輯) ---
st.subheader("📉 效率漏斗趨勢 (Efficiency Trend)")
df_f['Week'] = df_f['廣告期間(起)'].dt.to_period('W').apply(lambda r: r.start_time)

# 正確的加權計算：先加總分子分母，再相除
df_weekly = df_f.groupby(['Platform', 'Week'])[['費用', '轉換金額', '轉換', '點擊數', '曝光次數']].sum().reset_index()
df_weekly['ROAS'] = df_weekly['轉換金額'] / df_weekly['費用']
df_weekly['CPA'] = df_weekly['費用'] / df_weekly['轉換']
df_weekly['CTR'] = (df_weekly['點擊數'] / df_weekly['曝光次數']) * 100
df_weekly['CVR'] = (df_weekly['轉換'] / df_weekly['點擊數']) * 100

trend_metric = st.selectbox("選擇分析指標", ['ROAS (投資報酬率)', 'CPA (單次轉換成本)', 'CTR (點擊率)', '費用', '轉換金額'])
metric_map = {'ROAS (投資報酬率)': 'ROAS', 'CPA (單次轉換成本)': 'CPA', 'CTR (點擊率)': 'CTR', '費用': '費用', '轉換金額': '轉換金額'}
y_col = metric_map[trend_metric]

fig_line = px.line(df_weekly, x='Week', y=y_col, color='Platform', markers=True, 
                   title=f"雙平台 {trend_metric} 週走勢")
st.plotly_chart(fig_line, use_container_width=True)

# --- 第三層：英雄榜 (Top Campaigns) ---
st.subheader("🏆 黃金廣告活動英雄榜 (Top 10)")
rank_metric = st.radio("排序依據", ['轉換金額 (營收)', 'ROAS (效率)'], horizontal=True)
rank_col = '轉換金額' if rank_metric == '轉換金額 (營收)' else 'ROAS'

# 聚合計算
df_camp = df_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額']].sum().reset_index()
df_camp['ROAS'] = df_camp['轉換金額'] / df_camp['費用']

# 避免 ROAS 無限大或無意義 (花費過少)
if rank_col == 'ROAS':
    df_camp = df_camp[df_camp['費用'] > 1000] # 過濾掉花費太少的測試廣告

df_top = df_camp.sort_values(rank_col, ascending=True).tail(10) # 取前10

fig_bar = px.bar(df_top, x=rank_col, y='廣告活動', orientation='h', color='Platform', 
                 text_auto='.2f' if rank_col=='ROAS' else '.0f',
                 title=f"表現最好的前 10 名廣告 ({rank_metric})")
st.plotly_chart(fig_bar, use_container_width=True)

# 7. 詳細報表
with st.expander("📄 查看原始數據明細"):
    st.dataframe(df_f.sort_values('廣告期間(起)', ascending=False))
