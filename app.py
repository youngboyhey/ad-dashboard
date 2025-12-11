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
    'Organic/Direct': '#34A853', # 自然流量 (綠)
    'Ads': '#FBBC05',            # 廣告總合 (黃)
    'Traffic_Ads': '#F6B26B',    # 流量圖-廣告點擊 (淺橘)
    'Traffic_Org': '#93C47D'     # 流量圖-自然流量 (淺綠)
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
        df['廣告期間(迄)'] = df['廣告期間(迄)'].fillna(df['廣告期間(起)']) 
        if '轉換金額' in df.columns: df['轉換金額'] = df['轉換金額'].fillna(0)
    
    common = ['Platform', '廣告活動', '廣告期間(起)', '廣告期間(迄)', '費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    existing = [c for c in common if c in df_g.columns and c in df_m.columns]
    df_raw_ads = pd.concat([df_g[existing], df_m[existing]], ignore_index=True)

    # 🔥 日期拆解 (Explode) Logic 🔥
    # 這裡必須先拆解成每日，後續才能重新聚合成任意區間 (如每週)
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

# 4. 側邊欄過濾 (全域)
st.sidebar.header("🎯 全域篩選器")
min_date = min(df_ads['統計日期'].min(), df_site['日期'].min())
max_date = max(df_ads['統計日期'].max(), df_site['日期'].max())
date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])

if len(date_range) != 2: st.stop()
start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

# 廣告平台篩選
all_platforms = df_ads['Platform'].unique()
sidebar_platform = st.sidebar.multiselect("📱 廣告平台 (影響圖表)", all_platforms, default=all_platforms)

# 資料截取
df_ads_f = df_ads[
    (df_ads['統計日期'] >= start_d) & 
    (df_ads['統計日期'] <= end_d) &
    (df_ads['Platform'].isin(sidebar_platform))
].copy()

df_site_f = df_site[(df_site['日期'] >= start_d) & (df_site['日期'] <= end_d)].copy()

# 基礎每日合併 (Foundation)
daily_ads = df_ads_f.groupby('統計日期')[['費用', '轉換金額', '點擊數', '轉換']].sum().reset_index()
daily_ads.rename(columns={'統計日期': '日期', '費用': '廣告花費', '轉換金額': '廣告營收', '點擊數': '廣告點擊', '轉換': '廣告訂單'}, inplace=True)
daily_site = df_site_f[['日期', '營業額', '流量', '訂單數', '註冊會員數']].copy()
daily_site.rename(columns={'營業額': '全站營收', '流量': '全站流量'}, inplace=True)

df_merge_daily = pd.merge(daily_site, daily_ads, on='日期', how='left').fillna(0)

# === 🚀 新增：數據顆粒度控制器 ===
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("📊 圖表檢視粒度", ["每週 (Weekly)", "每日 (Daily)"], index=0)

# 根據選擇進行聚合
if view_mode == "每週 (Weekly)":
    # 將日期設為 Index 以便 Resample
    df_merge_daily.set_index('日期', inplace=True)
    # 按週 (W-MON: 每週一開始) 進行加總聚合
    df_chart = df_merge_daily.resample('W-MON').sum().reset_index()
    # 調整日期顯示 (只顯示該週開始日期)
    df_chart['日期'] = df_chart['日期'].dt.strftime('%Y-%m-%d')
else:
    df_chart = df_merge_daily.copy()
    # 格式化日期字串
    df_chart['日期'] = df_chart['日期'].dt.strftime('%Y-%m-%d')

# 計算衍生指標 (聚合後重新計算)
df_chart['自然流量營收'] = df_chart['全站營收'] - df_chart['廣告營收']
df_chart['自然流量'] = df_chart['全站流量'] - df_chart['廣告點擊']

# === 創建分頁 (Tabs) ===
tab1, tab2 = st.tabs(["🌐 全站營運總覽", "⚔️ Google vs Meta 雙平台 PK"])

