import streamlit as st
import google.generativeai as genai
import json
import re
from fpdf import FPDF
import base64
import pandas as pd
from datetime import datetime
import tempfile
import os
import urllib.request
from supabase import create_client, Client
import tempfile
import os
import urllib.request
from youtube_transcript_api import YouTubeTranscriptApi

st.set_page_config(page_title="AI MCQ Prep", page_icon="📝", layout="centered")

# --- Supabase Database ---
@st.cache_resource
def get_supabase_client() -> Client:
    """Create a persistent Supabase connection."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("⚠️ **Supabase Authentication Failed!**")
        st.warning("Please ensure you have added both `SUPABASE_URL` and `SUPABASE_KEY` to your Streamlit Cloud Secrets.")
        st.stop()

def save_score(username, topic, difficulty, score, total, questions_json, answers_json):
    supa = get_supabase_client()
    data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "difficulty": difficulty,
        "score": score,
        "total": total,
        "questions": questions_json,
        "answers": answers_json,
        "username": username
    }
    try:
        supa.table("history").insert(data).execute()
    except Exception as e:
        st.error(f"Failed to save score. Ensure the `history` table exists in Supabase. Error: {e}")

def get_history(username):
    supa = get_supabase_client()
    try:
        response = supa.table("history").select("*").eq("username", username).order("id", desc=True).execute()
        data = response.data
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

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

def create_domain_report_pdf(domain, content, image_paths=None):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    title = f"Study Manual: {domain}".encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 10, title, 0, 1, 'C')
    pdf.ln(5)
    
    # Embed images at the top if available
    if image_paths:
        for img_path in image_paths:
            try:
                pdf.image(img_path, x=15, w=180)
                pdf.ln(5)
            except Exception:
                pass
        pdf.add_page()
    
    pdf.set_font("Arial", size=11)
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue
        # Detect section headers (lines ending with colon or all caps short lines)
        if stripped.endswith(':') and len(stripped) < 80:
            pdf.ln(4)
            pdf.set_font("Arial", 'B', 13)
            pdf.multi_cell(0, 8, stripped.encode('latin-1', 'replace').decode('latin-1'))
            pdf.set_font("Arial", size=11)
        elif stripped.startswith('- ') or stripped.startswith('> '):
            bullet_text = f"  {stripped}".encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 6, bullet_text)
        else:
            clean_line = stripped.encode('latin-1', 'replace').decode('latin-1')
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

def extract_youtube_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def generate_youtube_questions(youtube_url, difficulty, api_key):
    vid_id = extract_youtube_id(youtube_url)
    if not vid_id:
        raise ValueError("Invalid YouTube URL")
    
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(vid_id)
        
        # Try to find English or Common Indian languages first
        try:
            transcript = transcript_list.find_transcript(['en', 'hi', 'kn', 'ta', 'te', 'ml', 'mr', 'bn', 'gu'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['en', 'hi', 'kn', 'ta', 'te', 'ml', 'mr', 'bn', 'gu'])
            except Exception:
                # Fallback: Just grab the absolute very first transcript available in ANY language!
                transcript = next(iter(transcript_list))
                
        transcript_data = transcript.fetch()
        transcript_text = " ".join([t['text'] for t in transcript_data])
        
    except Exception as e:
        raise ValueError(f"Could not fetch transcript from this video. Ensure it has captions enabled! Error details: {str(e)[:200]}")
    
    # Cap transcript length so we don't blow up token limits
    transcript = transcript_text[:15000] 
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    diff_prompt = "a mix of Easy, Medium, and Hard" if difficulty == "Mixed" else f"strictly {difficulty}"
    prompt = f"""You are an expert exam setter. Read this video transcript and generate exactly 10 distinct, unique Multiple Choice Questions based strictly on the content of the video.
Transcript Snippet: {transcript}
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

def fetch_domain_images(domain):
    """Fetch relevant images from DuckDuckGo and save to temp files."""
    image_paths = []
    try:
        from duckduckgo_search import DDGS
        results = DDGS().images(domain, max_results=3)
        for idx, r in enumerate(results):
            try:
                url = r['image']
                tmp_path = os.path.join(tempfile.gettempdir(), f"domain_img_{idx}.jpg")
                urllib.request.urlretrieve(url, tmp_path)
                image_paths.append(tmp_path)
            except Exception:
                continue
    except Exception:
        pass
    return image_paths

def generate_domain_report(domain, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    internet_context = ""
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(domain, max_results=5)
        internet_context = "\n\n".join([f"Source ({r['title']}): {r['body']}" for r in results])
    except Exception as e:
        internet_context = "Could not reach the internet."

    prompt = f"""You are a subject matter expert. Write an extremely comprehensive educational study manual about "{domain}".
Use the following recent internet snippets to ensure the facts are up to date and accurate:
{internet_context}

FORMATTING RULES (STRICTLY FOLLOW):
- Write EVERY piece of information as a bullet point starting with "- "
- Group bullet points under section headers. Write section headers as a short title followed by a colon, e.g. "Introduction:"
- DO NOT use markdown characters like asterisks (*), hashtags (#), or backticks (`)
- DO NOT write long paragraphs. Every sentence should be its own bullet point.

Sections to include:
Introduction:
Key Concepts and Principles:
Important Facts and Figures:
Historical Context:
Recent Trends and Developments:
Common Exam Questions and Tips:
Summary:"""

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
                q_val = selected_record.get('questions', '')
                a_val = selected_record.get('answers', '')
                hist_questions = json.loads(q_val) if q_val else []
                hist_answers = json.loads(a_val) if a_val else {}
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
            display_df['score'] = pd.to_numeric(display_df['score'], errors='coerce')
            display_df['total'] = pd.to_numeric(display_df['total'], errors='coerce')
            display_df['percentage'] = (display_df['score'] / display_df['total']) * 100
            st.line_chart(display_df['percentage'])

else:
    # --- View Routing ---
    if st.session_state.questions is None:
        # 1. SETUP SCREEN
        st.subheader("Configure Your Practice")
        
        tab_domain, tab_youtube = st.tabs(["Topic / Domain", "YouTube Video"])
        
        with tab_domain:
            with st.form("setup_form_domain"):
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
                                image_paths = fetch_domain_images(domain)
                                pdf_bytes = create_domain_report_pdf(domain, report_text, image_paths)
                                st.session_state.report_pdf_bytes = pdf_bytes
                                st.session_state.report_domain = domain
                            except Exception as e:
                                st.error(f"Report generation failed: {str(e)}")
                                
        with tab_youtube:
            with st.form("setup_form_youtube"):
                youtube_url = st.text_input("YouTube Video URL")
                yt_difficulty = st.selectbox("Difficulty", ["Mixed", "Easy", "Medium", "Hard"], key="yt_diff")
                yt_api_key = st.text_input("Gemini API Key", type="password", key="yt_key")
                
                submitted_yt_quiz = st.form_submit_button("Generate MCQs from Video")
                
                if submitted_yt_quiz:
                    if not youtube_url:
                        st.error("Please enter a YouTube URL.")
                    elif not yt_api_key:
                        st.error("Please enter your API Key.")
                    else:
                        with st.spinner("Fetching transcript and generating questions..."):
                            try:
                                data = generate_youtube_questions(youtube_url, yt_difficulty, yt_api_key)
                                st.session_state.questions = data
                                st.session_state.answers = {}
                                st.session_state.submitted = False
                                st.session_state.current_topic = f"YouTube: {youtube_url[:30]}..."
                                st.session_state.current_difficulty = yt_difficulty
                                st.session_state.score_saved = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Generation failed: {str(e)}")

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
