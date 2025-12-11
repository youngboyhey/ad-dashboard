import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 設定頁面
st.set_page_config(page_title="CarMall 車魔商城 - 電商戰情室", layout="wide")
st.title("📊 CarMall 車魔商城 - 電商戰情室")

# 2. Google Sheet 設定
sheet_id = "17EYeSds7eV-eX4qFt3_gS8ttL-aw-ARzVJ1rwveqTZ4"
gid_google = "0" 
gid_meta = "1891939344"   # Meta GID
gid_site = "1703192625"  # 官網 GID

url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"
url_site = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_site}"

# === 🎨 顏色設定 ===
color_map = {
    'Google': '#EA4335',  
    'Meta': '#4267B2',    
    'Organic/Direct': '#34A853',
    'Ads': '#FBBC05',           
    'Traffic_Ads': '#F6B26B',    
    'Traffic_Org': '#93C47D'     
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
        df['廣告期間(迄)'] = pd.to_datetime(df['廣告期間(迄)'], errors='coerce')
        df['廣告期間(迄)'] = df['廣告期間(迄)'].fillna(df['廣告期間(起)']) 
        if '轉換金額' in df.columns: df['轉換金額'] = df['轉換金額'].fillna(0)
    
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
st.sidebar.header("🎯 全域篩選器")
min_date = min(df_ads['統計日期'].min(), df_site['日期'].min())
max_date = max(df_ads['統計日期'].max(), df_site['日期'].max())
date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])

if len(date_range) != 2: st.stop()
start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

all_platforms = df_ads['Platform'].unique()
sidebar_platform = st.sidebar.multiselect("📱 廣告平台 (影響圖表)", all_platforms, default=all_platforms)

# 資料截取
df_ads_f = df_ads[
    (df_ads['統計日期'] >= start_d) & 
    (df_ads['統計日期'] <= end_d) &
    (df_ads['Platform'].isin(sidebar_platform))
].copy()

df_site_f = df_site[(df_site['日期'] >= start_d) & (df_site['日期'] <= end_d)].copy()

# 基礎每日合併
daily_ads = df_ads_f.groupby('統計日期')[['費用', '轉換金額', '點擊數', '轉換']].sum().reset_index()
daily_ads.rename(columns={'統計日期': '日期', '費用': '廣告花費', '轉換金額': '廣告營收', '點擊數': '廣告點擊', '轉換': '廣告訂單'}, inplace=True)
daily_site = df_site_f[['日期', '營業額', '流量', '訂單數', '註冊會員數']].copy()
daily_site.rename(columns={'營業額': '全站營收', '流量': '全站流量'}, inplace=True)

df_merge_daily = pd.merge(daily_site, daily_ads, on='日期', how='left').fillna(0)

# === 粒度控制器 ===
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("📊 圖表檢視粒度", ["每週 (Weekly)", "每日 (Daily)"], index=0)

if view_mode == "每週 (Weekly)":
    df_merge_daily.set_index('日期', inplace=True)
    df_chart = df_merge_daily.resample('W-MON').sum().reset_index()
    df_chart['日期'] = df_chart['日期'].dt.strftime('%Y-%m-%d')
else:
    df_chart = df_merge_daily.copy()
    df_chart['日期'] = df_chart['日期'].dt.strftime('%Y-%m-%d')

df_chart['自然流量營收'] = df_chart['全站營收'] - df_chart['廣告營收']
df_chart['自然流量'] = df_chart['全站流量'] - df_chart['廣告點擊']

# === 分頁 ===
tab1, tab2 = st.tabs(["🌐 全站營運總覽", "⚔️ Google vs Meta 雙平台 PK"])

