"""DIT Bid Comparison Pipeline — Streamlit web interface."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DIT Bid Comparison",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── RTL helper ────────────────────────────────────────────────────────────────

def rtl(text: str, size: str = "1rem", weight: str = "normal", color: str = "#222") -> None:
    st.markdown(
        f'<div dir="rtl" style="font-size:{size};font-weight:{weight};color:{color};'
        f'font-family:\'Segoe UI\',Arial,sans-serif;line-height:1.6">{text}</div>',
        unsafe_allow_html=True,
    )


def rtl_str(text: str, size: str = "1rem", weight: str = "normal", color: str = "#222") -> str:
    return (
        f'<div dir="rtl" style="font-size:{size};font-weight:{weight};color:{color};'
        f'font-family:\'Segoe UI\',Arial,sans-serif;line-height:1.6">{text}</div>'
    )


# ── sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/color/96/combo-chart.png", width=60)
    st.title("DIT Bid Comparison")
    st.markdown("---")
    page = st.radio(
        "ניווט",
        ["📖 כיצד זה עובד", "▶️ הרצת הצינור"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("DIT Multimedia · AI Pipeline v1.0")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — How It Works
# ══════════════════════════════════════════════════════════════════════════════

if page == "📖 כיצד זה עובד":

    st.title("כיצד עובד מערכת ההשוואה?")
    rtl(
        "מערכת DIT Bid Comparison מחליפה תהליך ידני של השוואת הצעות מחיר מקבלנים שונים. "
        "הצינור מורכב משלושה שכבות עיבוד וארבעה סוכני AI.",
        size="1.1rem",
        color="#444",
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Layer cards ───────────────────────────────────────────────────────────

    LAYER_STYLE = (
        "border-radius:12px;padding:18px 22px;margin-bottom:12px;"
        "border-left:6px solid {color};background:{bg};"
    )

    def layer_card(title: str, hebrew: str, color: str, bg: str, items: list[str]) -> None:
        bullets = "".join(f"<li>{i}</li>" for i in items)
        st.markdown(
            f'<div style="{LAYER_STYLE.format(color=color, bg=bg)}">'
            f'<div style="font-size:1.05rem;font-weight:700;color:{color}">{title}</div>'
            f'<div dir="rtl" style="margin-top:6px;color:#333;font-size:0.95rem">{hebrew}</div>'
            f'<ul dir="rtl" style="margin-top:8px;color:#555;font-size:0.9rem;padding-right:18px">{bullets}</ul>'
            f"</div>",
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("🏗️ ארכיטקטורה שלושת שכבות")

        layer_card(
            "שכבה 1 — עיבוד גולמי",
            "קריאת קבצי אקסל של הקבלנים — ללא AI, ללא עלות, מהיר ודטרמיניסטי",
            "#4472C4",
            "#EEF3FF",
            [
                "זיהוי עמודות גמיש (כל קבלן מסדר אחרת)",
                "חילוץ: מק\"ט, תיאור, כמות, מחיר יחידה, סך הכל",
                "פלט: מבנה JSON אחיד לכל קבלן",
            ],
        )

        layer_card(
            "שכבה 2 — נרמול",
            "ניקוי ובדיקה אוטומטית — scripts מקומיים + embeddings, ללא LLM",
            "#70AD47",
            "#EEF8EE",
            [
                "נרמול מחרוזות מק\"ט (POLY X52 = Poly Studio X52)",
                "חילוץ מפרט: NIT, אינץ', שעות פעולה",
                "בדיקת חשבון: כמות × מחיר = סך הכל",
                "התאמה וקטורית למק\"טים קיימים (all-MiniLM-L6-v2)",
            ],
        )

        layer_card(
            "שכבה 3 — סוכני AI",
            "שיפוט אנושי מוחלף ב-Claude — רק כאשר נדרשת הבנה",
            "#ED7D31",
            "#FFF4EE",
            [
                "סוכן A: פתרון אי-וודאות במק\"ט",
                "סוכן B: בדיקת חריגות טכניות",
                "סוכן C: דף התייחסות לקבלן (עברית)",
                "סוכן D: סיכום מנהלים",
            ],
        )

    with col2:
        st.subheader("🤖 הסוכנים")

        agents = [
            ("A", "#4472C4", "פתרון מק\"ט", "מק\"ט לא ברור? הסוכן מחליט אם מדובר באותו מוצר — ומשמר את ההחלטה לפרויקטים עתידיים"),
            ("B", "#ED7D31", "חריגות טכניות", "בודק: האם הקבלן הציע מה שנדרש במכרז? 330 NIT במקום 500? מוצר צרכני במקום מקצועי?"),
            ("C", "#70AD47", "דף התייחסות", "מייצר מכתב רשמי בעברית לקבלן עם רשימת תיקונים נדרשים לפני המשך ההערכה"),
            ("D", "#7030A0", "סיכום מנהלים", "מפיק טבלת השוואה כוללת עם סטיות, חריגות, והמלצה — לקריאת מנהל הפרויקט"),
        ]

        for letter, color, title, desc in agents:
            st.markdown(
                f'<div style="border-radius:10px;padding:14px;margin-bottom:10px;'
                f'border:2px solid {color};background:#FAFAFA">'
                f'<div style="display:flex;align-items:center;gap:10px">'
                f'<div style="width:32px;height:32px;border-radius:50%;background:{color};'
                f'color:white;font-weight:700;font-size:1rem;display:flex;align-items:center;justify-content:center">'
                f"{letter}</div>"
                f'<div style="font-weight:700;color:{color}">{title}</div></div>'
                f'<div dir="rtl" style="margin-top:8px;color:#555;font-size:0.88rem">{desc}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        # Vector DB box
        st.markdown(
            '<div style="border-radius:10px;padding:14px;margin-top:4px;'
            'background:linear-gradient(135deg,#F3EBF9,#E8D5F5);border:1px solid #7030A0">'
            '<div style="font-weight:700;color:#7030A0">🗄️ Vector DB (RAG)</div>'
            '<div dir="rtl" style="margin-top:6px;color:#555;font-size:0.88rem">'
            "זיכרון מוסדי — שומר החלטות טכניות מפרויקטים קודמים. "
            "לעולם לא שומר מחירים (סודיות מסחרית)."
            "</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Pipeline flow diagram ──────────────────────────────────────────────────

    st.subheader("🔄 זרימת הצינור")

    steps = [
        ("📂", "קריאת אקסל", "Layer 1", "#4472C4"),
        ("🔢", "בדיקת חשבון", "Layer 2", "#4472C4"),
        ("🔤", "נרמול מק\"ט", "Layer 2", "#4472C4"),
        ("🔍", "התאמה וקטורית", "Layer 2", "#70AD47"),
        ("🤖", "סוכן A", "Agent A", "#ED7D31"),
        ("📋", "סוכן B", "Agent B", "#ED7D31"),
        ("📊", "טבלת השוואה", "Build", "#70AD47"),
        ("✉️", "סוכן C", "Agent C", "#ED7D31"),
        ("📝", "סוכן D", "Agent D", "#7030A0"),
    ]

    cols = st.columns(len(steps))
    for col, (icon, label, layer, color) in zip(cols, steps):
        with col:
            st.markdown(
                f'<div style="text-align:center;padding:10px 4px;border-radius:8px;'
                f'border:2px solid {color};background:#FAFAFA">'
                f'<div style="font-size:1.4rem">{icon}</div>'
                f'<div style="font-size:0.78rem;font-weight:700;color:{color};margin-top:4px">{label}</div>'
                f'<div style="font-size:0.68rem;color:#888;margin-top:2px">{layer}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── I/O table ─────────────────────────────────────────────────────────────

    st.subheader("📥 קלט ופלט")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**קלט — מה נכנס:**")
        st.table({
            "קובץ": [
                "הצעה 1.xlsx",
                "הצעה 2.xlsx",
                "... (כל קבלן)",
                "BOQ (אופציונלי)",
            ],
            "תוכן": [
                "הצעת מחיר קבלן א׳",
                "הצעת מחיר קבלן ב׳",
                "הצעות נוספות",
                "רשימת כמויות מכרז",
            ],
        })

    with col_b:
        st.markdown("**פלט — מה יוצא:**")
        st.table({
            "קובץ": [
                "comparison_<פרויקט>.xlsx",
                "ref_sheet_<קבלן>.md",
                "executive_summary.md",
            ],
            "תוכן": [
                "טבלת השוואה מלאה עם הדגשות",
                "מכתב לכל קבלן עם תיקונים נדרשים",
                "סיכום מנהלים עם המלצה",
            ],
        })

    # ── Key decisions ─────────────────────────────────────────────────────────

    with st.expander("💡 עקרונות מרכזיים בתכנון"):
        rtl(
            "<b>Script לכל מה שניתן להגדיר כחוק · Embeddings להתאמת דמיון · "
            "AI רק כשנדרשת שיפוטיות · RAG לזיכרון מוסדי</b>",
            size="1rem",
        )
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns(3)
        with cols[0]:
            st.info("**🔒 פרטיות**\nמחירי הקבלנים לעולם לא עוזבים את המחשב — embeddings מקומיים, ChromaDB מקומי")
        with cols[1]:
            st.info("**⚡ מהירות**\nשכבות 1 ו-2 רצות ללא קריאות API — מהירות, חינמיות, דטרמיניסטיות")
        with cols[2]:
            st.info("**🔄 המשכיות**\nJSON ביניים נשמר אחרי כל שכבה — ניתן להמשיך מכל נקודה אחרי תקלה")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Run Pipeline
# ══════════════════════════════════════════════════════════════════════════════

else:

    st.title("▶️ הרצת צינור ההשוואה")
    rtl("העלה קבצי הצעות מחיר, הכנס שם פרויקט, ולחץ הרץ.", size="1.05rem", color="#444")
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Inputs ────────────────────────────────────────────────────────────────

    col_left, col_right = st.columns([3, 2])

    with col_left:
        contractor_files = st.file_uploader(
            "קבצי הצעות קבלנים (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            help="העלה קובץ אחד לפחות. כל קובץ = קבלן אחד.",
        )
        boq_file = st.file_uploader(
            "קובץ BOQ — רשימת כמויות (אופציונלי)",
            type=["xlsx"],
            help="אם לא מועלה, הצינור ירוץ ללא בדיקת BOQ.",
        )

    with col_right:
        project_id = st.text_input(
            "מזהה פרויקט (ASCII)",
            value="proj_2026_001",
            help="אותיות, מספרים ומקפים בלבד. ישמש לשמות תיקיות ופלטים.",
        )
        project_name = st.text_input(
            "שם פרויקט (לדוחות)",
            value="",
            placeholder="פרויקט מולטימדיה 2026",
            help="שם לקריאה אנושית — עברית מותרת.",
        )

        if contractor_files:
            st.success(f"✅ {len(contractor_files)} קבצים הועלו")
            for f in contractor_files:
                st.caption(f"• {f.name}")

    st.markdown("---")

    # ── Run button ────────────────────────────────────────────────────────────

    run_disabled = not contractor_files or not project_id.strip()
    run_btn = st.button(
        "▶️ הרץ צינור השוואה",
        disabled=run_disabled,
        type="primary",
        use_container_width=True,
    )

    if run_disabled and not contractor_files:
        st.info("העלה לפחות קובץ אחד של הצעת קבלן כדי להתחיל.")

    # ── Session state init ────────────────────────────────────────────────────

    if "pipeline_done" not in st.session_state:
        st.session_state.pipeline_done = False
    if "pipeline_outputs" not in st.session_state:
        st.session_state.pipeline_outputs = {}
    if "pipeline_error" not in st.session_state:
        st.session_state.pipeline_error = None

    # ── Pipeline execution ────────────────────────────────────────────────────

    if run_btn:
        st.session_state.pipeline_done = False
        st.session_state.pipeline_outputs = {}
        st.session_state.pipeline_error = None

        pid = project_id.strip()
        pname = project_name.strip() or None

        # ── Save uploads to temp dir ──────────────────────────────────────────
        tmp_dir = tempfile.mkdtemp(prefix="dit_")
        input_dir = Path(tmp_dir) / "contractors"
        input_dir.mkdir()

        boq_path = Path(tmp_dir) / "boq.xlsx"

        for uf in contractor_files:
            dest = input_dir / uf.name
            dest.write_bytes(uf.read())

        if boq_file:
            boq_path.write_bytes(boq_file.read())

        # ── Timeline display ──────────────────────────────────────────────────
        st.markdown("### ⏱️ התקדמות")
        timeline = st.container()

        try:
            # Lazy import so Streamlit loads fast even if deps are missing
            from src.layer1_parser.excel_reader import parse_excel
            from src.layer2_normalization.embeddings import match_file
            from src.layer2_normalization.math_validator import validate_file
            from src.layer2_normalization.spec_extractor import extract_specs
            from src.layer2_normalization.text_normalizer import normalize_mkt
            from src.layer3_agents.agent_a_ambiguity import resolve_ambiguities
            from src.layer3_agents.agent_b_deviation import review_file
            from src.layer3_agents.agent_c_ref_sheet import generate_ref_sheet
            from src.layer3_agents.agent_d_summary import generate_summary
            from src.layer3_agents.build_comparison_table import build
            from vector_db.store import VectorStore

            contractor_paths = sorted(input_dir.glob("*.xlsx"))

            # ── Init VectorStore ──────────────────────────────────────────────
            with timeline:
                with st.status("🗄️ אתחול מסד נתונים וקטורי...", expanded=False) as s:
                    store = VectorStore()
                    s.update(label="✅ מסד נתונים מוכן", state="complete")

            # ── Per-contractor processing ─────────────────────────────────────
            all_contractor_data: list[dict] = []

            for xlsx_path in contractor_paths:
                cid = xlsx_path.stem.replace(" ", "_")
                cid = "".join(
                    c if (c.isascii() and (c.isalnum() or c in "_-")) else "_"
                    for c in cid
                ).strip("_") or "contractor"
                display_name = xlsx_path.name

                with timeline:

                    with st.status(
                        f"📂 Layer 1 — קריאת אקסל: {display_name}", expanded=False
                    ) as s:
                        t0 = time.perf_counter()
                        parsed = parse_excel(xlsx_path, cid, pid)
                        elapsed = time.perf_counter() - t0
                        s.update(
                            label=f"✅ Layer 1 — {display_name} ({len(parsed.sheets)} גיליונות, {elapsed:.1f}s)",
                            state="complete",
                        )

                    with st.status(
                        f"🔢 Layer 2 — נרמול ובדיקה: {display_name}", expanded=False
                    ) as s:
                        t0 = time.perf_counter()
                        import json as _json
                        data = validate_file(parsed)
                        for sheet in data["sheets"]:
                            for row in sheet["rows"]:
                                raw = row.get("manufacturer_model") or row.get("mkt_raw") or ""
                                row["mkt_normalized"] = normalize_mkt(raw)
                                row["specs_extracted"] = extract_specs(row["description"])
                        match_file(data, store)
                        elapsed = time.perf_counter() - t0
                        n_math = sum(
                            1 for sh in data["sheets"] for r in sh["rows"]
                            if r.get("flags", {}).get("math_error")
                        )
                        n_uncertain = sum(
                            1 for sh in data["sheets"] for r in sh["rows"]
                            if r.get("mkt_match", {}).get("requires_agent")
                        )
                        s.update(
                            label=(
                                f"✅ Layer 2 — {display_name} "
                                f"(שגיאות חשבון: {n_math}, מק\"טים לא ברורים: {n_uncertain}, {elapsed:.1f}s)"
                            ),
                            state="complete",
                        )

                    with st.status(
                        f"🤖 סוכן A — פתרון מק\"ט: {display_name}", expanded=False
                    ) as s:
                        t0 = time.perf_counter()
                        data = resolve_ambiguities(data, store)
                        elapsed = time.perf_counter() - t0
                        s.update(
                            label=f"✅ סוכן A — {display_name} ({elapsed:.1f}s)",
                            state="complete",
                        )

                    with st.status(
                        f"📋 סוכן B — בדיקת חריגות: {display_name}", expanded=False
                    ) as s:
                        t0 = time.perf_counter()
                        data = review_file(data, store)
                        elapsed = time.perf_counter() - t0
                        n_dev = sum(
                            1 for sh in data["sheets"] for r in sh["rows"]
                            if r.get("technical_review", {}).get("deviation_detected")
                        )
                        s.update(
                            label=f"✅ סוכן B — {display_name} (חריגות: {n_dev}, {elapsed:.1f}s)",
                            state="complete",
                        )

                all_contractor_data.append(data)

            # ── Build comparison table ────────────────────────────────────────
            with timeline:
                with st.status("📊 בניית טבלת השוואה...", expanded=False) as s:
                    t0 = time.perf_counter()
                    xlsx_out = build(all_contractor_data, pid)
                    elapsed = time.perf_counter() - t0
                    s.update(
                        label=f"✅ טבלת השוואה נוצרה ({elapsed:.1f}s)",
                        state="complete",
                    )

            # ── Agent C — ref sheets ──────────────────────────────────────────
            ref_paths: list[str] = []
            for data in all_contractor_data:
                cid = data["meta"]["contractor_id"]
                with timeline:
                    with st.status(
                        f"✉️ סוכן C — דף התייחסות: {cid}", expanded=False
                    ) as s:
                        t0 = time.perf_counter()
                        ref_path = generate_ref_sheet(data)
                        elapsed = time.perf_counter() - t0
                        if ref_path:
                            ref_paths.append(ref_path)
                            s.update(
                                label=f"✅ סוכן C — דף התייחסות: {cid} ({elapsed:.1f}s)",
                                state="complete",
                            )
                        else:
                            s.update(
                                label=f"⏭️ סוכן C — {cid}: אין פריטים לתיקון",
                                state="complete",
                            )

            # ── Agent D — executive summary ───────────────────────────────────
            with timeline:
                with st.status("📝 סוכן D — סיכום מנהלים...", expanded=False) as s:
                    t0 = time.perf_counter()
                    summary_path = generate_summary(all_contractor_data, pid, pname)
                    elapsed = time.perf_counter() - t0
                    s.update(
                        label=f"✅ סוכן D — סיכום מנהלים ({elapsed:.1f}s)",
                        state="complete",
                    )

            # ── Store results in session_state ────────────────────────────────
            st.session_state.pipeline_outputs = {
                "xlsx_out": xlsx_out,
                "ref_paths": ref_paths,
                "summary_path": summary_path,
            }
            st.session_state.pipeline_done = True
            st.session_state.pipeline_error = None

        except ImportError as exc:
            st.session_state.pipeline_error = (
                f"שגיאת ייבוא מודולים: {exc}\n\n"
                "ודא שכל התלויות מותקנות: `pip install -r requirements.txt`"
            )
        except Exception as exc:
            st.session_state.pipeline_error = str(exc)

    # ── Error display ─────────────────────────────────────────────────────────

    if st.session_state.pipeline_error:
        st.markdown("---")
        st.markdown(
            '<div dir="rtl" style="background:#FFF0F0;border:2px solid #CC0000;'
            'border-radius:10px;padding:18px;font-family:Segoe UI,Arial,sans-serif">'
            '<div style="font-size:1.1rem;font-weight:700;color:#CC0000">❌ שגיאה בהרצת הצינור</div>'
            f'<pre style="margin-top:10px;color:#333;font-size:0.85rem;white-space:pre-wrap">'
            f'{st.session_state.pipeline_error}</pre>'
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Download section ──────────────────────────────────────────────────────

    if st.session_state.pipeline_done and st.session_state.pipeline_outputs:
        outputs = st.session_state.pipeline_outputs
        st.markdown("---")

        st.markdown(
            '<div dir="rtl" style="background:#EEFAF0;border:2px solid #28A745;'
            'border-radius:10px;padding:16px;font-family:Segoe UI,Arial,sans-serif;'
            'font-size:1.05rem;font-weight:700;color:#155724">'
            "✅ הצינור הסתיים בהצלחה! הורד את הקבצים:"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        dl_cols = st.columns(3)

        # Comparison Excel
        with dl_cols[0]:
            xlsx_path = Path(outputs["xlsx_out"])
            if xlsx_path.exists():
                st.download_button(
                    label="📊 טבלת השוואה (Excel)",
                    data=xlsx_path.read_bytes(),
                    file_name=xlsx_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        # Executive summary
        with dl_cols[1]:
            summary_path = Path(outputs["summary_path"])
            if summary_path.exists():
                st.download_button(
                    label="📝 סיכום מנהלים (Markdown)",
                    data=summary_path.read_bytes(),
                    file_name="executive_summary.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

        # Ref sheets
        with dl_cols[2]:
            ref_paths = outputs.get("ref_paths", [])
            if ref_paths:
                if len(ref_paths) == 1:
                    rp = Path(ref_paths[0])
                    st.download_button(
                        label="✉️ דף התייחסות לקבלן",
                        data=rp.read_bytes(),
                        file_name=rp.name,
                        mime="text/markdown",
                        use_container_width=True,
                    )
                else:
                    # Zip multiple ref sheets
                    import io
                    import zipfile

                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for rp_str in ref_paths:
                            rp = Path(rp_str)
                            if rp.exists():
                                zf.write(rp, rp.name)
                    buf.seek(0)
                    st.download_button(
                        label=f"✉️ דפי התייחסות ({len(ref_paths)} קבלנים)",
                        data=buf.getvalue(),
                        file_name="ref_sheets.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

        # ── Stats panel ───────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📈 פרטי ריצה"):
            xlsx_path = Path(outputs["xlsx_out"])
            if xlsx_path.exists():
                size_kb = xlsx_path.stat().st_size / 1024
                st.metric("גודל טבלת השוואה", f"{size_kb:.1f} KB")
            st.metric("דפי התייחסות שנוצרו", len(outputs.get("ref_paths", [])))
            summary_path = Path(outputs["summary_path"])
            if summary_path.exists():
                lines = summary_path.read_text(encoding="utf-8").count("\n")
                st.metric("שורות בסיכום מנהלים", lines)
