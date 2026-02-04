import streamlit as st
import pandas as pd
import json
import os
import uuid
from io import BytesIO

st.set_page_config(page_title="Data Viewer", layout="wide")
st.title("📊 Data Viewer")

# Thư mục lưu shared data
SHARED_DATA_DIR = "shared_data"
os.makedirs(SHARED_DATA_DIR, exist_ok=True)

# Khởi tạo session state cho bộ lọc
if "filter_status" not in st.session_state:
    st.session_state.filter_status = "Tất cả"
if "filter_sync" not in st.session_state:
    st.session_state.filter_sync = "Tất cả"

# Kiểm tra query param để load shared data
query_params = st.query_params
shared_id = query_params.get("share", None)

lms = None
loaded_from_share = False

if shared_id:
    # Load từ shared data
    shared_file = os.path.join(SHARED_DATA_DIR, f"{shared_id}.json")
    if os.path.exists(shared_file):
        with open(shared_file, "r", encoding="utf-8") as f:
            shared_data = json.load(f)
        lms = pd.DataFrame(shared_data)
        loaded_from_share = True
        st.success(f"✅ Đã load dữ liệu từ link chia sẻ (ID: {shared_id})")
    else:
        st.error("❌ Link chia sẻ không hợp lệ hoặc đã hết hạn")

if not loaded_from_share:
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

# Hiển thị dữ liệu nếu có (từ upload hoặc từ share)
if lms is not None:
    
    # Pivot table thống kê với nút bấm
    st.subheader("📊 Thống kê theo Status và Sync (bấm vào số để lọc)")
    
    # Tạo pivot data
    pivot = pd.pivot_table(lms, index="status", columns="sync_dmn_done", aggfunc="size", fill_value=0)
    status_list = list(pivot.index)
    sync_cols = list(pivot.columns)
    
    # Header row
    header_cols = st.columns([2] + [1] * len(sync_cols) + [1])
    header_cols[0].write("**Status**")
    for i, col in enumerate(sync_cols):
        header_cols[i + 1].write(f"**sync={col}**")
    header_cols[-1].write("**Tổng**")
    
    # Data rows với buttons
    for status in status_list:
        row_cols = st.columns([2] + [1] * len(sync_cols) + [1])
        row_cols[0].write(status)
        
        for i, sync_val in enumerate(sync_cols):
            count = int(pivot.loc[status, sync_val])
            if row_cols[i + 1].button(str(count), key=f"btn_{status}_{sync_val}"):
                st.session_state.filter_status = status
                st.session_state.filter_sync = sync_val
                st.rerun()
        
        # Tổng cho mỗi status
        total = int(pivot.loc[status].sum())
        if row_cols[-1].button(str(total), key=f"btn_{status}_total"):
            st.session_state.filter_status = status
            st.session_state.filter_sync = "Tất cả"
            st.rerun()
    
    # Reset button
    if st.button("🔄 Reset bộ lọc"):
        st.session_state.filter_status = "Tất cả"
        st.session_state.filter_sync = "Tất cả"
        st.rerun()
    
    st.divider()
    
    # Bộ lọc
    st.subheader("🔍 Bộ lọc")
    col_filter1, col_filter2 = st.columns(2)
    
    status_options = ["Tất cả"] + list(lms["status"].dropna().unique())
    sync_options = ["Tất cả", True, False]
    
    with col_filter1:
        status_index = status_options.index(st.session_state.filter_status) if st.session_state.filter_status in status_options else 0
        selected_status = st.selectbox("Lọc theo Status", status_options, index=status_index)
        st.session_state.filter_status = selected_status
    
    with col_filter2:
        sync_index = sync_options.index(st.session_state.filter_sync) if st.session_state.filter_sync in sync_options else 0
        selected_sync = st.selectbox("Lọc theo Sync DMN Done", sync_options, index=sync_index)
        st.session_state.filter_sync = selected_sync
    
    # Áp dụng bộ lọc
    lms_filtered = lms.copy()
    if st.session_state.filter_status != "Tất cả":
        lms_filtered = lms_filtered[lms_filtered["status"] == st.session_state.filter_status]
    if st.session_state.filter_sync != "Tất cả":
        lms_filtered = lms_filtered[lms_filtered["sync_dmn_done"] == st.session_state.filter_sync]
    
    # Hiển thị bảng dữ liệu đã lọc
    st.subheader("📗 Dữ liệu LMS (Excel)")
    st.dataframe(lms_filtered, use_container_width=True)
    st.info(f"Số dòng: {len(lms_filtered)} | Số cột: {len(lms_filtered.columns)}")
    
    # Xuất Excel dữ liệu đã lọc
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="LMS")
        return output.getvalue()
    
    # Xuất Excel tổng hợp (3 sheets)
    def to_excel_summary(lms_all):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Sheet 1: Toàn bộ dữ liệu
            lms_all.to_excel(writer, index=False, sheet_name="Data")
            
            # Sheet 2: Lỗi - status khác "Thành công"
            lms_error = lms_all[lms_all["status"] != "Thành công"]
            lms_error.to_excel(writer, index=False, sheet_name="Loi")
            
            # Sheet 3: Thành công nhưng chưa sync
            lms_not_sync = lms_all[(lms_all["status"] == "Thành công") & (lms_all["sync_dmn_done"] == False)]
            lms_not_sync.to_excel(writer, index=False, sheet_name="Chua_Sync")
        return output.getvalue()
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        excel_data = to_excel(lms_filtered)
        st.download_button(
            label="📥 Xuất Excel (dữ liệu đang lọc)",
            data=excel_data,
            file_name="lms_filtered.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col_btn2:
        excel_summary = to_excel_summary(lms)
        st.download_button(
            label="📥 Xuất Excel Tổng hợp (3 sheets)",
            data=excel_summary,
            file_name="lms_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col_btn3:
        if st.button("🔗 Tạo link chia sẻ"):
            # Tạo unique ID
            share_id = str(uuid.uuid4())[:8]
            shared_file = os.path.join(SHARED_DATA_DIR, f"{share_id}.json")
            
            # Lưu data ra file JSON
            lms.to_json(shared_file, orient="records", force_ascii=False, indent=2)
            
            # Tạo link chia sẻ
            share_url = f"?share={share_id}"
            st.session_state.share_url = share_url
            st.session_state.share_id = share_id
        
        if "share_url" in st.session_state:
            st.success(f"✅ Đã tạo link chia sẻ!")
            st.code(f"http://localhost:8501{st.session_state.share_url}")
            st.caption(f"ID: {st.session_state.share_id}")
else:
    if not shared_id:
        st.warning("Chưa upload file Excel")
