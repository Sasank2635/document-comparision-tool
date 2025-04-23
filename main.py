import time
import json
import pandas as pd
import streamlit as st
from io import BytesIO
from GeminiAPI import upload_to_gemini, compare_pdfs, get_default_prompt

st.set_page_config(page_title="📄 PDF Document Comparison Tool", layout="wide")
st.title('📄 PDF Document Comparison Tool')


# Session state init
def init_session():
    defaults = {
        "uploaded_files": None,
        "comparison_result": None,
        "file_uploader_key": "initial",
        "reset_clicked": False,
        "rescan_clicked": False,
        "download_triggered": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session()

# ✅ Trigger reset after download
if st.session_state.download_triggered:
    st.session_state.download_triggered = False
    st.session_state.uploaded_files = None
    st.session_state.comparison_result = None
    st.session_state.file_uploader_key = str(time.time())
    st.rerun()


# Reset and Rescan button logic
def reset_comparison():
    st.session_state.uploaded_files = None
    st.session_state.comparison_result = None
    st.session_state.reset_clicked = True
    st.session_state.file_uploader_key = str(time.time())
    st.rerun()


def display_results(result_data, doc_type, prefix=""):
    prefix_text = f"{prefix}: " if prefix else ""

    # Check if we're dealing with the new nested structure for invoices
    if doc_type == "Invoices" and isinstance(result_data.get("differences"), dict):
        # New nested structure with header and line items
        header_diffs = result_data["differences"].get("header_differences", [])
        line_diffs = result_data["differences"].get("line_item_differences", [])

        if not header_diffs and not line_diffs:
            st.info(f"✅ {prefix_text}No differences detected between the two {doc_type.lower()}.")
            return

        # Display header differences if any
        if header_diffs:
            st.subheader(f"🔍 {prefix_text}Header Differences in {doc_type}:")

            table_data = [
                {
                    "S.No": idx + 1,
                    "Field": item.get("field", ""),
                    "File 1": item.get("file1_value", ""),
                    "File 2": item.get("file2_value", "")
                }
                for idx, item in enumerate(header_diffs)
            ]
            df = pd.DataFrame(table_data)

            def highlight_rows(row):
                return ['background-color: #F8F9FA' if row.name % 2 == 0 else 'background-color: #FFFFFF'] * len(row)

            st.table(df.style.apply(highlight_rows, axis=1))

        # Display line item differences if any
        if line_diffs:
            st.subheader(f"🔍 {prefix_text}Line Item Differences in {doc_type}:")

            table_data = [
                {
                    "S.No": idx + 1,
                    "Item Index": item.get("item_index", ""),
                    "Field": item.get("field", ""),
                    "File 1": item.get("file1_value", ""),
                    "File 2": item.get("file2_value", "")
                }
                for idx, item in enumerate(line_diffs)
            ]
            df = pd.DataFrame(table_data)

            def highlight_rows(row):
                return ['background-color: #F8F9FA' if row.name % 2 == 0 else 'background-color: #FFFFFF'] * len(row)

            st.table(df.style.apply(highlight_rows, axis=1))

    # Original flat structure
    elif result_data.get("differences"):
        # Check if differences is a list (original format)
        if isinstance(result_data["differences"], list):
            st.subheader(f"🔍 {prefix_text}Found Differences in {doc_type}:")

            table_data = [
                {
                    "S.No": idx + 1,
                    "Field": item.get("field", ""),
                    "File 1": item.get("file1_value", ""),
                    "File 2": item.get("file2_value", "")
                }
                for idx, item in enumerate(result_data["differences"])
            ]
            df = pd.DataFrame(table_data)

            def highlight_rows(row):
                return ['background-color: #F8F9FA' if row.name % 2 == 0 else 'background-color: #FFFFFF'] * len(row)

            st.table(df.style.apply(highlight_rows, axis=1))
        else:
            st.error("Unexpected result format. Please check the API response.")
    else:
        st.info(f"✅ {prefix_text}No differences detected between the two {doc_type.lower()}.")


# Document type selector
doc_type = st.radio("Select Document Type:", ("Invoices", "Contracts"))
st.write(f"Upload two {doc_type} for comparison.")

# File uploader
uploaded_files = st.file_uploader(
    f"Upload two {doc_type} (Max 10MB each)",
    accept_multiple_files=True,
    type=['pdf'],
    key=st.session_state.get("file_uploader_key", "initial")
)

# Optional custom prompt input
custom_prompt = st.text_area(
    "✍️ Optional: Enter a field or custom prompt",
    placeholder="e.g. Invoice Number, Currency"
)

# Toggle for including default results with custom prompt
include_default = False
if custom_prompt and custom_prompt.strip():
    include_default = st.toggle("🔄 Also show results from default prompt", value=False)

# Submit button
submit_clicked = st.button("🚀 Submit for Comparison")

# Clear reset flag
if st.session_state.reset_clicked:
    st.session_state.reset_clicked = False

# 🚀 Trigger processing
if (
        uploaded_files and len(uploaded_files) == 2 and submit_clicked
) or st.session_state.rescan_clicked:

    if not st.session_state.rescan_clicked:
        st.session_state.uploaded_files = uploaded_files

    if st.session_state.uploaded_files and len(st.session_state.uploaded_files) == 2:
        st.success(f"📂 **File 1:** {st.session_state.uploaded_files[0].name}")
        st.success(f"📂 **File 2:** {st.session_state.uploaded_files[1].name}")

        with st.spinner('🔄 Processing files...'):
            try:
                file1 = upload_to_gemini(BytesIO(st.session_state.uploaded_files[0].read()),
                                         st.session_state.uploaded_files[0].name)
                file2 = upload_to_gemini(BytesIO(st.session_state.uploaded_files[1].read()),
                                         st.session_state.uploaded_files[1].name)

                prompt_expander = st.expander("📄 Prompt Sent to Gemini")

                # Include default in response even when using custom prompt?
                include_default = True  # Set to False if you don't want both

                # Choose prompt based on logic
                used_prompt = custom_prompt.strip() if custom_prompt and custom_prompt.strip() else get_default_prompt(
                    doc_type)


                # Scrollable box style
                def scrollable_box(text):
                    return f"""
                    <div style='max-height: 250px; overflow-y: auto; padding: 0.5rem; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; white-space: pre-wrap; font-family: monospace; font-size: 0.85rem;'>{text}</div>
                    """


                with prompt_expander:
                    if custom_prompt and custom_prompt.strip():
                        st.markdown("**Custom Prompt Used:**")
                        st.markdown(scrollable_box(custom_prompt.strip()), unsafe_allow_html=True)
                        if include_default:
                            st.markdown("**Default Prompt Also Considered (Reference):**")
                            st.markdown(scrollable_box(get_default_prompt(doc_type)), unsafe_allow_html=True)
                    else:
                        st.markdown(f"**Default Prompt for {doc_type}:**")
                        st.markdown(scrollable_box(used_prompt), unsafe_allow_html=True)

                response_text = compare_pdfs(file1, file2, doc_type, custom_prompt, include_default)
                differences = json.loads(response_text)

                st.session_state.comparison_result = differences
                st.session_state.rescan_clicked = False

            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")

# ✅ Display results if available
if (
        st.session_state.comparison_result
        and st.session_state.uploaded_files
        and len(st.session_state.uploaded_files) == 2
):
    differences = st.session_state.comparison_result

    # Handle both single and dual result formats
    if "custom" in differences and "default" in differences:
        # Create tabs for custom and default results
        tab1, tab2 = st.tabs(["📊 Custom Prompt Results", "📑 Default Prompt Results"])

        # Custom results tab
        with tab1:
            # Process custom results
            display_results(differences["custom"], doc_type, "Custom Prompt")

        # Default results tab
        with tab2:
            # Process default results
            display_results(differences["default"], doc_type, "Default Prompt")
    else:
        # Single result format (either just custom or just default)
        display_results(differences, doc_type, "")

    # Download button
    json_bytes = json.dumps(differences, indent=4).encode("utf-8")
    if st.download_button(
            label=f"⬇️ Download {doc_type} Differences JSON",
            data=json_bytes,
            file_name=f"{doc_type.lower()}_differences.json",
            mime="application/json"
    ):
        st.session_state.download_triggered = True

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("🔄 Reset & Upload New Files", on_click=reset_comparison)
# ⚠️ If file count invalid
elif uploaded_files and len(uploaded_files) != 2:
    st.warning("⚠️ Please upload exactly **two** files for comparison.")