# ==========================================
# Tab 1: 全站營運總覽 (保持不變)
# ==========================================
with tab1:
    st.subheader(f"💰 營收與流量構成分析 ({view_mode})")
    
    k1, k2, k3, k4 = st.columns(4)
    tot_rev = df_site_f['營業額'].sum() # 使用原始欄位
    ad_rev = df_ads_f['轉換金額'].sum()
    org_rev = tot_rev - ad_rev 
    
    k1.metric("🏠 全站總營收", f"${tot_rev:,.0f}")
    k2.metric("📢 廣告帶來營收", f"${ad_rev:,.0f}", delta=f"佔比 {(ad_rev/tot_rev*100 if tot_rev>0 else 0):.1f}%")
    k3.metric("🌳 自然/其他營收", f"${org_rev:,.0f}", help="對於營收：看到負數，請理解為**「多個廣告平台重複搶功勞 (Over-attribution)」**。")
    k4.metric("🛒 全站轉換率", f"{(df_merge_daily['全站營收'].count() / df_merge_daily['全站流量'].sum() * 100 if df_merge_daily['全站流量'].sum()>0 else 0):.2f}%")
    
    st.markdown("---")
    t1, t2, t3, t4 = st.columns(4)
    tot_traffic = df_merge_daily['全站流量'].sum()
    ad_clicks = df_merge_daily['廣告點擊'].sum() 
    org_traffic_diff = tot_traffic - ad_clicks
    new_mem = df_merge_daily['註冊會員數'].sum()
    
    t1.metric("👣 全站總流量 (Visits)", f"{tot_traffic:,.0f}")
    t2.metric("👆 廣告點擊數 (Clicks)", f"{ad_clicks:,.0f}")
    t3.metric("📉 流量落差 (自然流量)", f"{org_traffic_diff:,.0f}", delta_color="off", help="對於流量：看到負數，請理解為**「流失掉的廣告訪客」**。")
    t4.metric("👥 新增會員", f"{new_mem:,.0f} 人")
    
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        df_rev_stack = df_chart[['日期', '廣告營收', '自然流量營收']].melt(id_vars='日期', var_name='來源', value_name='金額')
        fig_rev = px.bar(df_rev_stack, x='日期', y='金額', color='來源', 
                         title=f"營收組成 ({view_mode})",
                         color_discrete_map={'廣告營收': color_map['Google'], '自然流量營收': color_map['Organic/Direct']})
        st.plotly_chart(fig_rev, use_container_width=True)
    
    with c2:
        df_traf_stack = df_chart[['日期', '廣告點擊', '自然流量']].melt(id_vars='日期', var_name='來源', value_name='流量')
        fig_traf = px.bar(df_traf_stack, x='日期', y='流量', color='來源',
                          title=f"流量組成 ({view_mode})",
                          color_discrete_map={'廣告點擊': color_map['Traffic_Ads'], '自然流量': color_map['Traffic_Org']})
        st.plotly_chart(fig_traf, use_container_width=True)

    fig_mem = go.Figure()
    fig_mem.add_trace(go.Bar(x=df_chart['日期'], y=df_chart['註冊會員數'], name='新增會員', marker_color='#FF9900'))
    fig_mem.add_trace(go.Scatter(x=df_chart['日期'], y=df_chart['廣告花費'], name='廣告花費', yaxis='y2', line=dict(color='gray', dash='dot')))
    fig_mem.update_layout(title=f"會員註冊 vs 廣告投入 ({view_mode})", yaxis=dict(title="會員數"), yaxis2=dict(title="廣告花費 ($)", overlaying='y', side='right', showgrid=False))
    st.plotly_chart(fig_mem, use_container_width=True)

