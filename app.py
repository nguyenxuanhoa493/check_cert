import streamlit as st
import pandas as pd
import json
import requests
from io import BytesIO

st.set_page_config(page_title="Data Viewer", layout="wide")
st.title("📊 Data Viewer")

# GitHub Gist API
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, 'secrets') else None

def create_gist(data_json: str, description: str = "LMS Data Share") -> str:
    """Tạo GitHub Gist và trả về Gist ID"""
    if not GITHUB_TOKEN:
        return None
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "description": description,
        "public": False,
        "files": {
            "lms_data.json": {
                "content": data_json
            }
        }
    }
    
    response = requests.post("https://api.github.com/gists", headers=headers, json=payload)
    
    if response.status_code == 201:
        return response.json()["id"]
    return None

def load_gist(gist_id: str) -> dict:
    """Load data từ GitHub Gist"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        response = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers)
        
        if response.status_code == 200:
            gist = response.json()
            if "lms_data.json" in gist["files"]:
                file_info = gist["files"]["lms_data.json"]
                
                # Nếu file lớn, content bị truncated, cần fetch từ raw_url
                if file_info.get("truncated", False) or file_info.get("content") is None:
                    raw_url = file_info.get("raw_url")
                    if raw_url:
                        raw_response = requests.get(raw_url, headers=headers)
                        if raw_response.status_code == 200:
                            return json.loads(raw_response.text)
                else:
                    content = file_info["content"]
                    return json.loads(content)
    except Exception as e:
        st.error(f"Lỗi khi load Gist: {str(e)}")
    return None

# Khởi tạo session state cho bộ lọc
if "filter_status" not in st.session_state:
    st.session_state.filter_status = "Tất cả"
if "filter_sync" not in st.session_state:
    st.session_state.filter_sync = "Tất cả"

# Kiểm tra query param để load shared data từ Gist
query_params = st.query_params
shared_id = query_params.get("share", None)

lms = None
loaded_from_share = False

if shared_id:
    # Load từ GitHub Gist
    shared_data = load_gist(shared_id)
    if shared_data:
        lms = pd.DataFrame(shared_data)
        loaded_from_share = True
        st.success(f"✅ Đã load dữ liệu từ link chia sẻ (Gist ID: {shared_id})")
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
    lms_headers = ["user_name", "user-code", "org", "code_syllabus", "syllabus", "data", "status", "time", "response_dms"]
    
    # Đọc DMS trước để có thể check sync
    dms = None
    dms_map_id_set = set()
    if file2 is not None:
        dms = pd.read_csv(file2)
        # Tạo MAP_ID cho DMS = PRODUCERID_CERTIFICATE
        if "PRODUCERID" in dms.columns and "CERTIFICATE" in dms.columns:
            dms["MAP_ID"] = dms["PRODUCERID"].astype(str) + "_" + dms["CERTIFICATE"].astype(str)
            dms_map_id_set = set(dms["MAP_ID"].dropna().astype(str))
    
    # Đọc và hiển thị dữ liệu
    if file1 is not None:
        lms = pd.read_excel(file1, skiprows=5, header=None, names=lms_headers)
        
        # Parse cột data từ JSON và lấy CERTIFICATENUMBER, PRODUCERID, CERTIFICATE
        def parse_data_fields(x):
            try:
                data = json.loads(x) if pd.notna(x) and x else {}
                return {
                    "CERTIFICATENUMBER": data.get("CERTIFICATENUMBER", ""),
                    "PRODUCERID": data.get("PRODUCERID", ""),
                    "CERTIFICATE": data.get("CERTIFICATE", "")
                }
            except:
                return {"CERTIFICATENUMBER": "", "PRODUCERID": "", "CERTIFICATE": ""}
        
        parsed = lms["data"].apply(parse_data_fields).apply(pd.Series)
        lms["CERTIFICATENUMBER"] = parsed["CERTIFICATENUMBER"]
        lms["PRODUCERID"] = parsed["PRODUCERID"]
        lms["CERTIFICATE"] = parsed["CERTIFICATE"]
        
        # Tạo MAP_ID cho LMS = PRODUCERID_CERTIFICATE
        lms["MAP_ID"] = lms["PRODUCERID"].astype(str) + "_" + lms["CERTIFICATE"].astype(str)
        
        # Thêm cột sync_dmn_done: True nếu MAP_ID tồn tại trong DMS
        if dms is not None and len(dms_map_id_set) > 0:
            lms["sync_dmn_done"] = lms["MAP_ID"].astype(str).isin(dms_map_id_set)
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
        if GITHUB_TOKEN:
            if st.button("🔗 Tạo link chia sẻ"):
                # Tạo Gist
                data_json = lms.to_json(orient="records", force_ascii=False)
                gist_id = create_gist(data_json)
                
                if gist_id:
                    share_url = f"?share={gist_id}"
                    st.session_state.share_url = share_url
                    st.session_state.share_id = gist_id
                else:
                    st.error("❌ Không thể tạo link chia sẻ. Kiểm tra GitHub Token.")
            
            if "share_url" in st.session_state:
                st.success(f"✅ Đã tạo link chia sẻ!")
                st.code(f"https://checkcertbvl.streamlit.app/{st.session_state.share_url}")
                st.caption(f"Gist ID: {st.session_state.share_id}")
        else:
            st.warning("⚠️ Chưa cấu hình GITHUB_TOKEN trong secrets")
elif not shared_id:
    st.warning("Chưa upload file Excel")
