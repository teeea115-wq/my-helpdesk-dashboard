import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ==========================================
# 1. ตั้งค่าหน้าเว็บ & CSS (แก้ไขปัญหาช่องวันที่ดำ)
# ==========================================
st.set_page_config(page_title="Helpdesk Executive Analytics", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Prompt', sans-serif !important; }
    
    .stApp { background-color: #F8FAFC; }
    
    /* การ์ดกราฟและตาราง */
    div.stPlotlyChart, div[data-testid="stDataFrame"] {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        border: 1px solid #E2E8F0;
        margin-bottom: 24px; 
    }

    /* --- 🛠 แก้ไข Sidebar (สไตล์ Enterprise ไม่ดำปึ๊ด) --- */
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E2E8F0; }
    
    /* สั่งเฉพาะหัวข้อและป้ายชื่อให้เป็นสีดำ */
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { 
        color: #0F172A !important; 
        font-weight: 600 !important; 
    }
    
    /* แต่งกล่อง Multiselect และ Date Input ให้เป็นโทนเดียวกัน */
    div[data-baseweb="select"] > div, 
    div[data-testid="stDateInput"] > div, 
    div[data-testid="stDateInput"] input {
        background-color: #F8FAFC !important; 
        border: 1px solid #CBD5E1 !important; 
        border-radius: 8px !important;
        color: #0F172A !important; /* ตัวเลขวันที่ในช่องจะเป็นสีดำ */
    }
    
    /* ป้าย Tag ในช่องเลือก (Multiselect) */
    span[data-baseweb="tag"] { 
        background-color: #E0E7FF !important; 
        color: #3730A3 !important; 
        border-radius: 4px; 
        font-weight: 600; 
    }
</style>
""", unsafe_allow_html=True)

# ฟังก์ชัน KPI Card แบบเรียบหรู
def create_kpi_card(title, value, accent_color, bg_icon_color):
    html = f"""
    <div style="background-color: #ffffff; padding: 24px 20px; border-radius: 12px; 
                border: 1px solid #E2E8F0; border-top: 4px solid {accent_color}; 
                box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1); margin-bottom: 20px;">
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
    if row.get('สถานะ') in ['ปิด Case', 'เสร็จสิ้น']:
        if pd.notna(row.get('Received_DT')) and pd.notna(row.get('Closed_DT')):
            return (row['Closed_DT'] - row['Received_DT']).total_seconds() / 60
        return 0
    else:
        if pd.notna(row.get('Received_DT')):
            return (now - row['Received_DT']).total_seconds() / 60
        return 0

def get_sla_status_label(row):
    limit = row.get('sla_limit_minutes', 0)
    actual = row.get('actual_minutes_spent', 0)
    if row.get('สถานะ') in ['ปิด Case', 'เสร็จสิ้น']:
        return '✅ ภายใน SLA' if actual <= limit else '❌ เกิน SLA (ปิดแล้ว)'
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
    
    now = pd.Timestamp.now()
    if 'SLA' in df.columns:
        df['sla_limit_minutes'] = df['SLA'].apply(parse_sla_to_mins)
        df['actual_minutes_spent'] = df.apply(lambda row: calculate_actual_mins(row, now), axis=1)
        df['sla_status_label'] = df.apply(get_sla_status_label, axis=1)
    return df