# ==========================================
# Tab 1: 全站營運總覽
# ==========================================
with tab1:
    st.subheader(f"💰 營收與流量構成分析 ({view_mode})")
    
    # KPI (始終顯示區間總和，不受日/週影響)
    k1, k2, k3, k4 = st.columns(4)
    tot_rev = df_merge_daily['全站營收'].sum()
    ad_rev = df_merge_daily['廣告營收'].sum()
    org_rev = tot_rev - ad_rev 
    
    k1.metric("🏠 全站總營收", f"${tot_rev:,.0f}")
    k2.metric("📢 廣告帶來營收", f"${ad_rev:,.0f}", delta=f"佔比 {(ad_rev/tot_rev*100 if tot_rev>0 else 0):.1f}%")
    k3.metric("🌳 自然/其他營收", f"${org_rev:,.0f}", help="若為負值，代表廣告平台追蹤到的營收大於官網實際入帳")
    k4.metric("🛒 全站轉換率", f"{(df_merge_daily['全站營收'].count() / df_merge_daily['全站流量'].sum() * 100 if df_merge_daily['全站流量'].sum()>0 else 0):.2f}%")
    
    # KPI Row 2: 流量
    st.markdown("---")
    t1, t2, t3, t4 = st.columns(4)
    tot_traffic = df_merge_daily['全站流量'].sum()
    ad_clicks = df_merge_daily['廣告點擊'].sum() 
    org_traffic_diff = tot_traffic - ad_clicks
    new_mem = df_merge_daily['註冊會員數'].sum()
    
    t1.metric("👣 全站總流量 (Visits)", f"{tot_traffic:,.0f}")
    t2.metric("👆 廣告點擊數 (Clicks)", f"{ad_clicks:,.0f}")
    t3.metric("📉 流量落差 (自然流量)", f"{org_traffic_diff:,.0f}", 
              help="全站流量 - 廣告點擊。若為負值，代表發生「點擊流失」。", delta_color="off") 
    t4.metric("👥 新增會員", f"{new_mem:,.0f} 人")
    
    st.divider()

    # 圖表區 (使用 df_chart，可能是日或週)
    c1, c2 = st.columns(2)
    with c1:
        # 營收堆疊圖
        df_rev_stack = df_chart[['日期', '廣告營收', '自然流量營收']].melt(id_vars='日期', var_name='來源', value_name='金額')
        fig_rev = px.bar(df_rev_stack, x='日期', y='金額', color='來源', 
                         title=f"營收組成 ({view_mode})",
                         color_discrete_map={'廣告營收': color_map['Google'], '自然流量營收': color_map['Organic/Direct']})
        st.plotly_chart(fig_rev, use_container_width=True)
    
    with c2:
        # 流量堆疊圖
        df_traf_stack = df_chart[['日期', '廣告點擊', '自然流量']].melt(id_vars='日期', var_name='來源', value_name='流量')
        fig_traf = px.bar(df_traf_stack, x='日期', y='流量', color='來源',
                          title=f"流量組成 ({view_mode})",
                          color_discrete_map={'廣告點擊': color_map['Traffic_Ads'], '自然流量': color_map['Traffic_Org']})
        st.plotly_chart(fig_traf, use_container_width=True)

    # 會員成長圖 (雙軸)
    fig_mem = go.Figure()
    # 會員數 Bar
    fig_mem.add_trace(go.Bar(x=df_chart['日期'], y=df_chart['註冊會員數'], name='新增會員', marker_color='#FF9900'))
    # 廣告花費 Line (Secondary Y)
    fig_mem.add_trace(go.Scatter(x=df_chart['日期'], y=df_chart['廣告花費'], name='廣告花費', yaxis='y2', 
                                 line=dict(color='gray', dash='dot')))
    
    fig_mem.update_layout(title=f"會員註冊 vs 廣告投入 ({view_mode})", 
                          yaxis=dict(title="會員數"),
                          yaxis2=dict(title="廣告花費 ($)", overlaying='y', side='right', showgrid=False))
    st.plotly_chart(fig_mem, use_container_width=True)

