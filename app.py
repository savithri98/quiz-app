import streamlit as st
import google.generativeai as genai
import json
import re
from fpdf import FPDF
import base64
import sqlite3
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AI MCQ Prep", page_icon="📝", layout="centered")

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('quiz_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            topic TEXT,
            difficulty TEXT,
            score INTEGER,
            total INTEGER,
            questions TEXT,
            answers TEXT,
            username TEXT
        )
    ''')
    try:
        c.execute('ALTER TABLE history ADD COLUMN questions TEXT')
        c.execute('ALTER TABLE history ADD COLUMN answers TEXT')
    except sqlite3.OperationalError:
        pass # Columns already exist
    try:
        c.execute('ALTER TABLE history ADD COLUMN username TEXT')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

init_db()

def save_score(username, topic, difficulty, score, total, questions_json, answers_json):
    conn = sqlite3.connect('quiz_history.db')
    c = conn.cursor()
    c.execute('INSERT INTO history (date, topic, difficulty, score, total, questions, answers, username) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, difficulty, score, total, questions_json, answers_json, username))
    conn.commit()
    conn.close()

def get_history(username):
    conn = sqlite3.connect('quiz_history.db')
    df = pd.read_sql_query('SELECT * FROM history WHERE username = ? ORDER BY id DESC', conn, params=(username,))
    conn.close()
    return df

# --- Aesthetic Overhaul (CSS) ---
st.markdown("""
<style>
    /* Dark Mode Glassmorphic Theme */
    .stApp {
        background-color: #0d0d0d;
        color: #e6e6e6;
    }
    
    /* Center cards and glass effect */
    .stForm, div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlock"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        backdrop-filter: blur(10px);
        margin-bottom: 1rem;
    }

    h1, h2, h3, h4 {
        font-family: 'Inter', sans-serif;
        color: #ffffff !important;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    
    .stButton > button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
        transition: all 0.2s ease-in-out;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(255, 255, 255, 0.2);
    }
    
    .stTextInput > div > div > input, .stSelectbox > div > div > div {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: #fff !important;
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    .stRadio > div {
        background: rgba(255, 255, 255, 0.02);
        padding: 10px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- PDF Generation Utility ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'AI Exam Prep Report', 0, 1, 'C')
        self.ln(5)

def create_pdf(questions, user_answers):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    score = sum([1 for idx, q in enumerate(questions) if user_answers.get(idx) == q['correctIndex'] or user_answers.get(str(idx)) == q['correctIndex']])
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Score: {score} / {len(questions)}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=11)
    for idx, q in enumerate(questions):
        pdf.set_font("Arial", 'B', 12)
        question_text = f"Q{idx+1}. {q['question']}".encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, question_text)
        
        pdf.set_font("Arial", size=10)
        u_ans = user_answers.get(str(idx))
        if u_ans is None:
            u_ans = user_answers.get(idx)
        for o_idx, opt in enumerate(q['options']):
            prefix = "[x]" if u_ans == o_idx else "[ ]"
            asterisk = " (CORRECT)" if o_idx == q['correctIndex'] else ""
            opt_text = f"{prefix} {chr(65+o_idx)}. {opt}{asterisk}".encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 6, opt_text)
        
        pdf.ln(2)
        pdf.set_font("Arial", 'I', 10)
        expl_text = f"Explanation: {q['explanation']}".encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, expl_text)
        pdf.ln(8)
        
    return pdf.output(dest="S").encode("latin-1")

def create_domain_report_pdf(domain, content):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    title = f"Study Manual: {domain}".encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 10, title, 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=11)
    for line in content.split('\n'):
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, clean_line)
    return pdf.output(dest="S").encode("latin-1")

# --- AI Generation Utility ---
def generate_questions(domain, difficulty, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    diff_prompt = "a mix of Easy, Medium, and Hard" if difficulty == "Mixed" else f"strictly {difficulty}"
    prompt = f"""You are an expert exam setter. Generate exactly 10 distinct, unique Multiple Choice Questions for a competitive exam.
Domain/Topic: {domain}
Difficulty: {diff_prompt}

Requirements:
1. Output exactly 10 questions. No more, no less.
2. Each question must have exactly 4 options.
3. Indicate the correct option index (0 to 3).
4. Provide a detailed explanation for the correct answer. 
5. Your response MUST be valid JSON, conforming to exactly this structure:
[
  {{
    "question": "string",
    "options": ["string", "string", "string", "string"],
    "correctIndex": integer,
    "difficulty": "Easy" | "Medium" | "Hard",
    "explanation": "string"
  }}
]"""
    response = model.generate_content(prompt)
    text = response.text
    text = re.sub(r'```json\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\n?', '', text, flags=re.IGNORECASE).strip()
    return json.loads(text)

def generate_domain_report(domain, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    internet_context = ""
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(domain, max_results=3)
        internet_context = "\n\n".join([f"Source ({r['title']}): {r['body']}" for r in results])
    except Exception as e:
        internet_context = "Could not reach the internet."

    prompt = f"""You are a subject matter expert. Write an extremely comprehensive educational study manual about "{domain}".
Use the following recent internet snippets to ensure the facts are up to date and accurate:
{internet_context}

Format Requirement: Write in plain text format only. Use simple paragraph breaks. DO NOT use markdown characters like asterisks (*), hashtags (#), bullet points (-), or backticks, as this breaks our PDF parser. 
Include:
1. Introduction
2. Key Concepts & Principles
3. Historical Context or Recent Trends
4. Summary"""

    response = model.generate_content(prompt)
    return response.text

# --- State Management ---
if 'username' not in st.session_state:
    st.session_state.username = None

# If not logged in, show login screen
if not st.session_state.username:
    st.markdown("<h1 style='text-align: center; margin-top: 100px;'>Welcome to AI Exam Prep</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #a0a0a0;'>Please identify yourself to access your personal dashboard.</p>", unsafe_allow_html=True)
    
    with st.form("login"):
        name_input = st.text_input("Enter your Username / Name:")
        if st.form_submit_button("Sign In"):
            if name_input.strip():
                st.session_state.username = name_input.strip()
                st.rerun()
            else:
                st.error("Name cannot be empty.")
    st.stop()


if 'questions' not in st.session_state:
    st.session_state.questions = None
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = ""
if 'current_difficulty' not in st.session_state:
    st.session_state.current_difficulty = ""
if 'score_saved' not in st.session_state:
    st.session_state.score_saved = False
if 'report_pdf_bytes' not in st.session_state:
    st.session_state.report_pdf_bytes = None
if 'report_domain' not in st.session_state:
    st.session_state.report_domain = None

def restart():
    st.session_state.questions = None
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.score_saved = False
    st.session_state.report_pdf_bytes = None
    st.session_state.report_domain = None

st.markdown("<h1 style='text-align: center;'>AI MCQ Generator</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #a0a0a0; margin-bottom: 2rem;'>Master any domain with dynamic, AI-generated questions</p>", unsafe_allow_html=True)

# Navigation
st.sidebar.title("Navigation")
st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.username}**")
nav_choice = st.sidebar.radio("Go to", ["Take a Quiz", "History Dashboard"], label_visibility="collapsed")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

if nav_choice == "History Dashboard":
    st.subheader(f"Performance History for {st.session_state.username}")
    history_df = get_history(st.session_state.username)
    if history_df.empty:
        st.info("No quiz history found for your account. Take a quiz to see your progress!")
    else:
        display_df = history_df.drop(columns=['questions', 'answers', 'username'], errors='ignore')
        
        st.markdown("<p style='color: #888; font-size: 0.9em; margin-bottom: 0.2rem;'>Click on any row below to view full quiz details.</p>", unsafe_allow_html=True)
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if len(event.selection.rows):
            selected_row_idx = event.selection.rows[0]
            selected_record = history_df.iloc[selected_row_idx]
            
            st.divider()
            st.write(f"### Quiz Details: {selected_record['topic']} ({selected_record['date']})")
            st.write(f"**Score:** {selected_record['score']} / {selected_record['total']}")
            
            try:
                hist_questions = json.loads(selected_record['questions']) if pd.notnull(selected_record.get('questions')) else []
                hist_answers = json.loads(selected_record['answers']) if pd.notnull(selected_record.get('answers')) else {}
            except Exception:
                hist_questions = []
                hist_answers = {}
                
            if not hist_questions:
                st.warning("No detail data available for this older record.")
            else:
                for i, q in enumerate(hist_questions):
                    st.markdown(f"#### Q{i+1}: {q['question']}")
                    
                    user_opt = hist_answers.get(str(i))
                    if user_opt is None:
                        user_opt = hist_answers.get(i)
                        
                    if isinstance(user_opt, str):
                        try:
                            user_opt = int(user_opt)
                        except ValueError:
                            user_opt = None
                            
                    correct_opt = q['correctIndex']
                    
                    for o_idx, opt in enumerate(q['options']):
                        if o_idx == correct_opt:
                            st.markdown(f"✅ **{chr(65+o_idx)}. {opt}**")
                        elif o_idx == user_opt and user_opt != correct_opt:
                            st.markdown(f"❌ ~~{chr(65+o_idx)}. {opt}~~")
                        else:
                            st.markdown(f"- {chr(65+o_idx)}. {opt}")
                            
                    st.info(f"**Explanation:**\n\n{q['explanation']}")
                    st.divider()
        else:
            st.write("### Score Trend (%)")
            display_df['percentage'] = (display_df['score'] / display_df['total']) * 100
            st.line_chart(display_df['percentage'])

else:
    # --- View Routing ---
    if st.session_state.questions is None:
        # 1. SETUP SCREEN
        st.subheader("Configure Your Practice")
        with st.form("setup_form"):
            domain = st.text_input("Topic / Domain (e.g. Quantum Physics, History)")
            difficulty = st.selectbox("Difficulty", ["Mixed", "Easy", "Medium", "Hard"])
            api_key = st.text_input("Gemini API Key", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted_quiz = st.form_submit_button("Generate 10 MCQs")
            with col2:
                submitted_report = st.form_submit_button("Fetch Detailed Study Manual")
                
            if submitted_quiz:
                if not domain:
                    st.error("Please enter a domain.")
                elif not api_key:
                    st.error("Please enter your API Key.")
                else:
                    with st.spinner("Generating distinct questions..."):
                        try:
                            data = generate_questions(domain, difficulty, api_key)
                            st.session_state.questions = data
                            st.session_state.answers = {}
                            st.session_state.submitted = False
                            st.session_state.current_topic = domain
                            st.session_state.current_difficulty = difficulty
                            st.session_state.score_saved = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation failed: {str(e)}")
                            
            if submitted_report:
                if not domain:
                    st.error("Please enter a domain.")
                elif not api_key:
                    st.error("Please enter your API Key.")
                else:
                    with st.spinner(f"Searching internet and synthesizing study manual for {domain}..."):
                        try:
                            report_text = generate_domain_report(domain, api_key)
                            pdf_bytes = create_domain_report_pdf(domain, report_text)
                            st.session_state.report_pdf_bytes = pdf_bytes
                            st.session_state.report_domain = domain
                        except Exception as e:
                            st.error(f"Report generation failed: {str(e)}")

        if st.session_state.report_pdf_bytes:
            st.success(f"Study Manual for '{st.session_state.report_domain}' generated successfully!")
            st.download_button(
                label=f"Download {st.session_state.report_domain} Manual PDF",
                data=st.session_state.report_pdf_bytes,
                file_name=f"{st.session_state.report_domain}_StudyGuide.pdf",
                mime="application/pdf",
                type="primary"
            )

    elif not st.session_state.submitted:
        # 2. QUIZ SCREEN
        st.subheader("Quiz Mode")
        st.progress(len(st.session_state.answers) / len(st.session_state.questions))
        
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.questions):
                st.markdown(f"**Q{i+1}: {q['question']}** *({q['difficulty']})*")
                selected = st.radio("Options", q['options'], key=f"q_{i}", index=None, label_visibility="collapsed")
                if selected is not None:
                    st.session_state.answers[i] = q['options'].index(selected)
                st.divider()
            
            submit_quiz = st.form_submit_button("Finish & Evaluate")
            if submit_quiz:
                if len(st.session_state.answers) < len(st.session_state.questions):
                    st.warning("You missed some questions! Please answer all.")
                else:
                    st.session_state.submitted = True
                    st.rerun()
        
        if st.button("Quit Quiz"):
            restart()
            st.rerun()

    else:
        # 3. RESULTS SCREEN
        questions = st.session_state.questions
        answers = st.session_state.answers
        
        score = sum([1 for i, q in enumerate(questions) if answers.get(i) == q['correctIndex']])
        
        # Save score instantly
        if not st.session_state.score_saved:
            q_json = json.dumps(questions)
            a_json = json.dumps(answers)
            save_score(st.session_state.username, st.session_state.current_topic, st.session_state.current_difficulty, score, len(questions), q_json, a_json)
            st.session_state.score_saved = True

        st.success(f"## Practice Complete! Score: {score} / {len(questions)}")
        
        pdf_bytes = create_pdf(questions, answers)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start New Test"):
                restart()
                st.rerun()
        with col2:
            st.download_button(
                label="Download Quiz Report PDF",
                data=pdf_bytes,
                file_name="Quiz_Result_Report.pdf",
                mime="application/pdf"
            )
        
        st.divider()
        
        for i, q in enumerate(questions):
            st.markdown(f"### Q{i+1}: {q['question']}")
            
            user_opt = answers.get(i)
            correct_opt = q['correctIndex']
            
            for o_idx, opt in enumerate(q['options']):
                if o_idx == correct_opt:
                    st.markdown(f"✅ **{chr(65+o_idx)}. {opt}**")
                elif o_idx == user_opt and user_opt != correct_opt:
                    st.markdown(f"❌ ~~{chr(65+o_idx)}. {opt}~~")
                else:
                    st.markdown(f"- {chr(65+o_idx)}. {opt}")
                    
            st.info(f"**Explanation:**\n\n{q['explanation']}")
            st.divider()
