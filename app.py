import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

# 1. 設定頁面
st.set_page_config(page_title="全通路電商戰情室", layout="wide")
st.title("📊 全通路電商戰情室 (Ads + Official Site)")

# 2. Google Sheet 設定
sheet_id = "17EYeSds7eV-eX4qFt3_gS8ttL-aw-ARzVJ1rwveqTZ4"
gid_google = "0" 
gid_meta = "1891939344"  # [⚠️請確認] Meta 分頁 GID
gid_site = "1703192625" # 官網後台數據 GID

url_google = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_google}"
url_meta = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_meta}"
url_site = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_site}"

# === 🎨 定義品牌顏色 ===
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
        st.error(f"無法讀取資料，請檢查 GID 或權限。錯誤: {e}")
        return pd.DataFrame(), pd.DataFrame()

    # --- A. 處理廣告數據 (加入區間拆解邏輯) ---
    df_g['Platform'] = 'Google'
    df_m['Platform'] = 'Meta'
    
    # 數值清理
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
        
        # 確保日期格式正確
        df['廣告期間(起)'] = pd.to_datetime(df['廣告期間(起)'], errors='coerce')
        df['廣告期間(迄)'] = pd.to_datetime(df['廣告期間(迄)'], errors='coerce')
        
        # 若沒有迄日，預設等於起日 (當作1天)
        df['廣告期間(迄)'] = df['廣告期間(迄)'].fillna(df['廣告期間(起)'])

        if '轉換金額' in df.columns: df['轉換金額'] = df['轉換金額'].fillna(0)
    
    # 合併原始廣告數據
    common = ['Platform', '廣告活動', '廣告期間(起)', '廣告期間(迄)', '費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    existing = [c for c in common if c in df_g.columns and c in df_m.columns]
    df_raw_ads = pd.concat([df_g[existing], df_m[existing]], ignore_index=True)

    # 🔥🔥🔥 關鍵步驟：將區間數據拆解為每日數據 (Explode) 🔥🔥🔥
    expanded_rows = []
    metrics_to_split = ['費用', '曝光次數', '點擊數', '轉換', '轉換金額']
    
    for _, row in df_raw_ads.iterrows():
        start = row['廣告期間(起)']
        end = row['廣告期間(迄)']
        
        if pd.isnull(start): continue
        
        # 計算天數
        days = (end - start).days + 1
        if days < 1: days = 1
        
        # 產生該區間的所有日期
        date_range = pd.date_range(start, end, freq='D')
        
        for date in date_range:
            new_row = row.copy()
            new_row['統計日期'] = date # 新增一個統一的日期欄位
            
            # 將數值平均分配給每一天
            for m in metrics_to_split:
                if m in row:
                    new_row[m] = row[m] / days
            
            expanded_rows.append(new_row)
            
    df_ads_daily = pd.DataFrame(expanded_rows)

    # --- B. 處理官網後台數據 ---
    site_cols_money = ['平均客單價', '營業額']
    site_cols_num = ['流量', '訂單數', '註冊會員數']

    for c in site_cols_money:
        if c in df_s.columns: df_s[c] = df_s[c].apply(clean_currency)
    for c in site_cols_num:
        if c in df_s.columns: df_s[c] = df_s[c].apply(clean_num)
        
    df_s['日期'] = pd.to_datetime(df_s['日期'], errors='coerce')
    
    return df_ads_daily, df_s

# 讀取數據 (這會花一點時間運算拆解)
df_ads, df_site = load_data()

if df_ads.empty or df_site.empty:
    st.warning("數據讀取中或部分數據缺失，請確認 GID 設定。")
    st.stop()

# 4. 側邊欄過濾器
st.sidebar.header("🎯 數據篩選")
min_date = min(df_ads['統計日期'].min(), df_site['日期'].min())
max_date = max(df_ads['統計日期'].max(), df_site['日期'].max())

date_range = st.sidebar.date_input("📅 日期區間", [min_date, max_date])
selected_platform = st.sidebar.multiselect("📱 廣告平台", df_ads['Platform'].unique(), default=df_ads['Platform'].unique())

# 應用過濾
if len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    
    # 這裡過濾的是已經拆解過的「統計日期」，所以 Top 10 不會消失了
    mask_ads = (df_ads['Platform'].isin(selected_platform)) & \
               (df_ads['統計日期'] >= start) & (df_ads['統計日期'] <= end)
    df_ads_f = df_ads[mask_ads].copy()

    mask_site = (df_site['日期'] >= start) & (df_site['日期'] <= end)
    df_site_f = df_site[mask_site].copy()
else:
    st.info("請選擇完整的開始與結束日期")
    st.stop()

# ==========================================
# 📊 第一部分：全站營運總覽
# ==========================================
st.markdown("### 🌐 全站營運與廣告貢獻分析")

# 1. 準備合併數據 (按日聚合)
# 廣告日報表 (使用拆解後的 '統計日期')
daily_ads = df_ads_f.groupby('統計日期')[['費用', '轉換金額', '點擊數', '轉換']].sum().reset_index()
daily_ads.rename(columns={'統計日期': '日期', '費用': '廣告花費', '轉換金額': '廣告營收', '點擊數': '廣告點擊', '轉換': '廣告訂單'}, inplace=True)

# 官網日報表
daily_site = df_site_f[['日期', '營業額', '流量', '訂單數', '註冊會員數']].copy()
daily_site.rename(columns={'營業額': '全站營收', '流量': '全站流量', '訂單數': '全站訂單'}, inplace=True)

# 合併 (Merge)
df_merge = pd.merge(daily_site, daily_ads, on='日期', how='left').fillna(0)

# 🔥 修正數學邏輯：自然流量營收 = 全站 - 廣告
df_merge['自然流量營收'] = df_merge['全站營收'] - df_merge['廣告營收']

# 視覺防呆：如果廣告追蹤 > 全站 (歸因落差)，自然營收顯示 0 或負數
# 為了讓堆疊圖好看，我們通常允許它顯示實際計算值，但在 KPI 卡片總和時會正確

df_merge['廣告貢獻率(%)'] = (df_merge['廣告營收'] / df_merge['全站營收'] * 100).fillna(0)

# KPI 卡片
k1, k2, k3, k4, k5 = st.columns(5)
total_site_rev = df_merge['全站營收'].sum()
total_ad_rev = df_merge['廣告營收'].sum()
organic_rev = df_merge['自然流量營收'].sum() # 這樣加總就會等於 (Total - Ad)

total_members = df_merge['註冊會員數'].sum()
ad_contrib_rate = (total_ad_rev / total_site_rev * 100) if total_site_rev > 0 else 0

k1.metric("🏠 全站總營收", f"${total_site_rev:,.0f}")
k2.metric("📢 廣告帶來營收", f"${total_ad_rev:,.0f}", delta=f"佔比 {ad_contrib_rate:.1f}%")
# 這裡顯示計算後的自然營收，確保 A + B = C
k3.metric("🌳 自然/其他營收", f"${organic_rev:,.0f}") 
k4.metric("👥 新增會員數", f"{total_members:,.0f} 人")
k5.metric("💰 廣告花費", f"${daily_ads['廣告花費'].sum():,.0f}")

st.divider()

# 圖表區
c_main1, c_main2 = st.columns(2)

with c_main1:
    st.subheader("💰 營收來源堆疊圖 (Ads vs Organic)")
    # 將數據melt成長格式
    df_rev_stack = df_merge[['日期', '廣告營收', '自然流量營收']].melt(id_vars='日期', var_name='來源', value_name='金額')
    
    # 處理負值：如果自然營收為負 (廣告>全站)，在圖表上可以過濾掉或保留
    # 這裡為了數學正確性保留，但 Plotly 堆疊圖遇到負值會有特殊表現
    
    fig_rev = px.bar(df_rev_stack, x='日期', y='金額', color='來源', 
                     title="每日營收組成：廣告 vs 自然 (加總應等於全站)",
                     color_discrete_map={'廣告營收': color_map['Google'], '自然流量營收': color_map['Organic/Direct']})
    st.plotly_chart(fig_rev, use_container_width=True)

with c_main2:
    st.subheader("👥 會員註冊趨勢")
    fig_mem = px.bar(df_merge, x='日期', y='註冊會員數', 
                     title="每日新增會員數",
                     color_discrete_sequence=['#FF9900'])
    fig_mem.add_trace(go.Scatter(x=df_merge['日期'], y=df_merge['廣告花費'], 
                                 mode='lines', name='廣告花費', yaxis='y2', line=dict(color='gray', dash='dot')))
    
    fig_mem.update_layout(yaxis2=dict(title='廣告花費', overlaying='y', side='right', showgrid=False))
    st.plotly_chart(fig_mem, use_container_width=True)


# ==========================================
# 📈 第二部分：廣告平台深入分析
# ==========================================
st.markdown("### 📢 廣告平台成效細節 (Google & Meta)")

col_p1, col_p2 = st.columns(2)

with col_p1:
    st.subheader("平台預算佔比")
    df_platform_cost = df_ads_f.groupby('Platform')['費用'].sum().reset_index()
    fig_pie = px.pie(df_platform_cost, values='費用', names='Platform', 
                     color='Platform', color_discrete_map=color_map, hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_p2:
    st.subheader("Top 10 廣告活動 (依營收)")
    
    # 修正 Top 10 空白問題：
    # 這裡使用已經拆解過日期的 df_ads_f，所以日期過濾是準確的
    df_camp = df_ads_f.groupby(['Platform', '廣告活動'])[['費用', '轉換金額']].sum().reset_index()
    
    # 計算 ROAS
    df_camp['ROAS'] = df_camp.apply(lambda x: x['轉換金額'] / x['費用'] if x['費用'] > 0 else 0, axis=1)
    
    # 排序
    df_top = df_camp.sort_values('轉換金額', ascending=True).tail(10)
    
    if not df_top.empty:
        fig_bar = px.bar(df_top, x='轉換金額', y='廣告活動', orientation='h', color='Platform',
                         title="營收最高的 10 個廣告",
                         text_auto='.0f',
                         color_discrete_map=color_map)
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("所選日期區間內無廣告數據")

with st.expander("📄 查看合併詳細報表 (全站 + 廣告)"):
    # 顯示處理後的表格，方便您核對數字
    st.dataframe(df_merge.sort_values('日期', ascending=False))
