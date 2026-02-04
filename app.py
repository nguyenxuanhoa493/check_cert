import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Data Viewer", layout="wide")
st.title("📊 Data Viewer")

# Upload files trên cùng 1 hàng
col_upload1, col_upload2 = st.columns(2)

with col_upload1:
    st.subheader("1. Upload file Excel (LMS)")
    file1 = st.file_uploader("Chọn file Excel", type=["xlsx", "xls"], key="excel")

with col_upload2:
    st.subheader("2. Upload file CSV (DMS)")
    file2 = st.file_uploader("Chọn file CSV", type=["csv"], key="csv")

st.divider()

# Header cho LMS
lms_headers = ["user_name", "user-code", "org", "code_syllabus", "syllabus", "data", "status", "date"]

# Đọc DMS trước để có thể check sync
dms = None
if file2 is not None:
    dms = pd.read_csv(file2)

# Đọc và hiển thị dữ liệu
if file1 is not None:
    lms = pd.read_excel(file1, skiprows=5, header=None, names=lms_headers)
    
    # Parse cột data từ JSON và flatten
    def parse_json(x):
        try:
            return json.loads(x) if pd.notna(x) and x else {}
        except:
            return {}
    
    data_parsed = lms["data"].apply(parse_json)
    data_flat = pd.json_normalize(data_parsed)
    
    # Xóa cột data cũ và nối các cột mới
    lms = pd.concat([lms.drop(columns=["data"]), data_flat], axis=1)
    
    # Thêm cột sync_dmn_done: True nếu CERTIFICATENUMBER tồn tại trong DMS
    if dms is not None and "CERTIFICATENUMBER" in lms.columns and "CERTIFICATENUMBER" in dms.columns:
        dms_cert_set = set(dms["CERTIFICATENUMBER"].dropna().astype(str))
        lms["sync_dmn_done"] = lms["CERTIFICATENUMBER"].astype(str).isin(dms_cert_set)
    else:
        lms["sync_dmn_done"] = False
    
    # Pivot table thống kê
    st.subheader("📊 Thống kê theo Status và Sync")
    pivot = pd.pivot_table(lms, index="status", columns="sync_dmn_done", aggfunc="size", fill_value=0)
    pivot.columns = [f"sync_dmn_done={col}" for col in pivot.columns]
    pivot["Tổng"] = pivot.sum(axis=1)
    st.dataframe(pivot, use_container_width=True)
    
    st.divider()
    
    # Bộ lọc
    st.subheader("🔍 Bộ lọc")
    col_filter1, col_filter2 = st.columns(2)
    
    with col_filter1:
        status_options = ["Tất cả"] + list(lms["status"].dropna().unique())
        selected_status = st.selectbox("Lọc theo Status", status_options)
    
    with col_filter2:
        sync_options = ["Tất cả", True, False]
        selected_sync = st.selectbox("Lọc theo Sync DMN Done", sync_options)
    
    # Áp dụng bộ lọc
    lms_filtered = lms.copy()
    if selected_status != "Tất cả":
        lms_filtered = lms_filtered[lms_filtered["status"] == selected_status]
    if selected_sync != "Tất cả":
        lms_filtered = lms_filtered[lms_filtered["sync_dmn_done"] == selected_sync]
    
    # Hiển thị bảng dữ liệu đã lọc
    st.subheader("📗 Dữ liệu LMS (Excel)")
    st.dataframe(lms_filtered, use_container_width=True)
    st.info(f"Số dòng: {len(lms_filtered)} | Số cột: {len(lms_filtered.columns)}")
    
    # Xuất Excel
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="LMS")
        return output.getvalue()
    
    excel_data = to_excel(lms_filtered)
    st.download_button(
        label="📥 Xuất Excel",
        data=excel_data,
        file_name="lms_filtered.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("Chưa upload file Excel")
