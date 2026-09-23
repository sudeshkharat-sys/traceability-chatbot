"""Simple web UI for the PFMEA pipeline: upload an Excel file, pick a
sheet (or run every sheet), and download the result with the Suggestion
columns filled in - no command line needed.

Just wraps run_pipeline.run_pipeline(); all the actual scoring logic
still lives in step5/step5c/step6 as before.

Usage:
    streamlit run app.py
"""

import shutil
import tempfile
from pathlib import Path

import streamlit as st
from openpyxl import load_workbook

from run_pipeline import run_pipeline

st.set_page_config(page_title="PFMEA AI Suggestions", layout="centered")
st.title("PFMEA AI Suggestions")
st.caption("Upload a PFMEA Excel file, choose what to run it on, and download the result with Severity/Detection/Prevention suggestions filled in.")

uploaded_file = st.file_uploader("Upload PFMEA Excel file", type=["xlsx"])

if uploaded_file is not None:
    # Work in a per-session temp dir so concurrent users / re-uploads don't
    # collide, and the original upload is never modified in place.
    if "work_dir" not in st.session_state or st.session_state.get("uploaded_name") != uploaded_file.name:
        st.session_state.work_dir = tempfile.mkdtemp(prefix="pfmea_ui_")
        st.session_state.uploaded_name = uploaded_file.name

    work_dir = Path(st.session_state.work_dir)
    source_path = work_dir / uploaded_file.name
    source_path.write_bytes(uploaded_file.getvalue())

    try:
        wb = load_workbook(source_path, read_only=True)
        sheet_names = wb.sheetnames
    except Exception as e:
        st.error(f"Could not read this Excel file: {e}")
        st.stop()

    st.success(f"Loaded '{uploaded_file.name}' - {len(sheet_names)} sheet(s) found.")

    scope = st.radio("What do you want to run this on?", ["Run on all sheets", "Choose specific sheet(s)"])
    if scope == "Choose specific sheet(s)":
        chosen_sheets = st.multiselect("Sheet(s) to process", sheet_names, default=sheet_names[:1])
    else:
        chosen_sheets = None  # None = every sheet, same as the CLI's default

    with st.expander("Advanced options"):
        repeat = st.number_input(
            "Repeat count (LLM calls per row, majority vote)",
            min_value=1, max_value=5, value=3,
            help="Higher = more resistant to single-call sampling noise, but more API calls/cost.",
        )
        merge_mode = st.checkbox(
            "Merge mode",
            value=True,
            help="When a Failure Mode cell has 2+ modes merged into one, fold each sub-mode's Severity/Detection/Prevention directly into the main columns as 'A = .../B = ...' instead of separate Sub-mode columns.",
        )
        cross_review = st.checkbox(
            "Run cross-row consistency check",
            value=True,
            help="A second AI pass over the whole sheet that flags rows scored inconsistently vs. a mechanically similar row (see AI Review column).",
        )

    run_disabled = scope == "Choose specific sheet(s)" and not chosen_sheets
    if st.button("Run", type="primary", disabled=run_disabled):
        log_box = st.empty()
        log_lines = []

        def ui_log(msg):
            log_lines.append(str(msg))
            log_box.code("\n".join(log_lines[-40:]))  # last 40 lines is enough to show progress

        with st.spinner("Scoring with the LLM - this calls the API once per row (x repeat), so it can take a while for a large sheet..."):
            try:
                output_path = run_pipeline(
                    source_path,
                    sheet_names=chosen_sheets,
                    repeat=int(repeat),
                    # output_path=None lets run_pipeline() pick the name based
                    # on merge_mode itself ("__merge_mode.xlsx" vs.
                    # "__with_suggestions.xlsx"), same as the CLI - so the
                    # downloaded filename actually reflects which mode ran.
                    output_path=None if merge_mode else work_dir / f"{source_path.stem}__with_suggestions.xlsx",
                    merge_mode=merge_mode,
                    cross_review=cross_review,
                    log=ui_log,
                )
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                st.stop()

        st.success("Done.")
        with open(output_path, "rb") as fh:
            st.download_button(
                "Download result",
                data=fh.read(),
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