# ==========================================
# Tab 2: Google vs Meta 雙平台 PK (大幅更新)
# ==========================================
with tab2:
    st.subheader("⚔️ 雙平台深度 PK 分析")
    
    # 計算平台總體 KPI
    platform_kpi = df_ads_f.groupby('Platform')[['費用', '轉換金額', '轉換', '點擊數', '曝光次數']].sum()
    platform_kpi['ROAS'] = platform_kpi.apply(lambda x: x['轉換金額'] / x['費用'] if x['費用'] > 0 else 0, axis=1)
    platform_kpi['CPA'] = platform_kpi.apply(lambda x: x['費用'] / x['轉換'] if x['轉換'] > 0 else 0, axis=1)
    platform_kpi['CPC'] = platform_kpi.apply(lambda x: x['費用'] / x['點擊數'] if x['點擊數'] > 0 else 0, axis=1)
    platform_kpi['CTR'] = platform_kpi.apply(lambda x: (x['點擊數'] / x['曝光次數'] * 100) if x['曝光次數'] > 0 else 0, axis=1)
    platform_kpi['CVR'] = platform_kpi.apply(lambda x: (x['轉換'] / x['點擊數'] * 100) if x['點擊數'] > 0 else 0, axis=1)

    # 頂部 KPI 卡片
    col_g, col_m = st.columns(2)
    with col_g:
        st.markdown("#### 🔴 Google Ads 總體表現")
        if 'Google' in platform_kpi.index:
            g = platform_kpi.loc['Google']
            # Row 1: 財務指標
            c1, c2, c3 = st.columns(3)
            c1.metric("花費", f"${g['費用']:,.0f}")
            c2.metric("營收", f"${g['轉換金額']:,.0f}")
            c3.metric("ROAS", f"{g['ROAS']:.2f}")
            # Row 2: 效率指標
            c4, c5, c6 = st.columns(3)
            c4.metric("CTR (點閱率)", f"{g['CTR']:.2f}%")
            c5.metric("CVR (轉換率)", f"{g['CVR']:.2f}%")
            c6.metric("CPA (獲客成本)", f"${g['CPA']:.0f}")
        else:
            st.info("無 Google 數據")

    with col_m:
        st.markdown("#### 🔵 Meta Ads 總體表現")
        if 'Meta' in platform_kpi.index:
            m = platform_kpi.loc['Meta']
            # Row 1: 財務指標
            c1, c2, c3 = st.columns(3)
            c1.metric("花費", f"${m['費用']:,.0f}")
            c2.metric("營收", f"${m['轉換金額']:,.0f}")
            c3.metric("ROAS", f"{m['ROAS']:.2f}")
            # Row 2: 效率指標
            c4, c5, c6 = st.columns(3)
            c4.metric("CTR (點閱率)", f"{m['CTR']:.2f}%")
            c5.metric("CVR (轉換率)", f"{m['CVR']:.2f}%")
            c6.metric("CPA (獲客成本)", f"${m['CPA']:.0f}")
        else:
            st.info("無 Meta 數據")

    st.divider()

    # 進階分析 Tab
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📈 核心趨勢 (Trend)", "🎯 漏斗效率 (Funnel)", "🔍 廣告活動象限 (Matrix)"])

    # 準備趨勢資料 (根據 view_mode)
    df_trend = df_ads_f.copy()
    if view_mode == "每週 (Weekly)":
        df_trend['Period'] = df_trend['統計日期'].dt.to_period('W').apply(lambda r: r.start_time)
    else:
        df_trend['Period'] = df_trend['統計日期']

    trend_group = df_trend.groupby(['Platform', 'Period'])[['費用', '轉換金額', '曝光次數', '點擊數', '轉換']].sum().reset_index()
    # 計算衍生指標
    trend_group['ROAS'] = trend_group['轉換金額'] / trend_group['費用']
    trend_group['CTR'] = (trend_group['點擊數'] / trend_group['曝光次數']) * 100
    trend_group['CVR'] = (trend_group['轉換'] / trend_group['點擊數']) * 100
    trend_group['CPC'] = trend_group['費用'] / trend_group['點擊數']
    
    # 格式化日期
    trend_group['Period'] = trend_group['Period'].dt.strftime('%Y-%m-%d')

    # --- Sub Tab 1: 核心趨勢 ---
    with sub_tab1:
        st.caption("觀察「花費」與「營收」的相關性，以及 ROAS 隨時間的變化")
        
        c_trend1, c_trend2 = st.columns(2)
        with c_trend1:
            # 花費趨勢
            fig_spend = px.line(trend_group, x='Period', y='費用', color='Platform', markers=True,
                                title=f"💰 廣告花費趨勢 ({view_mode})", color_discrete_map=color_map)
            st.plotly_chart(fig_spend, use_container_width=True)
        
        with c_trend2:
            # 營收趨勢
            fig_rev_trend = px.line(trend_group, x='Period', y='轉換金額', color='Platform', markers=True,
                                    title=f"💵 廣告營收趨勢 ({view_mode})", color_discrete_map=color_map)
            st.plotly_chart(fig_rev_trend, use_container_width=True)
            
        # ROAS 趨勢
        fig_roas = px.line(trend_group, x='Period', y='ROAS', color='Platform', markers=True,
                           title=f"⚖️ ROAS (投資報酬率) 走勢 ({view_mode})", color_discrete_map=color_map)
        # 加一條 ROAS = 1 的基準線
        fig_roas.add_hline(y=1, line_dash="dot", annotation_text="Break-even (ROAS=1)", annotation_position="bottom right")
        st.plotly_chart(fig_roas, use_container_width=True)

    # --- Sub Tab 2: 漏斗效率 ---
    with sub_tab2:
        st.caption("分析流量品質與素材吸引力：CTR 低代表素材不吸睛，CVR 低代表頁面/產品不吸引人")
        
        c_funnel1, c_funnel2 = st.columns(2)
        with c_funnel1:
            # CTR 趨勢
            fig_ctr = px.line(trend_group, x='Period', y='CTR', color='Platform', markers=True,
                              title="👆 CTR 點閱率趨勢 (%)", color_discrete_map=color_map,
                              labels={'CTR': 'CTR (%)'})
            st.plotly_chart(fig_ctr, use_container_width=True)
        
        with c_funnel2:
            # CVR 趨勢
            fig_cvr = px.line(trend_group, x='Period', y='CVR', color='Platform', markers=True,
                              title="🛒 CVR 轉換率趨勢 (%)", color_discrete_map=color_map,
                              labels={'CVR': 'CVR (%)'})
            st.plotly_chart(fig_cvr, use_container_width=True)

        # CPC 趨勢 (成本)
        fig_cpc = px.line(trend_group, x='Period', y='CPC', color='Platform', markers=True,
                          title="💸 CPC 單次點擊成本趨勢 ($)", color_discrete_map=color_map)
        st.plotly_chart(fig_cpc, use_container_width=True)

    # --- Sub Tab 3: 廣告活動象限 ---
    with sub_tab3:
        st.caption("🔴 **Google** / 🔵 **Meta** | 圓圈大小 = 花費金額 | 游標移上去可看廣告活動名稱")
        
        # 準備資料：以廣告活動為維度聚合
        camp_kpi = df_ads_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額', '轉換']].sum().reset_index()
        camp_kpi['ROAS'] = camp_kpi.apply(lambda x: x['轉換金額'] / x['費用'] if x['費用'] > 0 else 0, axis=1)
        camp_kpi['CPA'] = camp_kpi.apply(lambda x: x['費用'] / x['轉換'] if x['轉換'] > 0 else 0, axis=1)
        
        # 過濾掉花費太少的極端值，避免圖表混亂 (例如花費 < 1000)
        camp_kpi_filtered = camp_kpi[camp_kpi['費用'] > 500].copy()

        # 氣泡圖：X軸=CPA (越左越好), Y軸=ROAS (越高越好), Size=費用
        fig_bubble = px.scatter(camp_kpi_filtered, x="CPA", y="ROAS",
                                size="費用", color="Platform",
                                hover_name="廣告活動",
                                text="廣告活動", # 如果太亂可以拿掉這行
                                title="矩陣分析：ROAS vs CPA (圓圈越大花費越多)",
                                color_discrete_map=color_map,
                                log_x=True, # CPA 差異可能很大，用 Log scale 比較好讀
                                size_max=60)
        
        # 繪製象限輔助線 (假設 ROAS=2, CPA=500 為及格線，可自行調整)
        fig_bubble.add_hline(y=3, line_dash="dot", annotation_text="高 ROAS", line_color="green")
        fig_bubble.add_vline(x=500, line_dash="dot", annotation_text="高 CPA", line_color="red")
        
        st.plotly_chart(fig_bubble, use_container_width=True)
        
        st.markdown("""
        **💡 象限解讀：**
        * **左上角 (高 ROAS, 低 CPA)**：🔥 **明星廣告**，應該加碼預算！
        * **左下角 (低 ROAS, 低 CPA)**：可考慮優化客單價或素材，風險較低。
        * **右上角 (高 ROAS, 高 CPA)**：高價值客戶但獲客貴，需注意利潤空間。
        * **右下角 (低 ROAS, 高 CPA)**：☠️ **賠錢貨**，建議暫停或大幅修改。
        """)

    # 詳細報表 (保留在最下方)
    st.markdown("---")
    with st.expander("📋 查看詳細數據報表", expanded=False):
        st.dataframe(
            camp_kpi.sort_values('費用', ascending=False),
            column_config={
                "費用": st.column_config.NumberColumn("花費", format="$%d"),
                "轉換金額": st.column_config.NumberColumn("營收", format="$%d"),
                "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                "CPA": st.column_config.NumberColumn("CPA", format="$%.0f"),
            },
            use_container_width=True
        )
