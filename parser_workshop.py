"""
parser_workshop.py — Parser Workshop shared UI.

Shown when Rex encounters a PDF from an unknown institution.
Provides raw text inspection, institution list, and AI-assisted
pattern suggestion for building new parser templates.

Flow:
1. User drops a single PDF -> uploader disappears, analysis starts automatically
2. Visual spinner/progress while Rex works
3. Full-width analysis result with copy button
4. Raw statement text available as a popup/dialog
5. Inline chat with Rex to resolve parsing issues
"""

from __future__ import annotations

import os
import tempfile

import streamlit as st

import parsers


# ---------------------------------------------------------------------------
# PDF text extraction with OCR fallback
# ---------------------------------------------------------------------------

def _extract_pdf_text(filepath: str) -> str:
    """
    Extract text from a PDF, with multi-strategy fallback:
    1. pdfplumber with layout tolerance
    2. pdfminer.six with utf-8 codec
    3. OCR via pdf2image + pytesseract
    Falls back through each strategy if the extracted text looks garbled.
    """
    text = ""

    # --- Strategy 1: pdfplumber with tuned tolerances ---
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            pages_text = []
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                pages_text.append(page_text)
            text = "\n".join(pages_text)
    except Exception:
        text = ""

    if _text_looks_valid(text):
        return text

    # --- Strategy 2: pdfminer with utf-8 ---
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(filepath, codec="utf-8")
    except Exception:
        text = ""

    if _text_looks_valid(text):
        return text

    # --- Strategy 3: OCR fallback ---
    try:
        import pdf2image
        import pytesseract
        pages = pdf2image.convert_from_path(filepath, dpi=300)
        ocr_parts = []
        for page_img in pages:
            ocr_parts.append(pytesseract.image_to_string(page_img))
        text = "\n".join(ocr_parts)
    except Exception:
        pass

    if _text_looks_valid(text):
        return text

    # --- Last resort: return whatever pdfplumber gave us (even if garbled) ---
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            raw_parts = []
            for page in pdf.pages:
                raw_parts.append(page.extract_text() or "")
            return "\n".join(raw_parts)
    except Exception:
        return text or "(Could not extract any text from this PDF)"


def _text_looks_valid(text: str) -> bool:
    """
    Heuristic: text is 'valid' if it has a reasonable ratio of
    alphanumeric words vs garbled glyph codes.
    """
    if not text or len(text.strip()) < 50:
        return False
    import re
    words = re.findall(r"[A-Za-z]{2,}", text[:2000])
    # If fewer than 15 recognizable words in the first 2000 chars, it's garbled
    if len(words) < 15:
        return False
    # Check ratio of normal alpha chars vs total
    alpha_chars = sum(1 for c in text[:2000] if c.isalpha())
    total_chars = len(text[:2000])
    if total_chars == 0:
        return False
    return (alpha_chars / total_chars) > 0.25


# ---------------------------------------------------------------------------
# Main workshop UI
# ---------------------------------------------------------------------------

