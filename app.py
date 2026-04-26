import os, sys, tempfile, time
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

_api_key = os.getenv("GOOGLE_API_KEY")
if not _api_key:
    st.set_page_config(page_title="Catalyst — Setup Required", page_icon="⚡")
    st.error("### ❌ GOOGLE_API_KEY not found")
    st.markdown("""
**To fix this:**

1. Get a free Gemini API key at **https://aistudio.google.com/apikey**
2. Create a file called `.env` in the same folder as `app.py`
3. Add this line to `.env`:
```
GOOGLE_API_KEY=your_key_here
```
4. Restart the app: `streamlit run app.py`
    """)
    st.stop()

from pipeline import Pipeline
from utils.pdf_extractor import extract_text_safe


st.set_page_config(
    page_title="Catalyst — AI Skill Assessment",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Global ── */
html, body, [class*="css"] { font-family: 'Syne', sans-serif !important; }
.stApp { background: #0a0a0f; color: #e8e8f0; }

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 4rem !important; max-width: 1100px !important; }

/* ── Clickable Nav Bar ── */
.nav-bar {
    display: flex; gap: 0;
    background: #13131a; border: 1px solid #2a2a3d;
    border-radius: 12px; overflow: hidden;
    margin-bottom: 2rem;
}
.nav-step {
    flex: 1; padding: 14px 8px; text-align: center;
    font-size: 11px; font-family: 'JetBrains Mono', monospace;
    color: #6b6b8a; border-right: 1px solid #2a2a3d;
    cursor: default; transition: all .2s; user-select: none;
}
.nav-step:last-child { border-right: none; }
.nav-step .num { display: block; font-size: 18px; margin-bottom: 3px; }
.nav-step.active { background: rgba(108,99,255,.12); color: #6c63ff; }
.nav-step.done   { background: rgba(67,233,123,.08); color: #43e97b; cursor: pointer; }
.nav-step.done:hover { background: rgba(67,233,123,.16); }

/* ── Question timer badge ── */
.q-timer {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(108,99,255,.1); border: 1px solid rgba(108,99,255,.3);
    border-radius: 20px; padding: 4px 14px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #6c63ff;
    margin-bottom: 12px;
}
.q-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(67,233,123,.08); border: 1px solid rgba(67,233,123,.25);
    border-radius: 20px; padding: 4px 14px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #43e97b;
    margin-bottom: 12px; margin-left: 8px;
}
.answer-time {
    font-size: 11px; color: #6b6b8a;
    font-family: 'JetBrains Mono', monospace;
    text-align: right; margin-top: 4px;
}

/* ── Cards ── */
.cat-card {
    background: #13131a; border: 1px solid #2a2a3d;
    border-radius: 12px; padding: 24px; margin-bottom: 20px;
}
.cat-card-title {
    font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
    text-transform: uppercase; color: #6b6b8a;
    margin-bottom: 16px; display: flex; align-items: center; gap: 8px;
}
.cat-card-title .dot { width:6px; height:6px; border-radius:50%; background:#6c63ff; display:inline-block; }

/* ── Chips ── */
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip {
    padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-family: 'JetBrains Mono', monospace;
    background: #1c1c28; border: 1px solid #2a2a3d; color: #e8e8f0;
    display: inline-block;
}
.chip.req  { border-color:#6c63ff; color:#6c63ff; background:rgba(108,99,255,.08); }
.chip.pref { border-color:#ff6584; color:#ff6584; background:rgba(255,101,132,.08); }
.chip.good { border-color:#43e97b; color:#43e97b; background:rgba(67,233,123,.08); }

/* ── Chat messages ── */
.chat-wrap { max-height: 480px; overflow-y: auto; padding: 4px 0; }
.msg-ai {
    display: flex; gap: 10px; margin-bottom: 14px;
    animation: fadeUp .3s ease;
}
.msg-user {
    display: flex; gap: 10px; flex-direction: row-reverse; margin-bottom: 14px;
    animation: fadeUp .3s ease;
}
@keyframes fadeUp {
    from { opacity:0; transform:translateY(8px); }
    to   { opacity:1; transform:translateY(0); }
}
.avatar {
    width:32px; height:32px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:15px; flex-shrink:0;
}
.avatar-ai  { background: linear-gradient(135deg,#6c63ff,#ff6584); }
.avatar-usr { background:#1c1c28; border:1px solid #2a2a3d; }
.bubble-ai {
    max-width:78%; padding:12px 16px; border-radius:4px 12px 12px 12px;
    background:#1c1c28; border:1px solid #2a2a3d;
    font-size:14px; line-height:1.65; color:#e8e8f0;
}
.bubble-usr {
    max-width:78%; padding:12px 16px; border-radius:12px 4px 12px 12px;
    background:linear-gradient(135deg,#6c63ff,#8b85ff);
    font-size:14px; line-height:1.65; color:white;
}

/* ── Readiness bar ── */
.readiness-score {
    font-size: 48px; font-weight: 800;
    background: linear-gradient(135deg,#6c63ff,#43e97b);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1;
}
.readiness-label { font-family:'JetBrains Mono',monospace; font-size:13px; color:#6b6b8a; margin-top:4px; }
.progress-track {
    height:8px; background:#1c1c28; border-radius:4px; overflow:hidden; margin-top:12px;
}
.progress-fill {
    height:100%; border-radius:4px;
    background:linear-gradient(90deg,#6c63ff,#43e97b);
}

/* ── Skill plan cards ── */
.sp-card {
    background:#1c1c28; border:1px solid #2a2a3d;
    border-radius:10px; padding:18px; margin-bottom:14px;
}
.sp-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.sp-skill { font-size:15px; font-weight:700; }
.badge {
    font-size:10px; font-family:'JetBrains Mono',monospace;
    padding:3px 10px; border-radius:20px; font-weight:600; text-transform:uppercase;
}
.badge-Critical { background:rgba(255,101,132,.15); color:#ff6584; border:1px solid #ff6584; }
.badge-High     { background:rgba(255,209,102,.1); color:#ffd166; border:1px solid #ffd166; }
.badge-Medium   { background:rgba(108,99,255,.1); color:#6c63ff; border:1px solid #6c63ff; }
.badge-Low      { background:rgba(67,233,123,.1); color:#43e97b; border:1px solid #43e97b; }
.sp-meta {
    font-family:'JetBrains Mono',monospace; font-size:12px; color:#6b6b8a;
    display:flex; gap:16px; margin-bottom:10px;
}
.sp-why { font-size:13px; color:#6b6b8a; margin-bottom:12px; line-height:1.5; }
.resource {
    display:flex; align-items:flex-start; gap:10px;
    padding:8px 0; border-top:1px solid #2a2a3d;
}
.resource-info a { color:#6c63ff; text-decoration:none; font-size:13px; font-weight:600; }
.resource-meta { font-size:11px; color:#6b6b8a; font-family:'JetBrains Mono',monospace; margin-top:2px; }
.project-box {
    margin-top:12px; padding:10px 14px;
    background:rgba(108,99,255,.08); border-left:3px solid #6c63ff;
    border-radius:0 6px 6px 0; font-size:13px; color:#e8e8f0;
}
.project-label { font-size:10px; color:#6b6b8a; text-transform:uppercase; letter-spacing:1px; font-family:'JetBrains Mono',monospace; margin-bottom:4px; }

/* ── Week rows ── */
.week-row {
    display:flex; gap:12px; align-items:flex-start;
    padding:12px 0; border-bottom:1px solid #2a2a3d;
}
.week-row:last-child { border-bottom:none; }
.week-num { width:64px; flex-shrink:0; font-family:'JetBrains Mono',monospace; font-size:11px; color:#6c63ff; font-weight:600; padding-top:2px; }
.week-skill { font-size:13px; font-weight:600; margin-bottom:3px; }
.week-deliv { font-size:12px; color:#6b6b8a; }

/* ── Info grid ── */
.info-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
.info-item label { font-size:10px; color:#6b6b8a; text-transform:uppercase; letter-spacing:1px; font-family:'JetBrains Mono',monospace; }
.info-item .val  { font-size:16px; font-weight:700; margin-top:4px; }

/* ── Section heading ── */
.sec-head {
    font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#6b6b8a; margin:18px 0 10px;
}

/* ── Streamlit overrides ── */
div[data-testid="stTextInput"] input {
    background:#1c1c28 !important; color:#e8e8f0 !important;
    border:1px solid #2a2a3d !important; border-radius:8px !important;
    font-family:'Syne',sans-serif !important;
}
div[data-testid="stTextInput"] input:focus { border-color:#6c63ff !important; }

div[data-testid="stTextArea"] textarea {
    background:#1c1c28 !important; color:#e8e8f0 !important;
    border:1px solid #2a2a3d !important; border-radius:8px !important;
    font-family:'JetBrains Mono',monospace !important; font-size:13px !important;
}

.stButton > button {
    background:linear-gradient(135deg,#6c63ff,#8b85ff) !important;
    color:white !important; border:none !important;
    border-radius:8px !important; padding:10px 24px !important;
    font-family:'Syne',sans-serif !important; font-weight:700 !important;
    font-size:14px !important; transition:all .2s !important;
}
.stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 8px 24px rgba(108,99,255,.35) !important; }

div[data-testid="stFileUploader"] {
    background:#1c1c28 !important; border:2px dashed #2a2a3d !important;
    border-radius:8px !important;
}

div[data-testid="stTabs"] [data-baseweb="tab"] {
    background:transparent !important; color:#6b6b8a !important;
    border-radius:6px !important; font-family:'Syne',sans-serif !important; font-weight:600 !important;
}
div[data-testid="stTabs"] [aria-selected="true"] {
    background:#1c1c28 !important; color:#e8e8f0 !important;
}
div[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }

.stAlert { border-radius:8px !important; }
div[data-testid="stMetric"] { background:#1c1c28; border:1px solid #2a2a3d; border-radius:8px; padding:14px; }
div[data-testid="stMetric"] label { color:#6b6b8a !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color:#e8e8f0 !important; }
</style>
""", unsafe_allow_html=True)


def init_state():
    defaults = {
        "pipeline":        None,
        "stage":           "upload",  
        "chat_history":    [],         
        "assessment_done": False,
        "extracted":       None,
        "final_report":    None,
        "error":           None,
        "q_start_time":    None,      
        "q_number":        0,         
        "total_questions": 5,         
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

STAGE_ORDER = ["upload", "extracted", "assessing", "gap_view", "generating", "report"]
NAV_LABELS  = ["① Extract", "② Assess", "③ Gap Analysis", "④ Learn Plan", "⑤ Report"]
NAV_STAGES  = ["upload",   "extracted", "assessing",    "gap_view",   "report"]

def nav_bar():
    stage_to_nav = {
        "upload":     0,
        "extracted":  0,
        "assessing":  1,
        "gap_view":   2,
        "generating": 3,
        "report":     4,
    }
    current_nav = stage_to_nav.get(st.session_state.stage, 0)

    html = '<div class="nav-bar">'
    for i, label in enumerate(NAV_LABELS):
        if i < current_nav:
            cls = "done"
        elif i == current_nav:
            cls = "active"
        else:
            cls = ""
        num, name = label.split(" ", 1)
        html += f'<div class="nav-step {cls}"><span class="num">{num}</span>{name}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    if current_nav > 0:
        cols = st.columns(len(NAV_LABELS))
        for i in range(current_nav):
            with cols[i]:
                label_short = NAV_LABELS[i].split(" ", 1)[1]
                if st.button(f"↩ {label_short}", key=f"nav_jump_{i}",
                             help=f"Go back to {label_short}"):
                    st.session_state.stage = NAV_STAGES[i]
                    st.rerun()


def header():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;
                padding-bottom:20px;border-bottom:1px solid #2a2a3d;">
      <div style="width:44px;height:44px;border-radius:10px;
                  background:linear-gradient(135deg,#6c63ff,#ff6584);
                  display:flex;align-items:center;justify-content:center;
                  font-size:22px;font-weight:800;color:white;flex-shrink:0;">C</div>
      <div>
        <div style="font-size:20px;font-weight:800;letter-spacing:-.5px;">Catalyst — AI Skill Assessment</div>
        <div style="font-size:12px;color:#6b6b8a;font-family:'JetBrains Mono',monospace;margin-top:2px;">
          Resume + JD → Assessment → Gap Analysis → Personalised Learning Plan
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def card(title: str, content_fn):
    st.markdown(f"""<div class="cat-card">
      <div class="cat-card-title"><span class="dot"></span>{title}</div>""",
        unsafe_allow_html=True)
    content_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def chips(items: list[str], cls: str = "") -> str:
    return '<div class="chip-row">' + "".join(
        f'<span class="chip {cls}">{i}</span>' for i in (items or [])[:24]
    ) + "</div>"


def icon_for_type(t: str) -> str:
    return {"Course": "🎓", "Video": "▶️", "Book": "📖",
            "Documentation": "📑", "Practice": "💻"}.get(t, "🔗")


def stage_upload():
    nav_bar()

    st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>Resume + Job Description</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("**📄 Resume**")
        resume_file = st.file_uploader(
            "Upload PDF or TXT", type=["pdf", "txt"], label_visibility="collapsed"
        )
        if resume_file:
            st.success(f"✓ {resume_file.name}")

    with col2:
        st.markdown("**📋 Job Description**")
        jd_text = st.text_area(
            "Paste full JD here",
            placeholder="Paste the complete job description here…\n\nInclude: role title, responsibilities, required skills, preferred skills, experience level…",
            height=200,
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("⚡ Extract Skills & Start", use_container_width=False):
        if not resume_file:
            st.error("Please upload your resume.")
            return
        if not jd_text.strip():
            st.error("Please paste the job description.")
            return

        suffix = Path(resume_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(resume_file.read())
            tmp_path = tmp.name

        with st.spinner("🔍 Agent 1: Extracting skills from Resume & JD…"):
            try:
                pipe = Pipeline()
                extracted = pipe.run_extraction(tmp_path, jd_text.strip())
                os.unlink(tmp_path)

                st.session_state.pipeline  = pipe
                st.session_state.extracted = extracted
                st.session_state.stage     = "extracted"
                st.rerun()
            except Exception as e:
                os.unlink(tmp_path)
                st.error(f"Extraction failed: {e}")


def stage_extracted():
    nav_bar()
    ex = st.session_state.extracted
    rs = ex.resume_skills
    jd = ex.jd_requirements

    st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>✅ Skill Extraction Complete</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Candidate", rs.candidate_name or "—")
    col2.metric("Target Role", jd.job_title or "—")
    col3.metric("Domain", jd.domain or "—")
    col4.metric("Experience", f"{rs.total_years_experience} yrs")

    st.markdown('<div class="sec-head">Required Skills from JD</div>', unsafe_allow_html=True)
    st.markdown(chips(jd.required_skills, "req"), unsafe_allow_html=True)

    st.markdown('<div class="sec-head">Preferred Skills</div>', unsafe_allow_html=True)
    st.markdown(chips(jd.preferred_skills, "pref"), unsafe_allow_html=True)

    st.markdown('<div class="sec-head">Candidate\'s Skills (from Resume)</div>', unsafe_allow_html=True)
    st.markdown(chips(rs.technical_skills, "good"), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("💬 Start Conversational Assessment →"):
        with st.spinner("Starting assessment session…"):
            first_q = st.session_state.pipeline.start_assessment()
            st.session_state.chat_history = [{
                "role":    "ai",
                "content": first_q,
            }]
            st.session_state.q_start_time = time.time()
            st.session_state.q_number     = 1
            st.session_state.stage        = "assessing"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, _ = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            st.session_state.stage = "upload"
            st.rerun()


def render_chat_history():
    html = '<div class="chat-wrap">'
    q_num = 0
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        elapsed = msg.get("elapsed", None)

        if msg["role"] == "ai":
            q_num += 1
            q_label = f'<span class="q-timer">❓ Question {q_num} of {st.session_state.total_questions}</span>'
            html += f'''<div class="msg-ai">
              <div class="avatar avatar-ai">🤖</div>
              <div style="flex:1">
                {q_label}
                <div class="bubble-ai">{content}</div>
              </div>
            </div>'''
        else:
            elapsed_html = (
                f'<div class="answer-time">⚡ You answered in {elapsed:.1f}s</div>'
                if elapsed is not None else ""
            )
            html += f'''<div class="msg-user">
              <div class="avatar avatar-usr">👤</div>
              <div style="flex:1;display:flex;flex-direction:column;align-items:flex-end;">
                <div class="bubble-usr">{content}</div>
                {elapsed_html}
              </div>
            </div>'''
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def stage_assessing():
    nav_bar()

    ex  = st.session_state.extracted
    jd  = ex.jd_requirements
    tot = st.session_state.total_questions

    answered = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
    asked    = sum(1 for m in st.session_state.chat_history if m["role"] == "ai")

    st.markdown(f"""
    <div class="cat-card">
      <div class="cat-card-title"><span class="dot"></span>💬 Skill Assessment — {jd.job_title}</div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
        <span class="q-timer">📋 Question {min(asked, tot)} of {tot}</span>
        <span class="q-badge">✅ {answered} answered</span>
        <span style="font-size:11px;color:#6b6b8a;font-family:'JetBrains Mono',monospace;">
          Skills: {", ".join(ex.all_required_skills[:5])}
        </span>
      </div>
    """, unsafe_allow_html=True)

    render_chat_history()
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.assessment_done:
        st.success("✅ All questions answered!")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ Back to Extract", use_container_width=True):
                st.session_state.stage = "extracted"
                st.rerun()
        with col2:
            if st.button("🔎 View Gap Analysis →", type="primary", use_container_width=True):
                with st.spinner("Running gap analysis…"):
                    st.session_state.pipeline.run_gap_analysis()
                st.session_state.stage = "gap_view"
                st.rerun()
        return

    form_key = f"chat_form_{len(st.session_state.chat_history)}"
    with st.form(key=form_key, clear_on_submit=True):
        user_input = st.text_input(
            "Your answer",
            placeholder="Type your answer here…",
            label_visibility="collapsed",
        )
        col_back, col_send = st.columns([1, 4])
        with col_back:
            back_clicked = st.form_submit_button("⬅️ Back", use_container_width=True)
        with col_send:
            send_clicked = st.form_submit_button(
                "➤  Send Answer",
                type="primary",
                use_container_width=True,
            )

    if back_clicked:
        st.session_state.stage = "extracted"
        st.rerun()

    if send_clicked and user_input.strip():
        elapsed = None
        if st.session_state.q_start_time is not None:
            elapsed = time.time() - st.session_state.q_start_time

        st.session_state.chat_history.append({
            "role":    "user",
            "content": user_input.strip(),
            "elapsed": elapsed,
        })

        with st.spinner("Thinking…"):
            t0 = time.time()
            reply, is_done = st.session_state.pipeline.chat(user_input.strip())

        st.session_state.q_start_time = time.time()
        st.session_state.q_number    += 1
        st.session_state.chat_history.append({
            "role":    "ai",
            "content": reply,
        })

        if is_done:
            st.session_state.assessment_done = True
            with st.spinner("Scoring your responses…"):
                st.session_state.pipeline.finalise_assessment()

        st.rerun()



def stage_gap_view():
    nav_bar()
    r = st.session_state.pipeline.gap_analysis

    score = r.overall_readiness_score
    label = r.readiness_label
    bar_color = "#43e97b" if score >= 70 else "#ffd166" if score >= 45 else "#ff6584"

    st.markdown(f"""
    <div class="cat-card">
      <div class="cat-card-title"><span class="dot"></span>🔎 Gap Analysis — {r.candidate_name} → {r.target_role}</div>
      <div style="display:flex;align-items:flex-start;gap:32px;flex-wrap:wrap;">
        <div>
          <div class="readiness-score">{int(score)}<span style="font-size:22px;opacity:.5">/100</span></div>
          <div class="readiness-label">{label}</div>
          <div class="progress-track" style="width:220px;margin-top:10px;">
            <div class="progress-fill" style="width:{min(score,100)}%;background:linear-gradient(90deg,#6c63ff,{bar_color});"></div>
          </div>
        </div>
        <div style="flex:1;min-width:200px;">
          <div class="sec-head">Summary</div>
          <div style="font-size:13px;line-height:1.7;color:#6b6b8a;">{r.gaps_summary}</div>
          <div style="margin-top:10px;font-size:13px;line-height:1.7;color:#6b6b8a;">{r.strengths_summary}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if r.skill_gaps:
        st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>📉 Skill Gaps</div>', unsafe_allow_html=True)
        for g in r.skill_gaps:
            cur = g.current_score
            req = g.required_score
            pct_cur = (cur / 5) * 100
            pct_req = (req / 5) * 100
            pri     = g.priority
            badge_colors = {
                "Critical": ("#ff6584", "rgba(255,101,132,.15)"),
                "High":     ("#ffd166", "rgba(255,209,102,.1)"),
                "Medium":   ("#6c63ff", "rgba(108,99,255,.1)"),
                "Low":      ("#43e97b", "rgba(67,233,123,.1)"),
            }
            bc, bg = badge_colors.get(pri, ("#6c63ff", "rgba(108,99,255,.1)"))
            gap_bar_w = max(0, pct_req - pct_cur)

            st.markdown(f"""
            <div style="margin-bottom:16px;padding:14px;background:#1c1c28;border:1px solid #2a2a3d;border-radius:8px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="font-weight:700;font-size:14px;">{g.skill}</div>
                <span style="font-size:10px;font-family:'JetBrains Mono',monospace;padding:3px 10px;
                             border-radius:20px;border:1px solid {bc};color:{bc};background:{bg};">{pri}</span>
              </div>
              <div style="font-size:11px;font-family:'JetBrains Mono',monospace;color:#6b6b8a;margin-bottom:6px;">
                Current: {cur}/5 &nbsp;→&nbsp; Required: {req}/5 &nbsp;|&nbsp; Gap: {g.gap_size} levels
                &nbsp;|&nbsp; {"🔴 Must-have" if g.is_required else "🟡 Preferred"}
              </div>
              <div style="height:6px;background:#0a0a0f;border-radius:3px;overflow:hidden;position:relative;">
                <div style="height:100%;width:{pct_cur}%;background:#6c63ff;border-radius:3px;"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:10px;color:#6b6b8a;font-family:'JetBrains Mono',monospace;margin-top:3px;">
                <span>0</span><span style="color:#6c63ff;">▲ You ({cur})</span>
                <span style="color:{bc};">▲ Required ({req})</span><span>5</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>💪 Strong Skills</div>', unsafe_allow_html=True)
        st.markdown(chips(r.strong_skills, "good"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>❌ Missing Skills</div>', unsafe_allow_html=True)
        st.markdown(chips(r.missing_skills, "pref"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if r.adjacent_skills:
        st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>🔗 Adjacent Skills You Can Pick Up</div>', unsafe_allow_html=True)
        for a in r.adjacent_skills:
            effort_color = {"Low":"#43e97b","Medium":"#ffd166","High":"#ff6584"}.get(a.effort_level,"#6b6b8a")
            st.markdown(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #2a2a3d;">
              <div style="font-weight:700;font-size:13px;min-width:130px;">{a.skill}</div>
              <div style="flex:1;font-size:12px;color:#6b6b8a;">{a.why_adjacent}</div>
              <div style="font-size:11px;font-family:'JetBrains Mono',monospace;color:{effort_color};white-space:nowrap;">{a.effort_level} effort</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_fwd = st.columns([1, 1])
    with col_back:
        if st.button("⬅️ Back to Assessment", use_container_width=True):
            st.session_state.stage = "assessing"
            st.rerun()
    with col_fwd:
        if st.button("📚 Generate Learning Plan →", type="primary", use_container_width=True):
            st.session_state.stage = "generating"
            st.rerun()


def stage_generating():
    nav_bar()

    st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>⚙️ Generating Your Report</div>', unsafe_allow_html=True)

    statuses = [
        ("🔎 Agent 3: Running gap analysis…", 0),
        ("📋 LangGraph Node 1: Prioritising skill gaps + resources…", 1),
        ("🗓️ LangGraph Node 2: Building timeline + compiling report…", 2),
        ("✅ Done!", 3),
    ]

    progress_bar = st.progress(0, text=statuses[0][0])
    status_text  = st.empty()

    def update_progress(i):
        msg, pct_idx = statuses[i]
        progress_bar.progress(int((pct_idx + 1) * 25), text=msg)
        status_text.markdown(f"`{msg}`")

    st.markdown("</div>", unsafe_allow_html=True)

    try:
        update_progress(0)
        st.session_state.pipeline.run_gap_analysis()

        update_progress(1)
        time.sleep(0.3)
        update_progress(2)

        report = st.session_state.pipeline.run_learning_plan()
        st.session_state.final_report = report

        update_progress(3)
        time.sleep(0.5)
        st.session_state.stage = "report"
        st.rerun()

    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.session_state.stage = "gap_view"


def stage_report():
    nav_bar()
    r = st.session_state.final_report
    score = int(r.get("overall_readiness_score", 0))
    label = r.get("readiness_label", "—")
    weeks = r.get("total_learning_weeks", 0)
    hrs   = r.get("daily_hours_commitment", 2)

    pct = min(score, 100)
    bar_color = "#43e97b" if score >= 70 else "#ffd166" if score >= 45 else "#ff6584"

    st.markdown(f"""
    <div class="cat-card">
      <div class="cat-card-title"><span class="dot"></span>📊 Assessment Report — {r.get("candidate_name","")} → {r.get("target_role","")}</div>
      <div style="display:flex;align-items:flex-start;gap:32px;flex-wrap:wrap;">
        <div>
          <div class="readiness-score">{score}<span style="font-size:22px;opacity:.5">/100</span></div>
          <div class="readiness-label">{label}</div>
          <div class="progress-track" style="width:260px;margin-top:12px;">
            <div class="progress-fill" style="width:{pct}%;background:linear-gradient(90deg,#6c63ff,{bar_color});"></div>
          </div>
        </div>
        <div style="flex:1;min-width:220px;">
          <div class="info-grid">
            <div class="info-item"><label>Learning Duration</label><div class="val">{weeks} weeks</div></div>
            <div class="info-item"><label>Daily Commitment</label><div class="val">{hrs} hrs/day</div></div>
          </div>
          <div style="margin-top:16px;font-size:14px;line-height:1.7;color:#6b6b8a;">{r.get("executive_summary","")}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📚 Skill Learning Plans", "🗓️ Weekly Schedule", "💪 Strengths & Advice"])

    with tab1:
        skill_plans = r.get("skill_plans", [])
        if not skill_plans:
            st.info("No skill plans generated.")
        else:
            for plan in skill_plans:
                pri = plan.get("priority", "Medium")
                weeks_p = plan.get("estimated_weeks", 4)
                resources = plan.get("resources", [])
                proj = plan.get("practice_project", "")

                res_html = "".join([
                    f'''<div class="resource">
                      <div style="font-size:18px;flex-shrink:0">{icon_for_type(res.get("type",""))}</div>
                      <div class="resource-info">
                        <a href="{res.get("url","#")}" target="_blank">{res.get("title","Resource")}</a>
                        <div class="resource-meta">{res.get("platform","")} · {res.get("duration","")} · {"🟢 Free" if res.get("is_free",True) else "💳 Paid"}</div>
                      </div>
                    </div>'''
                    for res in resources
                ])

                proj_html = f"""<div class="project-box">
                  <div class="project-label">Practice Project</div>{proj}</div>""" if proj else ""

                st.markdown(f"""
                <div class="sp-card">
                  <div class="sp-header">
                    <div class="sp-skill">{plan.get("skill","")}</div>
                    <span class="badge badge-{pri}">{pri}</span>
                  </div>
                  <div class="sp-meta">
                    <span>{plan.get("current_level","?")} → {plan.get("target_level","?")}</span>
                    <span>⏱ {weeks_p} weeks</span>
                  </div>
                  <div class="sp-why">{plan.get("why_important","")}</div>
                  {res_html}
                  {proj_html}
                </div>
                """, unsafe_allow_html=True)
    with tab2:
        schedule = r.get("weekly_schedule", [])
        if not schedule:
            st.info("No schedule generated.")
        else:
            st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>Week-by-Week Plan</div>', unsafe_allow_html=True)
            rows_html = ""
            for w in schedule:
                skills_str = ", ".join(w.get("focus_skills", []))
                rows_html += f"""
                <div class="week-row">
                  <div class="week-num">Week {w.get("week_number","?")}</div>
                  <div style="flex:1">
                    <div class="week-skill">{skills_str}</div>
                    <div class="week-deliv">{w.get("deliverable","")}</div>
                  </div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#6b6b8a;white-space:nowrap;">
                    {w.get("daily_hours_needed",2)}h/day
                  </div>
                </div>"""
            st.markdown(rows_html + "</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="cat-card"><div class="cat-card-title"><span class="dot"></span>Strengths & Final Advice</div>', unsafe_allow_html=True)

        st.markdown('<div class="sec-head">What You\'re Already Good At</div>', unsafe_allow_html=True)
        st.markdown(chips(r.get("strengths", []), "good"), unsafe_allow_html=True)

        st.markdown('<div class="sec-head">Adjacent Skills to Explore Next</div>', unsafe_allow_html=True)
        st.markdown(chips(r.get("adjacent_skills_to_explore", []), "pref"), unsafe_allow_html=True)

        st.markdown('<div class="sec-head">Final Advice</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:14px;line-height:1.75;color:#6b6b8a;">{r.get("final_advice","")}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_reset = st.columns([1, 1])
    with col_back:
        if st.button("⬅️ Back to Gap Analysis", use_container_width=True):
            st.session_state.stage = "gap_view"
            st.rerun()
    with col_reset:
        if st.button("🔄 Start New Assessment", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def main():
    header()

    stage = st.session_state.stage

    if stage == "upload":
        stage_upload()
    elif stage == "extracted":
        stage_extracted()
    elif stage == "assessing":
        stage_assessing()
    elif stage == "gap_view":
        stage_gap_view()
    elif stage == "generating":
        stage_generating()
    elif stage == "report":
        stage_report()
    else:
        st.error(f"Unknown stage: {stage}")


if __name__ == "__main__":
    main()