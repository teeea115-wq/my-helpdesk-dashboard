import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ==========================================
# 1. ตั้งค่าหน้าเว็บ & CSS (แก้ปัญหาช่องวันที่ดำ)
# ==========================================
st.set_page_config(page_title="Helpdesk Executive Analytics", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Prompt', sans-serif !important; }
    
    .stApp { background-color: #F8FAFC; }
    
    /* การ์ดกราฟและตาราง */
    div.stPlotlyChart, div[data-testid="stDataFrame"] {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }

    /* --- 🛠 แก้ไข Sidebar (ไม่ให้ช่องวันที่ดำ) --- */
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E2E8F0; }
    
    /* เน้นเฉพาะหัวข้อและตัวหนังสือทั่วไป ไม่ไปทับ Widget */
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { 
        color: #0F172A !important; 
        font-weight: 600 !important; 
    }

    /* ปรับแต่งช่อง Multiselect และ Date Input ให้ดูโปร */
    div[data-baseweb="select"] > div, div[data-testid="stDateInput"] > div {
        background-color: #F8FAFC !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# ฟังก์ชัน KPI Card
def create_kpi_card(title, value, accent_color, bg_icon_color):
    html = f"""
    <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; 
                border: 1px solid #E2E8F0; border-top: 5px solid {accent_color}; 
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px;">
        <p style="color: #64748B; font-size: 14px; font-weight: 700; margin: 0;">{title}</p>
        <h1 style="color: #0F172A; font-size: 36px; font-weight: 800; margin: 0;">{value}</h1>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 2. ฟังก์ชันคำนวณ (Business Logic)
# ==========================================
def parse_sla_to_mins(sla_text):
    if pd.isna(sla_text): return 0
    text = str(sla_text)
    days = sum(map(int, re.findall(r'(\d+)\s*วัน', text)))
    hours = sum(map(int, re.findall(r'(\d+)\s*ชั่วโมง', text)))
    mins = sum(map(int, re.findall(r'(\d+)\s*นาที', text)))
    return (days * 1440) + (hours * 60) + mins

def calculate_actual_mins(row, now):
    status = row.get('สถานะ', '')
    if status in ['ปิด Case', 'เสร็จสิ้น']:
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
    status = row.get('สถานะ', '')
    if status in ['ปิด Case', 'เสร็จสิ้น']:
        return '✅ ภายใน SLA' if actual <= limit else '❌ เกิน SLA (ปิดแล้ว)'
    else:
        if actual > limit: return '🔥 เกินกำหนด'
        elif limit > 0 and (actual / limit) >= 0.8: return '⚠️ ใกล้หลุด SLA'
        else: return '🟢 ปกติ'

# ==========================================
# 3. โหลดข้อมูล
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
    df['sla_limit_minutes'] = df['SLA'].apply(parse_sla_to_mins) if 'SLA' in df.columns else 0
    df['actual_minutes_spent'] = df.apply(lambda row: calculate_actual_mins(row, now), axis=1)
    df['sla_status_label'] = df.apply(get_sla_status_label, axis=1)
    return df

try:
    df = load_and_prep_data(SHEET_URL)
    
    # --- Sidebar Filter ---
    st.sidebar.header("🎯 Filter")
    min_date, max_date = df['Received_Date'].min(), df['Received_Date'].max()
    date_range = st.sidebar.date_input("📅 ช่วงวันที่", value=(min_date, max_date))
    
    # กรองข้อมูลเบื้องต้น
    df_filtered = df.copy()
    if len(date_range) == 2:
        df_filtered = df_filtered[(df_filtered['Received_Date'] >= date_range[0]) & (df_filtered['Received_Date'] <= date_range[1])]

    selected_depts = st.sidebar.multiselect("🏢 เลือกแผนก", sorted(df['แผนก'].unique()))
    if selected_depts:
        df_filtered = df_filtered[df_filtered['แผนก'].isin(selected_depts)]

    # --- Dashboard Layout ---
    st.title("📊 Helpdesk Executive Dashboard")
    
    # 💥 โซนที่ 1: KPI (แถวบนสุด)
    c1, c2, c3, c4 = st.columns(4)
    total = len(df_filtered)
    closed = len(df_filtered[df_filtered['สถานะ'].isin(['ปิด Case', 'เสร็จสิ้น'])])
    with c1: create_kpi_card("เคสทั้งหมด", f"{total:,}", "#3B82F6", "#EFF6FF")
    with c2: create_kpi_card("ปิดงานแล้ว", f"{closed:,}", "#10B981", "#ECFDF5")
    with c3: create_kpi_card("งานค้าง", f"{total-closed:,}", "#F59E0B", "#FFFBEB")
    with c4: create_kpi_card("หลุด SLA", f"{len(df_filtered[df_filtered['sla_status_label'].str.contains('❌|🔥')]):,}", "#EF4444", "#FEF2F2")

    st.markdown("---")

    # 💥 โซนที่ 2: กราฟแผนก (Full Width เพื่อไม่ให้ชื่อแผนกหลุดขอบ)
    st.subheader("🏢 ปริมาณงานรายแผนก (คลิกที่แท่งเพื่อเจาะลึก)")
    dept_counts = df_filtered['แผนก'].value_counts().reset_index()
    dept_counts.columns = ['Department', 'Count']
    
    fig_dept = px.bar(dept_counts, x='Count', y='Department', orientation='h', text='Count',
                      color_discrete_sequence=['#3B82F6'])
    fig_dept.update_layout(
        margin=dict(l=150, r=50, t=20, b=20), # เผื่อซ้ายให้ชื่อแผนก
        xaxis_title="", yaxis_title="", 
        font=dict(family="Prompt", color="#0F172A"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    fig_dept.update_traces(textposition='outside')
    
    # 🔥 เปิดระบบคลิกแล้วเปลี่ยน (on_select)
    selected_points = st.plotly_chart(fig_dept, use_container_width=True, on_select="rerun", selection_mode="points", theme=None)
    
    df_final = df_filtered.copy()
    if selected_points and len(selected_points.selection.get("points", [])) > 0:
        dept_name = selected_points.selection["points"][0]["y"]
        df_final = df_final[df_final['แผนก'] == dept_name]
        st.success(f"🎯 กำลังแสดงข้อมูลเฉพาะ: **{dept_name}** (ดับเบิลคลิกที่กราฟเพื่อรีเซ็ต)")

    # 💥 โซนที่ 3: กราฟวงกลม 2 อัน (แบ่งคนละครึ่งแต่ขยายขอบ)
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📌 สัดส่วนสถานะงาน")
        fig_status = px.pie(df_final, names='สถานะ', hole=0.5)
        fig_status.update_layout(
            margin=dict(t=80, b=80, l=80, r=80), # เผื่อขอบรอบทิศไม่ให้ตัวเลขหาย
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_status, use_container_width=True, theme=None)

    with col_right:
        st.subheader("⏱️ สัดส่วน SLA")
        fig_sla = px.pie(df_final, names='sla_status_label', hole=0.5,
                        color_discrete_map={'✅ ภายใน SLA':'#10B981', '❌ เกิน SLA (ปิดแล้ว)':'#EF4444', '🔥 เกินกำหนด':'#B91C1C', '🟢 ปกติ':'#34D399', '⚠️ ใกล้หลุด SLA':'#F59E0B'})
        fig_sla.update_layout(
            margin=dict(t=80, b=80, l=80, r=80),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_sla, use_container_width=True, theme=None)

    # 💥 โซนที่ 4: ตารางข้อมูล
    st.subheader("🔍 รายละเอียดข้อมูล")
    st.dataframe(df_final, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")