# ==========================================
# Tab 2: Google vs Meta 雙平台 PK
# ==========================================
with tab2:
    st.subheader("平台成效深度對比")
    
    # 平台 KPI (使用原始過濾資料計算總和)
    platform_kpi = df_ads_f.groupby('Platform')[['費用', '轉換金額', '轉換', '點擊數']].sum()
    platform_kpi['ROAS'] = platform_kpi['轉換金額'] / platform_kpi['費用']
    platform_kpi['CPA'] = platform_kpi['費用'] / platform_kpi['轉換']
    platform_kpi['CPC'] = platform_kpi['費用'] / platform_kpi['點擊數']
    
    col_g, col_m = st.columns(2)
    
    with col_g:
        st.markdown("#### 🔴 Google Ads")
        if 'Google' in platform_kpi.index:
            g = platform_kpi.loc['Google']
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ROAS", f"{g['ROAS']:.2f}")
            c2.metric("CPA", f"${g['CPA']:.0f}")
            c3.metric("營收", f"${g['轉換金額']:,.0f}")
            c4.metric("花費", f"${g['費用']:,.0f}")
        else:
            st.info("無數據")

    with col_m:
        st.markdown("#### 🔵 Meta Ads")
        if 'Meta' in platform_kpi.index:
            m = platform_kpi.loc['Meta']
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ROAS", f"{m['ROAS']:.2f}")
            c2.metric("CPA", f"${m['CPA']:.0f}")
            c3.metric("營收", f"${m['轉換金額']:,.0f}")
            c4.metric("花費", f"${m['費用']:,.0f}")
        else:
            st.info("無數據")
            
    st.divider()
    
    # 圖表 PK
    c3, c4 = st.columns(2)
    with c3:
        # ROAS 趨勢 (這裡本身就是週報表概念，保持原樣或隨 view_mode 連動)
        # 為了清晰，這裡保持以「週」為單位的折線圖，因為看趨勢用週比較準
        df_weekly = df_ads_f.copy()
        df_weekly['Week'] = df_weekly['統計日期'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_group = df_weekly.groupby(['Platform', 'Week'])[['費用', '轉換金額']].sum().reset_index()
        weekly_group['ROAS'] = weekly_group['轉換金額'] / weekly_group['費用']
        fig_roas = px.line(weekly_group, x='Week', y='ROAS', color='Platform', markers=True,
                           title="每週 ROAS 趨勢對比", color_discrete_map=color_map)
        st.plotly_chart(fig_roas, use_container_width=True)

    with c4:
        # Top 10 (使用聚合數據)
        df_camp = df_ads_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額']].sum().reset_index()
        df_top = df_camp.sort_values('轉換金額', ascending=True).tail(10)
        fig_top = px.bar(df_top, x='轉換金額', y='廣告活動', orientation='h', color='Platform',
                         title="Top 10 廣告活動 (依營收)", text_auto='.0f', color_discrete_map=color_map)
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)

    # 詳細報表區
    st.markdown("---")
    st.subheader("📋 詳細廣告報表")
    
    with st.expander("🔎 表格進階篩選", expanded=True):
        table_platforms = st.multiselect("選擇報表顯示平台", all_platforms, default=sidebar_platform)
    
    df_table = df_ads[
        (df_ads['統計日期'] >= start_d) & 
        (df_ads['統計日期'] <= end_d) & 
        (df_ads['Platform'].isin(table_platforms))
    ].copy()
    
    group_cols = ['統計日期', 'Platform', '廣告活動']
    df_table_agg = df_table.groupby(group_cols)[['費用', '轉換金額', '曝光次數', '點擊數', '轉換']].sum().reset_index()
    
    df_table_agg['ROAS'] = df_table_agg.apply(lambda x: x['轉換金額']/x['費用'] if x['費用']>0 else 0, axis=1)
    df_table_agg['CPC'] = df_table_agg.apply(lambda x: x['費用']/x['點擊數'] if x['點擊數']>0 else 0, axis=1)
    df_table_agg['CTR(%)'] = df_table_agg.apply(lambda x: (x['點擊數']/x['曝光次數']*100) if x['曝光次數']>0 else 0, axis=1)
    df_table_agg['CPA'] = df_table_agg.apply(lambda x: x['費用']/x['轉換'] if x['轉換']>0 else 0, axis=1)
    
    st.dataframe(
        df_table_agg.sort_values(['統計日期', '轉換金額'], ascending=[False, False]),
        column_config={
            "統計日期": st.column_config.DateColumn("日期"),
            "費用": st.column_config.NumberColumn("花費", format="$%d"),
            "轉換金額": st.column_config.NumberColumn("營收", format="$%d"),
            "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
            "CTR(%)": st.column_config.NumberColumn("CTR", format="%.2f%%"),
            "CPC": st.column_config.NumberColumn("CPC", format="$%.1f"),
            "CPA": st.column_config.NumberColumn("CPA", format="$%.0f"),
        },
        use_container_width=True,
        hide_index=True
    )
