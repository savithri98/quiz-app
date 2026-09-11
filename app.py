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
            total INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_score(topic, difficulty, score, total):
    conn = sqlite3.connect('quiz_history.db')
    c = conn.cursor()
    c.execute('INSERT INTO history (date, topic, difficulty, score, total) VALUES (?, ?, ?, ?, ?)',
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, difficulty, score, total))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('quiz_history.db')
    df = pd.read_sql_query('SELECT * FROM history ORDER BY id DESC', conn)
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
    
    score = sum([1 for idx, q in enumerate(questions) if user_answers.get(idx) == q['correctIndex']])
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Score: {score} / {len(questions)}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=11)
    for idx, q in enumerate(questions):
        pdf.set_font("Arial", 'B', 12)
        question_text = f"Q{idx+1}. {q['question']}".encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, question_text)
        
        pdf.set_font("Arial", size=10)
        for o_idx, opt in enumerate(q['options']):
            prefix = "[x]" if user_answers.get(idx) == o_idx else "[ ]"
            asterisk = " (CORRECT)" if o_idx == q['correctIndex'] else ""
            opt_text = f"{prefix} {chr(65+o_idx)}. {opt}{asterisk}".encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 6, opt_text)
        
        pdf.ln(2)
        pdf.set_font("Arial", 'I', 10)
        expl_text = f"Explanation: {q['explanation']}".encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, expl_text)
        pdf.ln(8)
        
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

# --- State Management ---
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

def restart():
    st.session_state.questions = None
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.score_saved = False

st.markdown("<h1 style='text-align: center;'>AI MCQ Generator</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #a0a0a0; margin-bottom: 2rem;'>Master any domain with dynamic, AI-generated questions</p>", unsafe_allow_html=True)

# Navigation
st.sidebar.title("Navigation")
nav_choice = st.sidebar.radio("Go to", ["Take a Quiz", "History Dashboard"], label_visibility="collapsed")

if nav_choice == "History Dashboard":
    st.subheader("Your Past Performance")
    history_df = get_history()
    if history_df.empty:
        st.info("No quiz history found. Take a quiz to see your progress!")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        
        st.write("### Score Trend (%)")
        history_df['percentage'] = (history_df['score'] / history_df['total']) * 100
        st.line_chart(history_df['percentage'])

else:
    # --- View Routing ---
    if st.session_state.questions is None:
        # 1. SETUP SCREEN
        st.subheader("Configure Your Practice")
        with st.form("setup_form"):
            domain = st.text_input("Topic / Domain (e.g. Quantum Physics, History)")
            difficulty = st.selectbox("Difficulty", ["Mixed", "Easy", "Medium", "Hard"])
            api_key = st.text_input("Gemini API Key", type="password")
            
            submitted = st.form_submit_button("Generate 10 MCQs")
            
            if submitted:
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
            save_score(st.session_state.current_topic, st.session_state.current_difficulty, score, len(questions))
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
                label="Download PDF Report",
                data=pdf_bytes,
                file_name="Exam_Prep_Report.pdf",
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