def render_workshop(profile: str = "q42") -> None:
    """
    Render the Parser Workshop page.

    ``profile`` is either 'q' (personal finance) or 'q42' (tax mode).
    It determines which session-state keys to use for pending files.
    """
    st.markdown("## Parser Workshop")

    pending_key = f"{profile}_workshop_pending"
    analysis_key = f"{profile}_workshop_analysis"
    analyzing_key = f"{profile}_workshop_analyzing"
    chat_key = f"{profile}_workshop_chat_history"

    if pending_key not in st.session_state:
        st.session_state[pending_key] = []
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    pending: list[dict] = st.session_state.get(pending_key, [])

    # --- Show file uploader ONLY if no file is loaded ---
    if not pending:
        st.markdown(
            "Drop a bank statement PDF here and Rex will automatically analyze it."
        )
        uploaded = st.file_uploader(
            "Drop a PDF statement",
            type=["pdf"],
            key=f"{profile}_workshop_uploader",
            label_visibility="collapsed",
        )
        if uploaded:
            suffix = ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                raw_text = _extract_pdf_text(tmp_path)
                institution = parsers.detect_institution(raw_text)

                # Store the file in pending queue
                st.session_state[pending_key] = [
                    {"name": uploaded.name, "raw_text": raw_text, "institution": institution}
                ]
                # Clear any old analysis/chat
                st.session_state.pop(analysis_key, None)
                st.session_state[chat_key] = []
                # Flag that we should auto-analyze
                st.session_state[analyzing_key] = True
                st.rerun()
            except Exception as exc:
                st.error(f"Could not read PDF: {exc}")
            finally:
                os.unlink(tmp_path)

        st.info("No files loaded yet. Drop a PDF above to get started.")
        return

    # --- File is loaded — show analysis UI ---
    selected = pending[0]
    raw_text: str = selected.get("raw_text", "")
    institution = selected.get("institution")
    filename = selected["name"]

    # Header bar with filename and actions
    head_left, head_right = st.columns([4, 1])
    with head_left:
        st.markdown(f"### Analyzing: `{filename}`")
    with head_right:
        if st.button("Clear & Start Over", key=f"{profile}_workshop_clear_btn", type="secondary"):
            st.session_state[pending_key] = []
            st.session_state.pop(analysis_key, None)
            st.session_state.pop(analyzing_key, None)
            st.session_state[chat_key] = []
            st.rerun()

    if institution:
        known = dict(parsers.get_institution_list())
        st.success(
            f"Rex recognizes this as a **{known.get(institution, institution)}** statement — "
            "it already has a parser. Analysis below for reference."
        )

    # --- Auto-trigger analysis if just uploaded ---
    if st.session_state.get(analyzing_key) and not st.session_state.get(analysis_key):
        st.session_state.pop(analyzing_key, None)
        _analyze_with_rex(raw_text, filename, profile)

    # --- Processing indicator ---
    if st.session_state.get(analyzing_key) and not st.session_state.get(analysis_key):
        st.markdown("---")
        with st.spinner("Rex is analyzing the statement format..."):
            st.empty()
        return

    # --- Analysis result — full width ---
    analysis = st.session_state.get(analysis_key)
    if analysis:
        st.markdown("---")
        st.markdown("### Rex's Analysis")
        st.markdown(analysis)

        # Action buttons row
        btn_cols = st.columns([1, 1, 3])
        with btn_cols[0]:
            # Copy button — uses st.code trick for copy affordance
            if st.button("Copy Analysis", key=f"{profile}_workshop_copy_btn", type="secondary"):
                st.session_state[f"{profile}_workshop_show_copy"] = True

            if st.session_state.get(f"{profile}_workshop_show_copy"):
                st.code(analysis, language="markdown")
                st.caption("Select all and copy the text above.")

        with btn_cols[1]:
            if st.button("View Raw Text", key=f"{profile}_workshop_raw_btn", type="secondary"):
                st.session_state[f"{profile}_workshop_show_raw"] = not st.session_state.get(
                    f"{profile}_workshop_show_raw", False
                )

        # Raw text popup (toggle)
        if st.session_state.get(f"{profile}_workshop_show_raw"):
            with st.expander("Raw Statement Text", expanded=True):
                st.text_area(
                    "raw_text_view",
                    value=raw_text[:8000] + ("\n... (truncated)" if len(raw_text) > 8000 else ""),
                    height=350,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"{profile}_workshop_raw_text",
                )

    elif not st.session_state.get(analyzing_key):
        # Analysis hasn't run yet (e.g. pushed from import flow)
        if st.button("Analyze with Rex", key=f"{profile}_workshop_analyze_btn", type="primary"):
            _analyze_with_rex(raw_text, filename, profile)

    # --- Chat with Rex about this statement ---
    st.markdown("---")
    st.markdown("### Resolve with Rex")
    st.caption(
        "Chat directly with Rex to troubleshoot parsing issues, "
        "request a different extraction strategy, or ask questions about this statement."
    )

    # Render chat history
    chat_history: list[dict] = st.session_state.get(chat_key, [])
    for msg in chat_history:
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["content"])
        else:
            st.chat_message("assistant", avatar=None).markdown(msg["content"])

    # Chat input
    user_input = st.chat_input(
        "Ask Rex about this statement...",
        key=f"{profile}_workshop_chat_input",
    )
    if user_input:
        _chat_about_statement(user_input, raw_text, filename, profile)
        st.rerun()


# ---------------------------------------------------------------------------
# Rex analysis call
# ---------------------------------------------------------------------------

