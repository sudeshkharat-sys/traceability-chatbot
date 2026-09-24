"""Simple web UI for the PFMEA pipeline: upload an Excel file, pick a
sheet (or run every sheet), and download the result with the Suggestion
columns filled in - no command line needed.

Just wraps run_pipeline.run_pipeline(); all the actual scoring logic
still lives in step5/step5c/step6 as before.

Usage:
    streamlit run app.py
"""

import os
import shutil
import tempfile
from pathlib import Path

import streamlit as st
from openpyxl import load_workbook

from run_pipeline import run_pipeline
from step4b_embed_handbook import build_index
from step5_severity_llm import SEVERITY_TABLE_TEXT, _load_dotenv_into_environ, get_reference_text

SEVERITY_RETRIEVAL_QUERY = "Severity rating table effect on customer safe vehicle operation loss of function"


def embedding_credentials_missing():
    """Same check get_embedding_model() does, but as a plain bool so app.py
    can show a st.error() instead of letting sys.exit(1) kill the Streamlit
    worker thread."""
    _load_dotenv_into_environ()
    return not os.environ.get("AZURE_API_KEY") or not os.environ.get("AZURE_EMBEDDING_ENDPOINT")

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

    st.divider()
    st.subheader("Handbook grounding (RAG)")
    st.caption(
        "By default, Severity scoring uses a fixed table text baked into the script. "
        "Upload the AIAG-VDA handbook PDF (or a prebuilt index) instead to ground it in "
        "text actually retrieved from the handbook, and preview exactly what gets sent "
        "to the LLM before running."
    )

    handbook_mode = st.radio(
        "Handbook source",
        ["None (use built-in table)", "Upload handbook PDF", "Upload prebuilt index (.json)"],
        key="handbook_mode",
    )

    handbook_index_path = None
    if handbook_mode == "Upload handbook PDF":
        pdf_file = st.file_uploader("AIAG-VDA handbook PDF", type=["pdf"], key="handbook_pdf")
        if pdf_file is not None:
            pdf_path = work_dir / pdf_file.name
            index_path = pdf_path.with_name(f"{pdf_path.stem}__handbook_index.json")
            already_built = index_path.is_file() and st.session_state.get("handbook_pdf_name") == pdf_file.name
            if not already_built:
                if embedding_credentials_missing():
                    st.error(
                        "Missing AZURE_API_KEY / AZURE_EMBEDDING_ENDPOINT - cannot embed the PDF. "
                        "Set these in the app's .env, same as the other Azure credentials."
                    )
                else:
                    pdf_path.write_bytes(pdf_file.getvalue())
                    with st.spinner("Embedding handbook PDF (one API call per chunk - only needed once per PDF)..."):
                        try:
                            build_index(pdf_path, index_path)
                        except Exception as e:
                            st.error(f"Failed to embed handbook: {e}")
                            index_path = None
                    if index_path:
                        st.session_state.handbook_pdf_name = pdf_file.name
            if index_path and index_path.is_file():
                handbook_index_path = index_path
    elif handbook_mode == "Upload prebuilt index (.json)":
        json_file = st.file_uploader("Handbook index (.json)", type=["json"], key="handbook_json")
        if json_file is not None:
            index_path = work_dir / json_file.name
            index_path.write_bytes(json_file.getvalue())
            handbook_index_path = index_path

    if handbook_index_path:
        st.success(f"Will use handbook-grounded Severity reference: {handbook_index_path.name}")
        with st.expander("Preview retrieved context (what the LLM will actually see)"):
            preview_query = st.text_input(
                "Retrieval query (this is the exact query run_pipeline uses for Severity - edit it to test a different one)",
                value=SEVERITY_RETRIEVAL_QUERY,
                key="handbook_preview_query",
            )
            if st.button("Preview retrieval", key="handbook_preview_btn"):
                if embedding_credentials_missing():
                    st.error("Missing AZURE_API_KEY / AZURE_EMBEDDING_ENDPOINT - cannot embed the query.")
                else:
                    with st.spinner("Retrieving..."):
                        try:
                            st.session_state.handbook_preview_text = get_reference_text(
                                str(handbook_index_path), preview_query, fallback_text=SEVERITY_TABLE_TEXT,
                            )
                        except Exception as e:
                            st.error(f"Retrieval failed: {e}")
            if "handbook_preview_text" in st.session_state:
                st.code(st.session_state.handbook_preview_text[:4000], language="text")
                st.caption(
                    "This same text is inserted into the Severity section of EVERY row's prompt in this run "
                    "- retrieval runs once per run, not per row, so what you see here is what every row got."
                )
    else:
        st.caption("No handbook selected - Severity scoring will use the built-in hardcoded table text.")

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
                    handbook_index_path=str(handbook_index_path) if handbook_index_path else None,
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