try:
    df = load_and_prep_data(SHEET_URL)
    
    # ==========================================
    # 4. Sidebar Filter
    # ==========================================
    st.sidebar.markdown("<h2 style='color:#0F172A; font-weight: 800;'>🎯 ตัวกรองข้อมูล</h2>", unsafe_allow_html=True)
    
    min_date, max_date = df['Received_Date'].min(), df['Received_Date'].max()
    date_range = st.sidebar.date_input("📅 เลือกช่วงวันที่", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    start_date = date_range[0] if len(date_range) > 0 else min_date
    end_date = date_range[1] if len(date_range) > 1 else start_date
    df_date_filtered = df[(df['Received_Date'] >= start_date) & (df['Received_Date'] <= end_date)]

    selected_depts = st.sidebar.multiselect("🏢 เลือกแผนก (Department):", sorted(df_date_filtered['แผนก'].unique()))
    selected_status = st.sidebar.multiselect("📌 เลือกสถานะ (Status):", sorted(df_date_filtered['สถานะ'].unique()))

    df_filtered = df_date_filtered.copy()
    if selected_depts: df_filtered = df_filtered[df_filtered['แผนก'].isin(selected_depts)]
    if selected_status: df_filtered = df_filtered[df_filtered['สถานะ'].isin(selected_status)]

    # ==========================================
    # 5. Dashboard Layout
    # ==========================================
    st.markdown("<h1 style='color: #0F172A; font-weight: 800;'>📊 Helpdesk Enterprise Analytics</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; margin-top: -15px; margin-bottom: 25px;'>ข้อมูลเรียงใหม่ อ่านได้ครบ 100% ไม่หลุดขอบ</p>", unsafe_allow_html=True)

    kpi_zone = st.container()
    dept_zone = st.container()
    donuts_zone = st.container()
    table_zone = st.container()

    pro_layout = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Prompt", color="#0F172A", size=14),
        xaxis=dict(color="#0F172A", showgrid=False, tickfont=dict(size=13, weight="bold"), automargin=True), 
        yaxis=dict(color="#0F172A", showgrid=True, gridcolor="#E2E8F0", gridwidth=1, tickfont=dict(size=13, weight="bold"), automargin=True), 
        margin=dict(t=40, b=40, l=40, r=40) 
    )

    df_interactive = df_filtered.copy() 

    # --- KPI Card ---
    with kpi_zone:
        c1, c2, c3, c4 = st.columns(4)
        total = len(df_interactive)
        closed = len(df_interactive[df_interactive['สถานะ'].isin(['ปิด Case', 'เสร็จสิ้น'])])
        with c1: create_kpi_card("เคสทั้งหมด", f"{total:,}", "#3B82F6", "#EFF6FF")
        with c2: create_kpi_card("Completed", f"{closed:,}", "#10B981", "#ECFDF5")
        with c3: create_kpi_card("In Progress", f"{total-closed:,}", "#F59E0B", "#FFFBEB")
        with c4: create_kpi_card("หลุด SLA", f"{len(df_interactive[df_interactive['sla_status_label'].str.contains('❌|🔥')]):,}", "#EF4444", "#FEF2F2")

    # --- กราฟแผนก (Full Width) ---
    with dept_zone:
        section_title("ปริมาณงานแยกตามแผนก (Department Performance)", "🏢")
        dept_df = df_filtered['แผนก'].value_counts().reset_index()
        dept_df.columns = ['Department', 'Count']
        
        fig_dept = px.bar(dept_df, x='Count', y='Department', orientation='h', text='Count')
        fig_dept.update_traces(
            marker_color='#3B82F6', marker_line_color='#2563EB', marker_line_width=1,
            texttemplate='<b>%{x}</b>', textposition='outside', textfont=dict(color='#0F172A', size=15), 
            cliponaxis=False 
        )
        fig_dept.update_layout(**pro_layout)
        fig_dept.update_layout(height=max(400, len(dept_df)*45), showlegend=False, xaxis_title="", yaxis_title="")
        fig_dept.update_yaxes(categoryorder='total ascending')
        fig_dept.update_xaxes(range=[0, dept_df['Count'].max() * 1.2]) 
        
        dept_event = st.plotly_chart(fig_dept, use_container_width=True, on_select="rerun", selection_mode="points", theme=None)
        
        if dept_event and len(dept_event.selection.get("points", [])) > 0:
            clicked_dept = dept_event.selection["points"][0]["y"]
            df_interactive = df_interactive[df_interactive['แผนก'] == clicked_dept]
            st.success(f"🎯 โฟกัสข้อมูลแผนก: **{clicked_dept}**")

    # --- กราฟวงกลม 2 อัน ---
    with donuts_zone:
        col_pie1, col_pie2 = st.columns(2)
        
        with col_pie1:
            section_title("สัดส่วนสถานะงาน", "📌")
            status_df = df_interactive['สถานะ'].value_counts().reset_index()
            status_df.columns = ['Status', 'Count']
            fig_status = px.pie(status_df, names='Status', values='Count', hole=0.5)
            fig_status.update_traces(textposition='outside', textinfo='percent+label', textfont=dict(size=13, color='#0F172A', weight="bold"))
            fig_status.update_layout(**pro_layout)
            fig_status.update_layout(height=450, showlegend=False, margin=dict(t=80, b=80, l=80, r=80))
            st.plotly_chart(fig_status, use_container_width=True, theme=None)

        with col_pie2:
            section_title("สัดส่วนสถานะ SLA", "⏱️")
            sla_df = df_interactive['sla_status_label'].value_counts().reset_index()
            sla_df.columns = ['SLA_Status', 'Count']
            fig_sla = px.pie(sla_df, names='SLA_Status', values='Count', hole=0.5,
                            color_discrete_map={'✅ ภายใน SLA':'#10B981', '❌ เกิน SLA (ปิดแล้ว)':'#EF4444', '🔥 เกินกำหนด (รีบปิดด่วน!)':'#B91C1C'})
            fig_sla.update_traces(textposition='outside', textinfo='percent+label', textfont=dict(size=13, color='#0F172A', weight="bold"))
            fig_sla.update_layout(**pro_layout)
            fig_sla.update_layout(height=450, showlegend=False, margin=dict(t=80, b=80, l=80, r=80))
            st.plotly_chart(fig_sla, use_container_width=True, theme=None)

    # --- ตารางข้อมูล ---
    with table_zone:
        st.markdown("---")
        section_title("รายละเอียดเคสทั้งหมด (Raw Data Log)", "🔍")
        st.dataframe(df_interactive, use_container_width=True, height=500, hide_index=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")