def _analyze_with_rex(raw_text: str, filename: str, profile: str) -> None:
    """Call Rex to analyze the raw PDF text and suggest parser patterns."""
    analysis_key = f"{profile}_workshop_analysis"

    try:
        import rex  # type: ignore
        client = rex._get_client()  # reuse existing client helper
    except Exception:
        st.error("Could not connect to Rex (Anthropic API). Check your API key in .env.")
        return

    snippet = raw_text[:4000]
    prompt = f"""You are a financial data engineer helping to build a PDF bank statement parser.

Below is the first ~4000 characters of raw text extracted from a bank statement PDF named "{filename}".

```
{snippet}
```

Please analyze the text and provide:
1. **Institution name** — What bank or credit union is this?
2. **Detection pattern** — A short Python regex or string check that would uniquely identify this institution's statements.
3. **Statement date pattern** — How are the statement start/end dates expressed? Provide a regex.
4. **Transaction line pattern** — What does a transaction line look like? Provide a Python regex with named groups: `date`, `description`, `amount`. Note whether negative amounts use a leading minus, trailing minus, or a separate debit column.
5. **Section headers** — Are there section headers (e.g. "DEPOSITS", "WITHDRAWALS") that indicate credit vs debit?
6. **Stop marker** — Is there a line/section where transaction data ends (e.g. "DAILY BALANCE SUMMARY")?

If the extracted text appears garbled or unreadable (glyph codes, operator fragments, etc.), say so clearly and recommend the user try OCR extraction.

Be concise and provide actual regex patterns the developer can copy into parsers.py."""

    with st.spinner("Rex is analyzing the statement format..."):
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis = msg.content[0].text
            st.session_state[analysis_key] = analysis
        except Exception as exc:
            st.error(f"Rex analysis failed: {exc}")
    st.rerun()


# ---------------------------------------------------------------------------
# Chat with Rex about the statement
# ---------------------------------------------------------------------------

def _chat_about_statement(
    user_message: str,
    raw_text: str,
    filename: str,
    profile: str,
) -> None:
    """Send a chat message to Rex with the statement context."""
    chat_key = f"{profile}_workshop_chat_history"
    analysis_key = f"{profile}_workshop_analysis"

    try:
        import rex  # type: ignore
        client = rex._get_client()
    except Exception:
        st.error("Could not connect to Rex (Anthropic API). Check your API key in .env.")
        return

    analysis = st.session_state.get(analysis_key, "")
    snippet = raw_text[:3000]

    system_prompt = f"""You are Rex, a sharp financial data engineer and CPA assistant.
You are helping the user troubleshoot and resolve issues with parsing a bank statement PDF.

Statement file: "{filename}"
First ~3000 chars of extracted text:
```
{snippet}
```

{"Previous analysis:" + chr(10) + analysis if analysis else "No analysis yet."}

Help the user understand the parsing issues and suggest concrete fixes.
If the text is garbled, explain why (font encoding, CIDFont issues) and suggest OCR.
If they want to build a parser, provide regex patterns.
Be concise, direct, and helpful — classic Rex style."""

    chat_history: list[dict] = st.session_state.get(chat_key, [])
    chat_history.append({"role": "user", "content": user_message})

    try:
        # Build messages for API (exclude system-level context from history)
        api_messages = [{"role": m["role"], "content": m["content"]} for m in chat_history]

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=api_messages,
        )
        assistant_text = response.content[0].text
        chat_history.append({"role": "assistant", "content": assistant_text})
    except Exception as exc:
        chat_history.append({"role": "assistant", "content": f"Rex is temporarily unavailable: {exc}"})

    st.session_state[chat_key] = chat_history


# ---------------------------------------------------------------------------
# External API: push files from import flows
# ---------------------------------------------------------------------------

def push_unknown_file(profile: str, name: str, raw_text: str) -> None:
    """
    Store an unrecognized file in the workshop queue for the given profile.
    Call this from the import flow when UnknownInstitutionError is raised.
    """
    key = f"{profile}_workshop_pending"
    if key not in st.session_state:
        st.session_state[key] = []
    # Replace any existing — workshop handles one file at a time
    st.session_state[key] = [{"name": name, "raw_text": raw_text}]
