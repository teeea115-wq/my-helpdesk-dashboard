import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Helpdesk Analytics", layout="wide")

# ฟังก์ชันคำนวณ (ก๊อปปี้ส่วนนี้ไปทั้งหมด)
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
        if actual > limit: return '🔥 เกินกำหนด'
        elif limit > 0 and (actual / limit) >= 0.8: return '⚠️ ใกล้หลุด SLA'
        else: return '🟢 ปกติ'

# โหลดข้อมูล
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSRVUhShKYRay7zI0R4LcD9YBoe9VaZHIYvSRMWNXBAMDFws78ImtPqVPAfqKSvD_4lua8dgJm1OTaG/pub?output=csv"

try:
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip()
    
    if 'วัน / เวลา (รับเรื่องร้องขอ)' in df.columns:
        df['Received_DT'] = pd.to_datetime(df['วัน / เวลา (รับเรื่องร้องขอ)'], format='%d/%m/%y %H:%M:%S', errors='coerce')
        df['Received_Date'] = df['Received_DT'].dt.date
    if 'วัน / เวลา (ปิดเคส)' in df.columns:
        df['Closed_DT'] = pd.to_datetime(df['วัน / เวลา (ปิดเคส)'], format='%d/%m/%y %H:%M:%S', errors='coerce')

    now = pd.Timestamp.now()
    df['sla_limit_minutes'] = df['SLA'].apply(parse_sla_to_mins) if 'SLA' in df.columns else 0
    df['actual_minutes_spent'] = df.apply(lambda row: calculate_actual_mins(row, now), axis=1)
    df['sla_status_label'] = df.apply(get_sla_status_label, axis=1)

    # กราฟวงกลมแบบไม่หลุดขอบ
    st.title("📊 Helpdesk Dashboard")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("สถานะงาน")
        fig1 = px.pie(df, names='สถานะ', hole=0.5)
        fig1.update_layout(margin=dict(t=80, b=80, l=80, r=80))
        st.plotly_chart(fig1, use_container_width=True)
        
    with col2:
        st.subheader("สถานะ SLA")
        fig2 = px.pie(df, names='sla_status_label', hole=0.5)
        fig2.update_layout(margin=dict(t=80, b=80, l=80, r=80))
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
