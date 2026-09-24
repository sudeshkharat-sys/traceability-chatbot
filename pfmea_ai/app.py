"""Simple web UI for the PFMEA pipeline: upload an Excel file, pick a
sheet (or run every sheet), and download the result with the Suggestion
columns filled in - no command line needed.

Just wraps run_pipeline.run_pipeline(); all the actual scoring logic
still lives in step5/step5c/step6 as before.

Usage:
    streamlit run app.py
"""

import hashlib
import os
import tempfile
from pathlib import Path

import streamlit as st
from openpyxl import load_workbook

from run_pipeline import run_pipeline
from step4b_embed_handbook import build_index
from step5_severity_llm import SEVERITY_TABLE_TEXT, _load_dotenv_into_environ, get_reference_text

SEVERITY_RETRIEVAL_QUERY = "Severity rating table effect on customer safe vehicle operation loss of function"

# step4b_embed_handbook.py already produced aiag-vda-fmea-handbook-1__handbook_index.json
# (the AIAG-VDA handbook, pre-embedded, sitting next to this script) - reuse THAT by
# default instead of asking for a fresh PDF upload + re-embedding every session.
BUNDLED_HANDBOOK_INDEXES = sorted(Path(__file__).parent.glob("*__handbook_index.json"))


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
    # Deterministic (not random mkdtemp) per-file work dir, keyed by name +
    # size, so it resolves to the SAME path if Streamlit restarts mid-run
    # (a crash, a manual restart) and the same file is re-uploaded - that's
    # what makes the partial-result recovery below possible: the on-disk
    # checkpoints from run_pipeline() survive even though st.session_state
    # itself was wiped by the restart.
    file_bytes = uploaded_file.getvalue()
    file_key = hashlib.sha1(f"{uploaded_file.name}:{len(file_bytes)}".encode()).hexdigest()[:16]
    work_dir = Path(tempfile.gettempdir()) / "pfmea_ui_sessions" / file_key
    work_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.work_dir = str(work_dir)
    st.session_state.uploaded_name = uploaded_file.name

    source_path = work_dir / uploaded_file.name
    if not source_path.is_file():
        source_path.write_bytes(file_bytes)

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

    bundled_options = [f"Use bundled: {p.name}" for p in BUNDLED_HANDBOOK_INDEXES]
    mode_options = bundled_options + ["Upload handbook PDF", "Upload prebuilt index (.json)", "None (use built-in table)"]
    handbook_mode = st.radio(
        "Handbook source",
        mode_options,
        # Default to the already-embedded handbook sitting next to app.py if one
        # exists - no reason to re-upload/re-embed a PDF that's already indexed.
        index=0,
        key="handbook_mode",
    )

    handbook_index_path = None
    if handbook_mode in bundled_options:
        handbook_index_path = BUNDLED_HANDBOOK_INDEXES[bundled_options.index(handbook_mode)]
    elif handbook_mode == "Upload handbook PDF":
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

    top_k = 3
    if handbook_index_path:
        top_k = st.number_input(
            "top_k (how many handbook chunks to retrieve per query)",
            min_value=1, max_value=10, value=3,
            help=(
                "The retriever embeds the query, scores every chunk in the handbook index by cosine "
                "similarity, and keeps the top_k highest-scoring ones - those are concatenated together "
                "as the reference text handed to the LLM. Higher top_k = more surrounding context (safer "
                "if the right table spans multiple chunks) but a longer, noisier prompt; lower top_k = "
                "tighter and cheaper but risks missing the right chunk if it didn't score #1. 3 is the "
                "script's own default and is usually enough for one table."
            ),
            key="handbook_top_k",
        )

        preview_query = st.text_input(
            "Retrieval query (the exact query run_pipeline uses for Severity - edit it to test a different one)",
            value=SEVERITY_RETRIEVAL_QUERY,
            key="handbook_preview_query",
        )

        # Auto-refresh (not gated behind a button) whenever the handbook,
        # query, or top_k changes, so what's shown here is always exactly
        # what the upcoming Run would use - never a stale preview.
        preview_key = (str(handbook_index_path), preview_query, top_k)
        if st.session_state.get("handbook_preview_key") != preview_key:
            if embedding_credentials_missing():
                st.error("Missing AZURE_API_KEY / AZURE_EMBEDDING_ENDPOINT - cannot embed the query.")
            else:
                with st.spinner("Retrieving..."):
                    try:
                        text, source = get_reference_text(
                            str(handbook_index_path), preview_query,
                            fallback_text=SEVERITY_TABLE_TEXT, top_k=int(top_k), return_source=True,
                        )
                        st.session_state.handbook_preview_text = text
                        st.session_state.handbook_preview_source = source
                        st.session_state.handbook_preview_key = preview_key
                    except Exception as e:
                        st.error(f"Retrieval failed: {e}")

        source = st.session_state.get("handbook_preview_source", "")
        if source.startswith("PDF"):
            st.success(f"Context source: {source}")
        elif source:
            st.warning(
                f"Context source: {source} - a handbook was selected, but the LLM will still get the "
                "hardcoded table, not your PDF. Check the index was built from the right PDF, or that "
                "the query actually matches content in it."
            )

        with st.expander("Context the LLM will actually receive for Severity", expanded=True):
            if "handbook_preview_text" in st.session_state:
                st.code(st.session_state.handbook_preview_text[:4000], language="text")
                st.caption(
                    "This same text is inserted into the Severity section of EVERY row's prompt in this "
                    "run - retrieval runs once per run (not per row), so what you see here is what every "
                    "row got."
                )
    else:
        st.caption("No handbook selected - Severity scoring will use the built-in hardcoded table text (source: fallback).")

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

        st.caption("Cost tracking")
        estimate_cost = st.checkbox(
            "Estimate cost (USD)",
            value=False,
            help="Token counts always show after a run (real numbers from Azure's usage_metadata, not "
                 "an estimate). Turning this on additionally multiplies them by the $/1K rates below to "
                 "estimate cost - enter your actual Azure deployment pricing, since it isn't looked up "
                 "automatically and varies by model/region.",
        )
        price_per_1k_input = price_per_1k_output = None
        if estimate_cost:
            cost_col1, cost_col2 = st.columns(2)
            with cost_col1:
                price_per_1k_input = st.number_input(
                    "$ per 1K input tokens", min_value=0.0, value=0.0, step=0.0001, format="%.4f",
                )
            with cost_col2:
                price_per_1k_output = st.number_input(
                    "$ per 1K output tokens", min_value=0.0, value=0.0, step=0.0001, format="%.4f",
                )

    # Mirrors run_pipeline()'s own output_path naming - computed here (not
    # left to run_pipeline's default) so its path is known BEFORE a run
    # starts, which is what lets an interrupted run's on-disk checkpoints
    # (see run_pipeline.py's row/sheet checkpoints) be found and offered
    # for download again below, even after this session's state was lost.
    output_suffix = "__merge_mode.xlsx" if merge_mode else "__with_suggestions.xlsx"
    output_path = work_dir / f"{source_path.stem}{output_suffix}"

    if output_path.is_file():
        st.info(
            f"A result file already exists for this upload at this setting ('{output_path.name}') - "
            "either from a previous completed run, or one that was interrupted partway through "
            "(the pipeline saves progress every few rows and after each sheet, so this may already "
            "contain most of the scored rows without spending any more API calls)."
        )
        with open(output_path, "rb") as fh:
            st.download_button(
                "Download existing/partial result",
                data=fh.read(),
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_existing",
            )

    run_disabled = scope == "Choose specific sheet(s)" and not chosen_sheets
    if st.button("Run", type="primary", disabled=run_disabled):
        log_box = st.empty()
        log_lines = []

        def ui_log(msg):
            log_lines.append(str(msg))
            log_box.code("\n".join(log_lines[-40:]))  # last 40 lines is enough to show progress

        usage_rows = []
        with st.spinner("Scoring with the LLM - this calls the API once per row (x repeat), so it can take a while for a large sheet..."):
            try:
                output_path = run_pipeline(
                    source_path,
                    sheet_names=chosen_sheets,
                    repeat=int(repeat),
                    output_path=output_path,
                    handbook_index_path=str(handbook_index_path) if handbook_index_path else None,
                    top_k=int(top_k),
                    merge_mode=merge_mode,
                    cross_review=cross_review,
                    log=ui_log,
                    usage_rows=usage_rows,
                    price_per_1k_input=price_per_1k_input,
                    price_per_1k_output=price_per_1k_output,
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

        if usage_rows:
            st.subheader("Token usage per row (Severity scoring)")
            st.caption(
                "Real counts from Azure's usage_metadata per API response - not an estimate. Each row's "
                f"total covers all {int(repeat)} repeat call(s) for that row. Doesn't include the separate "
                "merged-mode split-scoring or cross-row review calls."
            )
            st.dataframe(usage_rows, use_container_width=True)

            total_in = sum(r["input_tokens"] for r in usage_rows)
            total_out = sum(r["output_tokens"] for r in usage_rows)
            total_tokens = sum(r["total_tokens"] for r in usage_rows)
            summary = f"**{len(usage_rows)} row(s)** scored - input: **{total_in:,}** tokens, output: **{total_out:,}** tokens, total: **{total_tokens:,}** tokens"
            if price_per_1k_input is not None:
                total_cost = sum(r["cost_usd"] for r in usage_rows if r["cost_usd"] is not None)
                summary += f", estimated cost: **${total_cost:.4f}**"
            st.markdown(summary)
