import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ==========================================
# 1. ตั้งค่าหน้าเว็บ & CSS (Theme: Enterprise Clean)
# ==========================================
st.set_page_config(page_title="Helpdesk Executive Analytics", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Prompt', sans-serif !important; }
    
    .stApp { background-color: #F8FAFC; }
    
    div.stPlotlyChart, div[data-testid="stDataFrame"] {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        border: 1px solid #E2E8F0;
        margin-bottom: 24px; 
    }

    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E2E8F0; }
    
    /* 💥 แก้ไข: สั่งให้ตัวหนังสือดำเฉพาะหัวข้อ ไม่ลามไปทับช่องวันที่ */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #0F172A !important; font-weight: 600 !important; } 
    
    /* 💥 แก้ไข: รวมกล่อง Date Input ให้มีพื้นหลังขาว/ขอบเทา เหมือนกล่อง Multiselect */
    div[data-baseweb="select"] > div, div[data-testid="stDateInput"] > div { 
        background-color: #F8FAFC !important; 
        border: 1px solid #CBD5E1 !important; 
        border-radius: 6px !important; 
    }
    span[data-baseweb="tag"] { background-color: #E0E7FF !important; color: #3730A3 !important; border: none !important; border-radius: 4px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ฟังก์ชัน KPI Card
def create_kpi_card(title, value, accent_color, bg_icon_color):
    html = f"""
    <div style="background-color: #ffffff; padding: 24px 20px; border-radius: 12px; 
                border: 1px solid #E2E8F0; border-top: 4px solid {accent_color}; 
                box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1); margin-bottom: 20px; position: relative; overflow: hidden;">
        <p style="color: #64748B; font-size: 14px; font-weight: 700; margin: 0 0 10px 0; letter-spacing: 0.5px;">{title}</p>
        <h1 style="color: #0F172A; font-size: 40px; font-weight: 800; margin: 0; line-height: 1;">{value}</h1>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def section_title(text, icon=""):
    st.markdown(f"<h3 style='color: #0F172A; font-weight: 700; margin-top: 10px; margin-bottom: 15px;'>{icon} {text}</h3>", unsafe_allow_html=True)

# ==========================================
# 2. ฟังก์ชันคำนวณ SLA
# ==========================================
def parse_sla_to_mins(sla_text):
    if pd.isna(sla_text): return 0
    text = str(sla_text)
    days = sum(map(int, re.findall(r'(\d+)\s*วัน', text)))
    hours = sum(map(int, re.findall(r'(\d+)\s*ชั่วโมง', text)))
    mins = sum(map(int, re.findall(r'(\d+)\s*นาที', text)))
    return (days * 1440) + (hours * 60) + mins

def calculate_actual_mins(row, now):
    if row['สถานะ'] in ['ปิด Case', 'เสร็จสิ้น']:
        if pd.notna(row['Received_DT']) and pd.notna(row['Closed_DT']):
            return (row['Closed_DT'] - row['Received_DT']).total_seconds() / 60
        return 0
    else:
        if pd.notna(row['Received_DT']):
            return (now - row['Received_DT']).total_seconds() / 60
        return 0

def get_sla_status_label(row):
    limit = row['sla_limit_minutes']
    actual = row['actual_minutes_spent']
    is_closed = row['สถานะ'] in ['ปิด Case', 'เสร็จสิ้น']
    if is_closed: return '✅ ภายใน SLA' if actual <= limit else '❌ เกิน SLA (ปิดแล้ว)'
    else:
        if actual > limit: return '🔥 เกินกำหนด (รีบปิดด่วน!)'
        elif limit > 0 and (actual / limit) >= 0.8: return '⚠️ ใกล้หลุด SLA (เร่งมือ)'
        else: return '🟢 ปกติ'

# ==========================================
# 3. โหลดและจัดการข้อมูล
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSRVUhShKYRay7zI0R4LcD9YBoe9VaZHIYvSRMWNXBAMDFws78ImtPqVPAfqKSvD_4lua8dgJm1OTaG/pub?output=csv"

@st.cache_data(ttl=300)
def load_and_prep_data(url):
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip() 
    if 'วัน / เวลา (รับเรื่องร้องขอ)' in df.columns:
        df['Received_DT'] = pd.to_datetime(df['วัน / เวลา (รับเรื่องร้องขอ)'], format='%d/%m/%y %H:%M:%S', errors='coerce')
        df['Received_Date'] = df['Received_DT'].dt.date
    if 'วัน / เวลา (ปิดเคส)' in df.columns:
        df['Closed_DT'] = pd.to_datetime(df['วัน / เวลา (ปิดเคส)'], format='%d/%m/%y %H:%M:%S', errors='coerce')

    df['แผนก'] = df.get('แผนก', pd.Series(['ไม่ระบุ']*len(df))).fillna('ไม่ระบุ')
    df['สถานะ'] = df.get('สถานะ', pd.Series(['ไม่ระบุ']*len(df))).fillna('ไม่ระบุ')
    df['Category'] = df.get('Category', pd.Series(['ไม่ระบุ']*len(df))).fillna('ไม่ระบุ')
    df['Sub Category'] = df.get('Sub Category', pd.Series(['ไม่ระบุ']*len(df))).fillna('ไม่ระบุ')

    now = pd.Timestamp.now()
    if 'SLA' in df.columns:
        df['sla_limit_minutes'] = df['SLA'].apply(parse_sla_to_mins)
        df['actual_minutes_spent'] = df.apply(lambda row: calculate_actual_mins(row, now), axis=1)
        df['sla_status_label'] = df.apply(get_sla_status_label, axis=1)
    else:
        df['sla_status_label'] = 'ไม่พบข้อมูล SLA'
    return df

try:
    df = load_and_prep_data(SHEET_URL)
    
    # ==========================================
    # 4. Sidebar Filter (กรองอิสระข้ามกลุ่ม 100%)
    # ==========================================
    st.sidebar.markdown("<h2 style='color:#0F172A; font-weight: 800;'>🎯 ตัวกรองข้อมูล</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    
    min_date, max_date = df['Received_Date'].min(), df['Received_Date'].max()
    date_range = st.sidebar.date_input("📅 ช่วงเวลา (Date Range)", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    start_date = date_range[0] if len(date_range) > 0 else min_date
    end_date = date_range[1] if len(date_range) > 1 else start_date
    df_date_filtered = df[(df['Received_Date'] >= start_date) & (df['Received_Date'] <= end_date)]

    all_depts = sorted(df_date_filtered['แผนก'].unique())
    all_status = sorted(df_date_filtered['สถานะ'].unique())
    all_sla = sorted(df_date_filtered['sla_status_label'].unique())

    selected_depts = st.sidebar.multiselect("🏢 แผนก (Department):", all_depts)
    selected_status = st.sidebar.multiselect("📌 สถานะ (Status):", all_status)
    selected_sla = st.sidebar.multiselect("⏱️ เกณฑ์ SLA:", all_sla)

    df_filtered = df_date_filtered.copy()
    if selected_depts: df_filtered = df_filtered[df_filtered['แผนก'].isin(selected_depts)]
    if selected_status: df_filtered = df_filtered[df_filtered['สถานะ'].isin(selected_status)]
    if selected_sla: df_filtered = df_filtered[df_filtered['sla_status_label'].isin(selected_sla)]

    # ==========================================
    # 5. Dashboard Layout
    # ==========================================
    st.markdown("<h1 style='color: #0F172A; font-weight: 800;'>📊 Helpdesk Enterprise Analytics</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; margin-top: -15px; margin-bottom: 25px;'>คลิกที่แท่งกราฟแผนก เพื่อดูข้อมูลเจาะลึก | ดับเบิลคลิกเพื่อยกเลิก</p>", unsafe_allow_html=True)

    kpi_zone = st.container()
    trend_zone = st.container()
    donuts_zone = st.container()
    dept_zone = st.container()
    table_zone = st.container()

    pro_layout = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Prompt", color="#0F172A", size=14),
        xaxis=dict(color="#0F172A", showgrid=False, tickfont=dict(size=13, weight="bold"), automargin=True), 
        yaxis=dict(color="#0F172A", showgrid=True, gridcolor="#E2E8F0", gridwidth=1, tickfont=dict(size=13, weight="bold"), automargin=True), 
        margin=dict(t=40, b=40, l=40, r=40) 
    )

    df_interactive = df_filtered.copy() 

    # --- กราฟแผนก ---
    with dept_zone:
        section_title("ปริมาณงานแยกตามแผนก (Department Performance)", "🏢")
        dept_df = df_filtered['แผนก'].value_counts().reset_index()
        dept_df.columns = ['Department', 'Count']
        chart_height = max(500, len(dept_df) * 45) 
        
        fig_dept = px.bar(dept_df, x='Count', y='Department', orientation='h', text='Count')
        fig_dept.update_traces(
            marker_color='#3B82F6', marker_line_color='#2563EB', marker_line_width=1,
            texttemplate='<b>%{x}</b>', textposition='outside', textfont=dict(color='#0F172A', size=15), 
            cliponaxis=False 
        )
        fig_dept.update_layout(**pro_layout)
        fig_dept.update_layout(height=chart_height, showlegend=False, xaxis_title="", yaxis_title="")
        fig_dept.update_yaxes(categoryorder='total ascending')
        fig_dept.update_xaxes(range=[0, dept_df['Count'].max() * 1.15] if not dept_df.empty else [0, 100]) 
        
        dept_event = st.plotly_chart(fig_dept, use_container_width=True, on_select="rerun", selection_mode="points", theme=None)
        
        if dept_event and len(dept_event.selection.get("points", [])) > 0:
            clicked_dept = dept_event.selection["points"][0]["y"]
            df_interactive = df_interactive[df_interactive['แผนก'] == clicked_dept]
            st.success(f"🎯 โฟกัสข้อมูลแผนก: **{clicked_dept}**")

    # --- เติม KPI ---
    with kpi_zone:
        c1, c2, c3, c4, c5 = st.columns(5)
        total = len(df_interactive)
        closed = len(df_interactive[df_interactive['สถานะ'].isin(['ปิด Case', 'เสร็จสิ้น'])])
        open_cases = total - closed
        sla_breached = len(df_interactive[df_interactive['sla_status_label'].isin(['❌ เกิน SLA (ปิดแล้ว)', '🔥 เกินกำหนด (รีบปิดด่วน!)'])])
        sla_warning = len(df_interactive[df_interactive['sla_status_label'] == '⚠️ ใกล้หลุด SLA (เร่งมือ)'])

        with c1: create_kpi_card("Total Cases", f"{total:,}", "#3B82F6", "#EFF6FF")
        with c2: create_kpi_card("Completed", f"{closed:,}", "#10B981", "#ECFDF5")
        with c3: create_kpi_card("In Progress", f"{open_cases:,}", "#F59E0B", "#FFFBEB")
        with c4: create_kpi_card("SLA Breached", f"{sla_breached:,}", "#EF4444", "#FEF2F2")
        with c5: create_kpi_card("SLA Warning", f"{sla_warning:,}", "#FACC15", "#FEFCE8")

    # --- Trend ---
    with trend_zone:
        section_title("ปริมาณเคสรายวัน (Daily Volume Trend)", "📈")
        trend_df = df_interactive.groupby('Received_Date').size().reset_index(name='Cases')
        if not trend_df.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=trend_df['Received_Date'], y=trend_df['Cases'], mode='lines+markers+text',
                text=trend_df['Cases'], textposition='top center', textfont=dict(color='#0F172A', size=15, weight="bold"),
                line=dict(color='#2563EB', width=3, shape='spline'), 
                marker=dict(size=8, color='#FFFFFF', line=dict(width=2, color='#2563EB')),
                fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)',
                cliponaxis=False 
            ))
            fig_trend.update_layout(**pro_layout)
            fig_trend.update_layout(height=450, xaxis_title="", yaxis_title="") 
            fig_trend.update_yaxes(range=[0, trend_df['Cases'].max() * 1.3]) 
            st.plotly_chart(fig_trend, use_container_width=True, theme=None)

    # --- 💥 กราฟวงกลม 2 อัน (แก้ไม้ตาย: ถ่าง Margin ให้กว้างสุดๆ เพื่อย่อวงกลมลง) ---
    with donuts_zone:
        col_pie1, col_pie2 = st.columns(2)
        
        with col_pie1:
            section_title("สัดส่วนสถานะงาน (Status)", "📌")
            status_df = df_interactive['สถานะ'].value_counts().reset_index()
            status_df.columns = ['Status', 'Count']
            status_color_map = {
                'ปิด Case': '#10B981', 'เสร็จสิ้น': '#10B981', 
                'รับเรื่องร้องขอ': '#F59E0B', 'กำลังดำเนินการ': '#3B82F6', 'ไม่ระบุ': '#94A3B8'
            }
            fig_status = px.pie(status_df, names='Status', values='Count', hole=0.55, color='Status', color_discrete_map=status_color_map)
            fig_status.update_traces(
                textposition='outside', textinfo='percent+label', 
                textfont=dict(size=14, color='#0F172A', weight="bold"),
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            fig_status.update_layout(**pro_layout)
            # 💥 THE FIX: ถ่างระยะขอบซ้าย-ขวาเป็น 160px และบน-ล่าง 120px เพื่อบีบวงกลมให้เล็กลง Label จะได้ไม่ชนขอบ
            fig_status.update_layout(height=500, showlegend=False, margin=dict(t=120, b=120, l=160, r=160))
            st.plotly_chart(fig_status, use_container_width=True, theme=None)

        with col_pie2:
            section_title("สัดส่วนสถานะ SLA", "⏱️")
            sla_df = df_interactive['sla_status_label'].value_counts().reset_index()
            sla_df.columns = ['SLA_Status', 'Count']
            color_map = {
                '✅ ภายใน SLA': '#10B981', '🟢 ปกติ': '#34D399', 
                '⚠️ ใกล้หลุด SLA (เร่งมือ)': '#F59E0B', 
                '🔥 เกินกำหนด (รีบปิดด่วน!)': '#EF4444', '❌ เกิน SLA (ปิดแล้ว)': '#B91C1C'
            }
            fig_sla = px.pie(sla_df, names='SLA_Status', values='Count', hole=0.55, color='SLA_Status', color_discrete_map=color_map)
            fig_sla.update_traces(
                textposition='outside', textinfo='percent+label',
                textfont=dict(size=14, color='#0F172A', weight="bold"),
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            fig_sla.update_layout(**pro_layout)
            # 💥 THE FIX: ใช้ margin ชุดเดียวกันเพื่อให้ขนาดวงกลมเท่ากันพอดีเป๊ะ
            fig_sla.update_layout(height=500, showlegend=False, margin=dict(t=120, b=120, l=160, r=160))
            st.plotly_chart(fig_sla, use_container_width=True, theme=None)

    # --- โซนตาราง ---
    with table_zone:
        st.markdown("---")
        section_title("สรุปหมวดหมู่ปัญหา (Category Distribution)", "📑")
        if not df_interactive.empty:
            cat_sub_df = df_interactive.groupby(['Category', 'Sub Category']).size().reset_index(name='จำนวนเคส')
            cat_sub_df = cat_sub_df.sort_values('จำนวนเคส', ascending=False)
            max_val = int(cat_sub_df['จำนวนเคส'].max()) if not cat_sub_df.empty else 100
            st.dataframe(
                cat_sub_df, 
                use_container_width=True, height=400, hide_index=True,
                column_config={"จำนวนเคส": st.column_config.ProgressColumn("จำนวนเคส", format="%d", min_value=0, max_value=max_val)}
            )
        
        st.markdown("<br>", unsafe_allow_html=True)

        section_title("รายละเอียดเคสทั้งหมด (Raw Data Log)", "🔍")
        display_cols = ['หมายเลข Case', 'วันที่รับเรื่อง', 'แผนก', 'Category', 'Sub Category', 'สถานะ', 'SLA', 'sla_status_label']
        table_df = df_interactive.copy()
        if 'วัน / เวลา (รับเรื่องร้องขอ)' in table_df.columns: table_df['วันที่รับเรื่อง'] = table_df['วัน / เวลา (รับเรื่องร้องขอ)']
        available_cols = [c for c in display_cols if c in table_df.columns]
        
        st.dataframe(table_df[available_cols], use_container_width=True, height=500, hide_index=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการรันระบบ: {e}")

