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
gid_meta = "1891939344"   # [⚠️請確認] Meta GID
gid_site = "1703192625"  # [⚠️請確認] 官網 GID

url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"
url_site = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_site}"

# === 🎨 顏色設定 ===
color_map = {
    'Google': '#EA4335',  
    'Meta': '#4267B2',    
    'Organic/Direct': '#34A853', 
    'Ads': '#FBBC05'      
}

# 3. 數據處理核心
@st.cache_data(ttl=600)
def load_data():
    try:
        df_g = pd.read_csv(url_google)
        df_m = pd.read_csv(url_meta)
        df_s = pd.read_csv(url_site)
    except Exception as e:
        st.error(f"讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

    # --- A. 處理廣告數據 (含日期拆解) ---
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
        df['廣告期間(迄)'] = pd.to_datetime(df['廣告期間(迄)'], errors='coerce')
        df['廣告期間(迄)'] = df['廣告期間(迄)'].fillna(df['廣告期間(起)']) # 補全日期
        if '轉換金額' in df.columns: df['轉換金額'] = df['轉換金額'].fillna(0)
    
    # 合併原始廣告數據
    common = ['Platform', '廣告活動', '廣告期間(起)', '廣告期間(迄)', '費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    existing = [c for c in common if c in df_g.columns and c in df_m.columns]
    df_raw_ads = pd.concat([df_g[existing], df_m[existing]], ignore_index=True)

    # 🔥 日期拆解 (Explode) Logic 🔥
    expanded_rows = []
    metrics_to_split = ['費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    
    for _, row in df_raw_ads.iterrows():
        start, end = row['廣告期間(起)'], row['廣告期間(迄)']
        if pd.isnull(start): continue
        
        days = (end - start).days + 1
        days = 1 if days < 1 else days
        date_range = pd.date_range(start, end, freq='D')
        
        for date in date_range:
            new_row = row.copy()
            new_row['統計日期'] = date
            for m in metrics_to_split:
                if m in row: new_row[m] = row[m] / days
            expanded_rows.append(new_row)
            
    df_ads_daily = pd.DataFrame(expanded_rows)

    # --- B. 處理官網數據 ---
    site_cols = ['平均客單價', '營業額', '流量', '訂單數', '註冊會員數']
    for c in site_cols:
        if c in df_s.columns: 
            df_s[c] = df_s[c].apply(clean_currency if c in ['平均客單價', '營業額'] else clean_num)
        
    df_s['日期'] = pd.to_datetime(df_s['日期'], errors='coerce')
    
    return df_ads_daily, df_s

df_ads, df_site = load_data()
if df_ads.empty or df_site.empty: st.stop()

# 4. 側邊欄過濾
st.sidebar.header("🎯 數據篩選")
min_date = min(df_ads['統計日期'].min(), df_site['日期'].min())
max_date = max(df_ads['統計日期'].max(), df_site['日期'].max())
date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])

if len(date_range) != 2: st.stop()
start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

# 過濾數據
df_ads_f = df_ads[(df_ads['統計日期'] >= start_d) & (df_ads['統計日期'] <= end_d)].copy()
df_site_f = df_site[(df_site['日期'] >= start_d) & (df_site['日期'] <= end_d)].copy()

# 準備合併數據 (全站 vs 廣告)
daily_ads = df_ads_f.groupby('統計日期')[['費用', '轉換金額', '點擊數', '轉換']].sum().reset_index()
daily_ads.rename(columns={'統計日期': '日期', '費用': '廣告花費', '轉換金額': '廣告營收', '點擊數': '廣告點擊', '轉換': '廣告訂單'}, inplace=True)
daily_site = df_site_f[['日期', '營業額', '流量', '訂單數', '註冊會員數']].copy()
daily_site.rename(columns={'營業額': '全站營收'}, inplace=True)

df_merge = pd.merge(daily_site, daily_ads, on='日期', how='left').fillna(0)
# 🔥 修正負值問題：如果廣告營收 > 全站，自然營收設為 0 (視覺上)
df_merge['自然流量營收'] = (df_merge['全站營收'] - df_merge['廣告營收']).apply(lambda x: x if x > 0 else 0)

# === 創建分頁 (Tabs) ===
tab1, tab2 = st.tabs(["🌐 全站營運總覽", "⚔️ Google vs Meta 雙平台 PK"])

# ==========================================
# Tab 1: 全站營運總覽 (老闆視角)
# ==========================================
with tab1:
    st.subheader("營收來源與會員成長")
    
    # KPI
    k1, k2, k3, k4 = st.columns(4)
    tot_rev = df_merge['全站營收'].sum()
    ad_rev = df_merge['廣告營收'].sum()
    org_rev = tot_rev - ad_rev # 數學上真實的自然營收 (可能為負，代表廣告歸因大於後台)
    new_mem = df_merge['註冊會員數'].sum()
    
    k1.metric("🏠 全站總營收", f"${tot_rev:,.0f}")
    k2.metric("📢 廣告帶來營收", f"${ad_rev:,.0f}", delta=f"佔比 {(ad_rev/tot_rev*100 if tot_rev>0 else 0):.1f}%")
    k3.metric("🌳 自然/其他營收", f"${org_rev:,.0f}", help="若為負值代表廣告平台歸因大於官網實際入帳")
    k4.metric("👥 新增會員", f"{new_mem:,.0f} 人")
    
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        # 堆疊圖 (使用修正過負值的欄位繪圖，避免跑版)
        df_stack = df_merge[['日期', '廣告營收', '自然流量營收']].melt(id_vars='日期', var_name='來源', value_name='金額')
        fig_rev = px.bar(df_stack, x='日期', y='金額', color='來源', 
                         title="每日營收組成 (廣告 vs 自然)",
                         color_discrete_map={'廣告營收': color_map['Google'], '自然流量營收': color_map['Organic/Direct']})
        st.plotly_chart(fig_rev, use_container_width=True)
    
    with c2:
        # 雙軸圖：會員 vs 廣告費
        fig_dual = go.Figure()
        fig_dual.add_trace(go.Bar(x=df_merge['日期'], y=df_merge['註冊會員數'], name='新增會員', marker_color='#FF9900'))
        fig_dual.add_trace(go.Scatter(x=df_merge['日期'], y=df_merge['廣告花費'], name='廣告花費', yaxis='y2', 
                                      line=dict(color='gray', dash='dot')))
        fig_dual.update_layout(title="會員註冊 vs 廣告投入", 
                               yaxis=dict(title="會員數"),
                               yaxis2=dict(title="廣告花費 ($)", overlaying='y', side='right', showgrid=False))
        st.plotly_chart(fig_dual, use_container_width=True)

# ==========================================
# Tab 2: Google vs Meta 雙平台 PK (投手視角)
# ==========================================
with tab2:
    st.subheader("平台成效深度對比")
    
    # 1. 計算各平台關鍵指標
    platform_kpi = df_ads_f.groupby('Platform')[['費用', '轉換金額', '轉換', '點擊數']].sum()
    platform_kpi['ROAS'] = platform_kpi['轉換金額'] / platform_kpi['費用']
    platform_kpi['CPA'] = platform_kpi['費用'] / platform_kpi['轉換']
    platform_kpi['CPC'] = platform_kpi['費用'] / platform_kpi['點擊數']
    
    # 2. 顯示 KPI 卡片 (分成兩列：Google 一列，Meta 一列)
    
    # Google 區塊
    st.markdown("#### 🔴 Google Ads")
    g_cols = st.columns(5)
    if 'Google' in platform_kpi.index:
        g_data = platform_kpi.loc['Google']
        g_cols[0].metric("花費", f"${g_data['費用']:,.0f}")
        g_cols[1].metric("營收", f"${g_data['轉換金額']:,.0f}")
        g_cols[2].metric("ROAS", f"{g_data['ROAS']:.2f}")
        g_cols[3].metric("CPA", f"${g_data['CPA']:.0f}")
        g_cols[4].metric("CPC", f"${g_data['CPC']:.1f}")
    else:
        st.info("無 Google 數據")

    st.markdown("---")

    # Meta 區塊
    st.markdown("#### 🔵 Meta Ads")
    m_cols = st.columns(5)
    if 'Meta' in platform_kpi.index:
        m_data = platform_kpi.loc['Meta']
        m_cols[0].metric("花費", f"${m_data['費用']:,.0f}")
        m_cols[1].metric("營收", f"${m_data['轉換金額']:,.0f}")
        m_cols[2].metric("ROAS", f"{m_data['ROAS']:.2f}")
        m_cols[3].metric("CPA", f"${m_data['CPA']:.0f}")
        m_cols[4].metric("CPC", f"${m_data['CPC']:.1f}")
    else:
        st.info("無 Meta 數據")
        
    st.divider()
    
    # 3. 圖表 PK
    c3, c4 = st.columns(2)
    
    with c3:
        # ROAS 趨勢對比
        df_weekly = df_ads_f.copy()
        df_weekly['Week'] = df_weekly['統計日期'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_group = df_weekly.groupby(['Platform', 'Week'])[['費用', '轉換金額']].sum().reset_index()
        weekly_group['ROAS'] = weekly_group['轉換金額'] / weekly_group['費用']
        
        fig_roas = px.line(weekly_group, x='Week', y='ROAS', color='Platform', markers=True,
                           title="每週 ROAS 趨勢對比", color_discrete_map=color_map)
        st.plotly_chart(fig_roas, use_container_width=True)

    with c4:
        # Top 10 廣告 (混和排名)
        df_camp = df_ads_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額']].sum().reset_index()
        df_camp['ROAS'] = df_camp.apply(lambda x: x['轉換金額']/x['費用'] if x['費用']>0 else 0, axis=1)
        df_top = df_camp.sort_values('轉換金額', ascending=True).tail(10)
        
        fig_top = px.bar(df_top, x='轉換金額', y='廣告活動', orientation='h', color='Platform',
                         title="Top 10 廣告活動 (依營收)", text_auto='.0f', color_discrete_map=color_map)
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)
