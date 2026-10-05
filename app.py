import streamlit as st
import plotly.express as px
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

def get_ca_from_db(date_str):
    supa = get_supabase_client()
    try:
        response = supa.table("current_affairs").select("content").eq("date", date_str).execute()
        if response.data:
            return response.data[0]["content"]
    except Exception:
        pass
    return None

def save_ca_to_db(date_str, content):
    supa = get_supabase_client()
    try:
        supa.table("current_affairs").upsert({"date": date_str, "content": content}).execute()
    except Exception:
        pass

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
        try:
            transcript_text = " ".join([t['text'] for t in transcript_data])
        except TypeError:
            transcript_text = " ".join([t.text for t in transcript_data])
        
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

def generate_current_affairs_report(date_str, region, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    search_topic = "Karnataka State" if region == "Karnataka" else "India"
    
    internet_context = ""
    try:
        from duckduckgo_search import DDGS
        # Search for news specifically on that date related to the region
        search_query = f"{search_topic} Current affairs top news {date_str}"
        results = DDGS().text(search_query, max_results=10)
        internet_context = "\n\n".join([f"Source ({r['title']}): {r['body']}" for r in results])
    except Exception:
        internet_context = "Could not reach the internet."
        
    prompt = f"""You are a master civil services exam setter for Indian competitive exams (like KPSC/UPSC).
Your task is to write a highly detailed, systematic, point-by-point Daily Current Affairs brief specifically focusing on **{search_topic}** for exactly this date: {date_str}.

Use the following internet search snippets to ensure your facts are accurate for that specific day:
{internet_context}

FORMATTING RULES:
- Write strictly in Markdown. Cover Politics, Economy, Science/Tech, and Social Issues relevant to {search_topic}.
- Use clear bullet points.
- Highlight key terms, schemes, or names in **bold**.
- Be purely educational and factual, tailored for a student preparing for KRIES / KPSC exams.
- If the internet snippets don't have enough data for that exact date, provide general important current affairs from that specific month/week of that year for {search_topic}."""
    
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
nav_choice = st.sidebar.radio("Go to", ["Take a Quiz", "History Dashboard", "Current Affairs 🇮🇳", "Study Plan 📚", "Focus Chamber ⏱️"], label_visibility="collapsed")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# --- Gamification: Streaks & XP ---
try:
    history_df_sb = get_history(st.session_state.username)
    if not history_df_sb.empty:
        total_score = pd.to_numeric(history_df_sb['score'], errors='coerce').sum()
        total_quizzes = len(history_df_sb)
    else:
        total_score = 0
        total_quizzes = 0
except:
    total_score = 0
    total_quizzes = 0

xp = int(total_score * 15 + total_quizzes * 50)
level = int((xp / 500) ** 0.8) + 1
next_level_xp = int((level ** 1.25) * 500)

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #16213e, #0f3460); padding: 1rem; border-radius: 12px; margin-top: 2rem; border: 1px solid #1a1a2e; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
    <h3 style="color: #f7c948; margin:0 0 5px 0;">🔥 Level {level}</h3>
    <p style="color: white; margin:0; font-size: 1.1rem; font-weight: bold;">{xp} <span style="color: #a0a0a0; font-size: 0.9rem; font-weight: normal;">XP</span></p>
    <div style="width: 100%; background-color: #1a1a2e; border-radius: 5px; margin-top: 8px;">
        <div style="width: {min((xp/next_level_xp)*100, 100)}%; height: 8px; background-color: #f7c948; border-radius: 5px;"></div>
    </div>
    <p style="color: #a0a0a0; margin: 4px 0 0 0; font-size: 0.75rem; text-align: right;">{next_level_xp} XP to next lvl</p>
</div>
""", unsafe_allow_html=True)


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

elif nav_choice == "Current Affairs 🇮🇳":
    st.subheader("Daily Current Affairs Portal")
    st.markdown("Select a date and region to fetch or generate the current affairs for that specific day.")
    
    region_choice = st.radio("Select Scope:", ["National (India 🇮🇳)", "Karnataka State 🟡🔴"], horizontal=True)
    region_key = "Karnataka" if "Karnataka" in region_choice else "India"
    
    col1, col2 = st.columns(2)
    with col1:
        selected_date = st.date_input("Select Date", value=datetime.today(), min_value=datetime(2025, 8, 1), max_value=datetime.today())
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        api_key_ca = st.text_input("Gemini API Key (if generating new)", type="password", key="ca_api_key")
        
    date_str = selected_date.strftime("%Y-%m-%d")
    cache_key = f"{date_str}_{region_key}"
    
    if st.button("Load / Generate Current Affairs"):
        with st.spinner("Checking Database..."):
            ca_content = get_ca_from_db(cache_key)
            
        if ca_content:
            st.success("Loaded instantly from Database Cache! ✅")
            st.markdown(ca_content)
        else:
            if not api_key_ca:
                st.error("This date hasn't been generated yet. Please enter your Gemini API Key to let the AI search and synthesize it!")
            else:
                with st.spinner(f"First time generating {region_key} news for {date_str}. Searching the internet and synthesizing..."):
                    try:
                        ca_content = generate_current_affairs_report(date_str, region_key, api_key_ca)
                        save_ca_to_db(cache_key, ca_content)
                        st.success("Generated and permanently cached to database! ✅")
                        st.markdown(ca_content)
                    except Exception as e:
                        st.error(f"Generation failed: {str(e)}")

elif nav_choice == "Study Plan \U0001f4da":
    # --- Tab switch between KRIES and KSET ---
    sp_tab1, sp_tab2 = st.tabs(["🔥 KRIES — Computer Science Teacher", "🎓 KSET — Assistant Professor"])

    with sp_tab1:
        # --- Motivational Header ---
        from datetime import date as dt_date
        today = dt_date.today()
        exam_target = dt_date(2026, 11, 15)
        days_left = (exam_target - today).days
        if days_left < 0:
            days_left = 0

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FF6B35, #F7C948, #FF6B35); padding: 2rem; border-radius: 20px; text-align: center; margin-bottom: 2rem; animation: pulse 2s infinite;">
            <h1 style="color: #1a1a2e; margin: 0; font-size: 2.5rem;">🔥 KRIES EXAM WARRIOR 🔥</h1>
            <p style="color: #1a1a2e; font-size: 1.3rem; margin: 0.5rem 0;">Computer Science Teacher | Your Dream Job Awaits!</p>
            <div style="display: flex; justify-content: center; gap: 2rem; margin-top: 1rem;">
                <div style="background: rgba(0,0,0,0.2); padding: 1rem 2rem; border-radius: 15px;">
                    <h2 style="color: white; margin: 0; font-size: 3rem;">{days_left}</h2>
                    <p style="color: #f0f0f0; margin: 0; font-size: 1rem;">DAYS LEFT</p>
                </div>
            </div>
            <p style="color: #1a1a2e; font-size: 1rem; margin-top: 1rem; font-style: italic;">"Every expert was once a beginner. START NOW."</p>
        </div>
        <style>
            @keyframes pulse {{
                0% {{ transform: scale(1); }}
                50% {{ transform: scale(1.01); }}
                100% {{ transform: scale(1); }}
            }}
        </style>
        """, unsafe_allow_html=True)

        import math
        week_num = min(math.ceil((today - dt_date(2026, 10, 5)).days / 7), 4)
        if week_num < 1:
            week_num = 1

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f3460, #16213e); border: 2px solid #e94560; padding: 1.5rem; border-radius: 15px; margin-bottom: 1.5rem;">
            <h3 style="color: #e94560; margin: 0;">🎯 TODAY\'S MISSION — {today.strftime('%A, %B %d')}</h3>
            <p style="color: #a0a0a0; margin: 0.3rem 0;">Week {week_num} of your preparation journey</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 📅 Week 1: C Programming + Indian Constitution (Oct 5–11)")
        w1 = [
            ["Sun 5", "C Basics: History, structure, keywords", "Indian Constitution: Preamble, Fundamental Rights"],
            ["Mon 6", "Variables, Data Types, Constants, Operators", "Directive Principles, Fundamental Duties"],
            ["Tue 7", "Control Instructions (if-else, switch, loops)", "Indian Polity: Parliament, President, PM"],
            ["Wed 8", "Functions, Recursion, Scope", "Karnataka History: Chalukyas to Vijayanagara"],
            ["Thu 9", "Arrays (1D, 2D), Strings in C", "Karnataka Geography: Rivers, Districts, Dams"],
            ["Fri 10", "Pointers, Dynamic Memory Allocation", "Current Affairs (use your app!)"],
            ["Sat 11", "📝 REVISION + MOCK TEST", "📝 REVISION + MOCK TEST"]
        ]
        st.dataframe(pd.DataFrame(w1, columns=["Day", "💻 Paper II (CS)", "📖 Paper I (GK)"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 2: Data Structures + Indian History (Oct 12–18)")
        w2 = [
            ["Sun 12", "Structures, Unions, typedef in C", "Indian History: Ancient India"],
            ["Mon 13", "File Handling in C", "Medieval India, Mughal Empire"],
            ["Tue 14", "Computer Fundamentals: CPU, Memory, I/O", "Indian Freedom Movement"],
            ["Wed 15", "Number Systems: Binary, Octal, Hex", "Indian Geography: Physical features, Climate"],
            ["Thu 16", "Boolean Algebra, Logic Gates", "Indian Economy: Five Year Plans, NITI Aayog"],
            ["Fri 17", "Operating Systems Basics", "Karnataka: State schemes, Budget"],
            ["Sat 18", "📝 REVISION + MOCK TEST", "📝 REVISION + MOCK TEST"]
        ]
        st.dataframe(pd.DataFrame(w2, columns=["Day", "💻 Paper II (CS)", "📖 Paper I (GK)"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 3: Networking + Science & Environment (Oct 19–25)")
        w3 = [
            ["Sun 19", "Computer Networks: LAN, WAN, TCP/IP", "General Science: Physics basics"],
            ["Mon 20", "Internet, Protocols (HTTP, FTP, SMTP)", "Chemistry: Elements, Compounds, Reactions"],
            ["Tue 21", "Database Basics: DBMS, SQL queries", "Biology: Human body, Diseases, Nutrition"],
            ["Wed 22", "HTML, Web Technologies basics", "Environmental Science & Ecology"],
            ["Thu 23", "Cyber Security, Viruses, Firewalls", "Space & Technology: ISRO missions"],
            ["Fri 24", "MS Office (Word, Excel, PowerPoint)", "Current Affairs (use your app!)"],
            ["Sat 25", "📝 FULL MOCK TEST (100 CS Qs)", "📝 FULL MOCK TEST (100 GK Qs)"]
        ]
        st.dataframe(pd.DataFrame(w3, columns=["Day", "💻 Paper II (CS)", "📖 Paper I (GK)"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 4: Final Revision Sprint (Oct 26 – Nov 1)")
        w4 = [
            ["Sun 26", "Revise all C Programming", "—"],
            ["Mon 27", "Revise Computer Fundamentals + Networks", "—"],
            ["Tue 28", "—", "Revise Indian Constitution + Karnataka History"],
            ["Wed 29", "—", "Revise Indian Geography + Economy"],
            ["Thu 30", "Current Affairs marathon (Aug–Oct)", "Current Affairs marathon (Aug–Oct)"],
            ["Fri 31", "🔥 FULL-LENGTH MOCK TEST", "🔥 FULL-LENGTH MOCK TEST"],
            ["Sat 1", "Light revision, rest, confidence!", "Light revision, rest, confidence!"]
        ]
        st.dataframe(pd.DataFrame(w4, columns=["Day", "💻 Paper II (CS)", "📖 Paper I (GK)"]), use_container_width=True, hide_index=True)

        st.markdown("""
        <div style="background: linear-gradient(135deg, #0f3460, #16213e); border-left: 5px solid #e94560; padding: 1.5rem; border-radius: 10px; margin-top: 1.5rem;">
            <h3 style="color: #e94560; margin: 0 0 0.5rem 0;">🎯 KRIES Exam Pattern</h3>
            <table style="width: 100%; color: #e0e0e0; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #333;"><th style="padding: 8px; text-align: left;">Paper</th><th style="padding: 8px; text-align: left;">Subject</th><th style="padding: 8px;">Qs</th><th style="padding: 8px;">Marks</th><th style="padding: 8px;">Time</th></tr>
                <tr style="border-bottom: 1px solid #333;"><td style="padding: 8px;">Paper I</td><td style="padding: 8px;">General Studies / GK</td><td style="padding: 8px; text-align: center;">100</td><td style="padding: 8px; text-align: center;">100</td><td style="padding: 8px; text-align: center;">2 Hrs</td></tr>
                <tr><td style="padding: 8px;">Paper II</td><td style="padding: 8px;">Computer Science</td><td style="padding: 8px; text-align: center;">100</td><td style="padding: 8px; text-align: center;">100</td><td style="padding: 8px; text-align: center;">2 Hrs</td></tr>
            </table>
            <p style="color: #e94560; margin: 0.8rem 0 0 0; font-weight: bold;">⚠️ Negative Marking: -0.25 per wrong answer</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #e94560, #FF6B35); padding: 1.5rem; border-radius: 15px; text-align: center; margin-top: 2rem;">
            <h2 style="color: white; margin: 0;">💪 YOU'VE GOT THIS!</h2>
            <p style="color: #f0f0f0; font-size: 1.1rem; margin: 0.5rem 0 0 0;">"C Programming is KING" — master it, and 50% of Paper II is yours!</p>
            <p style="color: #f0f0f0; font-size: 0.9rem; margin: 0.3rem 0 0 0;">💡 Pro Tip: Generate 10 MCQs daily on today's topic!</p>
        </div>
        """, unsafe_allow_html=True)

    with sp_tab2:
        # --- KSET Study Plan ---
        from datetime import date as dt_date2
        today2 = dt_date2.today()

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); padding: 2rem; border-radius: 20px; text-align: center; margin-bottom: 2rem; border: 2px solid #6c63ff;">
            <h1 style="color: #f7c948; margin: 0; font-size: 2.5rem;">🎓 KSET WARRIOR 🎓</h1>
            <p style="color: #c0c0f0; font-size: 1.3rem; margin: 0.5rem 0;">Computer Science & Applications | Assistant Professor</p>
            <div style="background: rgba(108,99,255,0.2); padding: 0.8rem 1.5rem; border-radius: 12px; display: inline-block; margin-top: 1rem;">
                <p style="color: #f7c948; margin: 0; font-size: 1.1rem; font-weight: bold;">100 Questions | 200 Marks | No Negative Marking ✅</p>
            </div>
            <p style="color: #a0a0e0; font-size: 1rem; margin-top: 1rem; font-style: italic;">"The higher the level, the greater the reward. REACH FOR IT."</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background: linear-gradient(135deg, #0f3460, #16213e); border: 2px solid #6c63ff; padding: 1.2rem; border-radius: 12px; margin-bottom: 1.5rem;">
            <p style="color: #c0c0f0; margin: 0; font-size: 1rem;">
            🧠 KSET Paper 2 is fully aligned with the <b style="color:#f7c948">UGC NET Computer Science syllabus</b>.
            It tests you on advanced CS concepts — far beyond KRIES level.
            The good news: <b style="color:#6c63ff">no negative marking!</b> So attempt every question.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 📅 Week 1: Foundations & Logic (Oct 6–12)")
        kw1 = [
            ["Mon 6",  "Discrete Math: Set Theory, Relations, Functions, Logic", "Graph Theory: Coloring, Trees, Spanning Trees"],
            ["Tue 7",  "Counting & Combinatorics, Pigeonhole Principle", "Group Theory, Lattices, Boolean Algebra"],
            ["Wed 8",  "Digital Logic: Gates, K-Maps, Combinational Circuits", "Sequential Circuits: Flip-flops, Counters, Registers"],
            ["Thu 9",  "Computer Org: Data representation, Registers, ALU", "Instruction Cycle, Addressing Modes, Pipelining"],
            ["Fri 10", "Memory Hierarchy: Cache, RAM, Virtual Memory", "I/O Organization, DMA, Interrupts"],
            ["Sat 11", "📝 REVISION — Discrete Math", "📝 REVISION — Digital Logic & Arch"],
            ["Sun 12", "🔥 MOCK TEST: Foundations", "🔥 MOCK TEST: Foundations"]
        ]
        st.dataframe(pd.DataFrame(kw1, columns=["Day", "💻 CS Topic A", "💻 CS Topic B"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 2: Core Engineering (Oct 13–19)")
        kw2 = [
            ["Mon 13", "Data Structures: Arrays, Linked Lists, Stacks, Queues", "Trees: BST, AVL, Red-Black, B-Trees, Heaps"],
            ["Tue 14", "Hashing, Graph Algorithms: BFS, DFS, Dijkstra, Floyd", "Sorting & Searching: Merge Sort, Quick Sort, Bin. Search"],
            ["Wed 15", "Algorithm Design: Greedy, D&C, Backtracking", "Dynamic Programming, NP-Completeness, Complexity"],
            ["Thu 16", "Theory of Computation: FA, NFA, Regular Expressions", "Context-Free Grammar, PDAs, Pushdown Automata"],
            ["Fri 17", "Turing Machines, Decidability, Halting Problem", "Compiler Design: Lexical Analysis, Parsing Techniques"],
            ["Sat 18", "📝 REVISION — Data Structures & Algorithms", "📝 REVISION — TOC & Compilers"],
            ["Sun 19", "🔥 MOCK TEST: Core Engineering", "🔥 MOCK TEST: Core Engineering"]
        ]
        st.dataframe(pd.DataFrame(kw2, columns=["Day", "💻 CS Topic A", "💻 CS Topic B"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 3: Systems & Networks (Oct 20–26)")
        kw3 = [
            ["Mon 20", "OS: Process Management, Scheduling Algorithms", "Deadlocks, Synchronization, Semaphores"],
            ["Tue 21", "Memory Management: Paging, Segmentation, TLB", "File Systems, I/O Management"],
            ["Wed 22", "Computer Networks: OSI & TCP/IP Models, IP Addressing", "Routing Protocols: RIP, OSPF, BGP"],
            ["Thu 23", "Transport Layer: TCP vs UDP, Congestion Control", "Application Layer: HTTP, DNS, FTP, SMTP, HTTPS"],
            ["Fri 24", "Network Security: Cryptography, Firewalls, VPNs", "Wireless: WiFi, Bluetooth, 4G/5G Architecture"],
            ["Sat 25", "📝 REVISION — Operating Systems", "📝 REVISION — Networks & Security"],
            ["Sun 26", "🔥 MOCK TEST: Systems & Networks", "🔥 MOCK TEST: Systems & Networks"]
        ]
        st.dataframe(pd.DataFrame(kw3, columns=["Day", "💻 CS Topic A", "💻 CS Topic B"]), use_container_width=True, hide_index=True)

        st.markdown("### 📅 Week 4: Advanced Tech & Full Revision (Oct 27 – Nov 2)")
        kw4 = [
            ["Mon 27", "DBMS: Relational Model, SQL, Relational Algebra", "Normalization: 1NF to BCNF, Functional Dependencies"],
            ["Tue 28", "Transaction Processing, ACID, Concurrency Control", "Distributed Databases, NoSQL Basics"],
            ["Wed 29", "Software Engineering: SDLC, Agile, Waterfall", "Testing: Unit, Integration, Black/White Box, UML"],
            ["Thu 30", "Artificial Intelligence: Search algorithms (A*, BFS)", "Machine Learning basics, ANN, Expert Systems"],
            ["Fri 31", "OOP: Java/C++ Concepts, Inheritance, Polymorphism", "Web Tech: HTML, XML, HTTP Architecture"],
            ["Sat 1",  "🔥 FULL MOCK TEST — All Topics", "🔥 FULL MOCK TEST — All Topics"],
            ["Sun 2",  "🧘 Light Revision + Rest", "🧘 Confidence Building"]
        ]
        st.dataframe(pd.DataFrame(kw4, columns=["Day", "💻 CS Topic A", "💻 CS Topic B"]), use_container_width=True, hide_index=True)

        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e, #0f3460); border-left: 5px solid #6c63ff; padding: 1.5rem; border-radius: 10px; margin-top: 1.5rem;">
            <h3 style="color: #f7c948; margin: 0 0 0.8rem 0;">🎯 KSET High-Weightage Topics</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; color: #c0c0f0;">
                <div>
                    <p style="color: #6c63ff; font-weight: bold; margin: 0 0 0.3rem;">Very High Weightage</p>
                    <ul style="margin: 0; padding-left: 1.2rem;">
                        <li>Data Structures & Algorithms</li>
                        <li>DBMS & SQL</li>
                        <li>Operating Systems</li>
                        <li>Computer Networks</li>
                    </ul>
                </div>
                <div>
                    <p style="color: #6c63ff; font-weight: bold; margin: 0 0 0.3rem;">High Weightage</p>
                    <ul style="margin: 0; padding-left: 1.2rem;">
                        <li>Theory of Computation</li>
                        <li>Discrete Mathematics</li>
                        <li>Software Engineering</li>
                        <li>Computer Organization</li>
                    </ul>
                </div>
            </div>
            <p style="color: #f7c948; margin: 1rem 0 0 0; font-weight: bold;">✅ NO NEGATIVE MARKING — Attempt every single question!</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #6c63ff, #1a1a2e); padding: 1.5rem; border-radius: 15px; text-align: center; margin-top: 2rem;">
            <h2 style="color: white; margin: 0;">🎓 FUTURE PROFESSOR — OWN IT!</h2>
            <p style="color: #f0f0f0; font-size: 1.1rem; margin: 0.5rem 0 0 0;">Master DSA + DBMS + OS + Networks = 60%+ of the paper solved!</p>
            <p style="color: #f0f0f0; font-size: 0.9rem; margin: 0.3rem 0 0 0;">💡 Pro Tip: Use the Quiz tab and type topics like "DBMS Normalization KSET level" for hard questions!</p>
        </div>
        """, unsafe_allow_html=True)

elif nav_choice == "Focus Chamber ⏱️":
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #FF6B35, #F7C948, #FF6B35); padding: 2rem; border-radius: 20px; text-align: center; margin-bottom: 2rem; animation: pulse 2s infinite;">
        <h1 style="color: #1a1a2e; margin: 0; font-size: 2.5rem;">⏱️ FOCUS CHAMBER</h1>
        <p style="color: #1a1a2e; font-size: 1.3rem; margin: 0.5rem 0;">25 Minutes of Unbroken Concentration</p>
    </div>
    <style>
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.01); }}
            100% {{ transform: scale(1); }}
        }}
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### Prepare your study environment. Lock in.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        import time
        
        if "focus_timer_active" not in st.session_state:
            st.session_state.focus_timer_active = False
            
        if not st.session_state.focus_timer_active:
            if st.button("🔴 ENTER DEEP FOCUS (Start 25m)", use_container_width=True):
                st.session_state.focus_timer_active = True
                st.rerun()
        else:
            if st.button("⏹️ ABORT MISSION", use_container_width=True):
                st.session_state.focus_timer_active = False
                st.rerun()
                
            ph = st.empty()
            
            # Simple JS timer instead of blocking python sleep for better UX in Streamlit
            st.components.v1.html("""
            <div style="text-align: center; color: white; font-family: 'Courier New', monospace; font-size: 6rem; font-weight: bold; background: #1a1a2e; padding: 2rem; border-radius: 20px; border: 2px solid #e94560; box-shadow: 0 0 20px rgba(233, 69, 96, 0.5);">
                <span id="timer">25:00</span>
            </div>
            <script>
                var time_in_sec = 25 * 60;
                var x = setInterval(function() {
                    time_in_sec--;
                    var minutes = Math.floor(time_in_sec / 60);
                    var seconds = time_in_sec % 60;
                    if(seconds < 10) { seconds = "0" + seconds; }
                    document.getElementById("timer").innerHTML = minutes + ":" + seconds;
                    if (time_in_sec < 0) {
                        clearInterval(x);
                        document.getElementById("timer").innerHTML = "DONE!";
                        document.getElementById("timer").style.color = "#4CAF50";
                    }
                }, 1000);
            </script>
            """, height=200)

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
