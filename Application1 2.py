import streamlit as st
import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
import random

# ----------------------------- CONFIG -----------------------------
TENANT_ID = "talos"
AUTH_TOKEN = None
HEADERS_BASE = {"Content-Type": "application/json"}

# Customer-Industry Mapping
CUSTOMER_INDUSTRY_MAP = {
    "Abbive": "Pharma",
    "BMS": "Pharma", 
    "BLR Airport": "Logistics",
    "Chevron": "Energy",
    "Coles": "Retail",
    "DELL": "Technology",
    "Microsoft": "Technology",
    "Mu Labs": "Technology",
    "Nike": "Consumer Goods",
    "Skill Development": "Education",
    "Southwest Airlines": "Airlines",
    "THD": "Retail",
    "Tmobile": "Technology",
    "Walmart": "Retail"
}

ACCOUNTS = ["Select Customer"] + list(CUSTOMER_INDUSTRY_MAP.keys())
INDUSTRIES = ["Select Industry"] + list(set(CUSTOMER_INDUSTRY_MAP.values()))

API_CONFIGS = [
    {
        "name": "vocabulary",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758548233201&level=1",
        "multiround_convo": 3,
        "description": "Extract Vocabulary",
        "prompt": lambda problem, outputs: f"{problem}\n\nExtract the vocabulary from this problem statement."
    },
    {
        "name": "current_system",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758549095254&level=1",
        "multiround_convo": 2,
        "description": "Describe Current System",
        "prompt": lambda problem, outputs: f"Problem statement - {problem}\n\nContext from vocabulary:\n{outputs.get('vocabulary','')}\n\nDescribe the current system, inputs, outputs, and pain points."
    },
    {
        "name": "Q1",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758555344231&level=1",
        "multiround_convo": 2,
        "description": "Q1. What is the frequency and pace of change in the key inputs driving the business?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q1. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q2",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758549615986&level=1",
        "multiround_convo": 2,
        "description": "Q2. To what extent are these changes cyclical and predictable versus sporadic and unpredictable?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q2. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q3",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758614550482&level=1",
        "multiround_convo": 2,
        "description": "Q3. How resilient is the current system in absorbing these changes without requiring significant rework or disruption?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q3. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q4",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758614809984&level=1",
        "multiround_convo": 2,
        "description": "Q4. To what extent do stakeholders share a common understanding of the key terms and concepts?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q4. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q5",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758615038050&level=1",
        "multiround_convo": 2,
        "description": "Q5. Are there any conflicting definitions or interpretations that could create confusion?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q5. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q6",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758615386880&level=1",
        "multiround_convo": 2,
        "description": "Q6. Are objectives, priorities, and constraints clearly communicated and well-defined?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q6. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q7",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758615778653&level=1",
        "multiround_convo": 2,
        "description": "Q7. To what extent are key inputs interdependent?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q7. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q8",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758616081630&level=1",
        "multiround_convo": 2,
        "description": "Q8. How well are the governing rules, functions, and relationships between inputs understood?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q8. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q9",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758616793510&level=1",
        "multiround_convo": 2,
        "description": "Q9. Are there any hidden or latent dependencies that could impact outcomes?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q9. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q10",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758617140479&level=1",
        "multiround_convo": 2,
        "description": "Q10. Are there hidden or latent dependencies that could affect outcomes?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q10. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q11",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758618137301&level=1",
        "multiround_convo": 2,
        "description": "Q11. Are feedback loops insufficient or missing, limiting our ability to adapt?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q11. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "Q12",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758619317968&level=1",
        "multiround_convo": 2,
        "description": "Q12. Do we lack established benchmarks or 'gold standards' to validate results?",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\nContext from Current System:\n{outputs.get('current_system','')}\n\n"
            "Q12. Provide detailed analysis, score 0–5, and justification."
        )
    },
    {
        "name": "hardness_summary",
        "url": "https://eoc.mu-sigma.com/talos-engine/agency/reasoning_api?society_id=1757657318406&agency_id=1758619658634&level=1",
        "multiround_convo": 2,
        "description": "Hardness Level, Summary & Key Takeaways",
        "prompt": lambda problem, outputs: (
            f"Problem statement - {problem}\n\n"
            "Context from all previous analysis:\n"
            f"Current System:\n{outputs.get('current_system','')}\n"
            f"Q1:\n{outputs.get('Q1','')}\n"
            f"Q2:\n{outputs.get('Q2','')}\n"
            f"Q3:\n{outputs.get('Q3','')}\n"
            f"Q4:\n{outputs.get('Q4','')}\n"
            f"Q5:\n{outputs.get('Q5','')}\n"
            f"Q6:\n{outputs.get('Q6','')}\n"
            f"Q7:\n{outputs.get('Q7','')}\n"
            f"Q8:\n{outputs.get('Q8','')}\n"
            f"Q9:\n{outputs.get('Q9','')}\n"
            f"Q10:\n{outputs.get('Q10','')}\n"
            f"Q11:\n{outputs.get('Q11','')}\n"
            f"Q12:\n{outputs.get('Q12','')}\n\n"
            "Provide Hardness Score, Level, Summary & Key Takeaways."
        )
    }
]

# VUIA Dimension to Questions Mapping
VUIA_MAPPING = {
    "Volatility": ["Q1", "Q2", "Q3"],
    "Ambiguity": ["Q4", "Q5", "Q6"],
    "Interconnectedness": ["Q7", "Q8", "Q9"],
    "Uncertainty": ["Q10", "Q11", "Q12"]
}

# ----------------------------- UTILITY FUNCTIONS -----------------------------
def json_to_text(data):
    """Convert JSON response to readable text"""
    if data is None: 
        return ""
    if isinstance(data, str): 
        return data
    if isinstance(data, dict):
        for key in ("result", "output", "content", "text"):
            if key in data and data[key]:
                return json_to_text(data[key])
        if "data" in data: 
            return json_to_text(data["data"])
        return "\n".join(f"{k}: {json_to_text(v)}" for k, v in data.items() if v)
    if isinstance(data, list): 
        return "\n".join(json_to_text(x) for x in data if x)
    return str(data)

def clean_output(text):
    """
    Remove Markdown headers like ###, ##, # and leading/trailing whitespace
    """
    if not text:
        return ""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.strip()

def call_api(api_cfg, problem_text, outputs, tenant_id=TENANT_ID, auth_token=AUTH_TOKEN, tries=3):
    """Calls the API with retry logic - CORRECTED VERSION"""
    prompt = api_cfg["prompt"](problem_text, outputs)
    
    headers_list = []
    base = HEADERS_BASE.copy()
    if tenant_id:
        headers_list = [
            dict(base, **{"Tenant-ID": tenant_id}), 
            dict(base, **{"X-Tenant-ID": tenant_id})
        ]
    else:
        headers_list = [base]
    if auth_token:
        headers_list = [dict(h, **{"Authorization": f"Bearer {auth_token}"}) for h in headers_list]

    last_err = None
    for attempt in range(1, tries + 1):
        for headers in headers_list:
            try:
                # CORRECT PAYLOAD STRUCTURE
                payload = {
                    "agency_goal": prompt,  # This is the key fix!
                    "multiround_convo": api_cfg.get("multiround_convo", 1),
                    "user_id": "talos-rest-endpoint"
                }
                
                resp = requests.post(api_cfg["url"], headers=headers, json=payload, timeout=60)
                
                if resp.status_code == 200:
                    res = json_to_text(resp.json())
                    # Handle multiround conversation if needed
                    for r in range(1, api_cfg.get("multiround_convo", 1)):
                        # For subsequent rounds, use the previous response as the prompt
                        next_payload = {
                            "agency_goal": res,
                            "multiround_convo": 1,
                            "user_id": "talos-rest-endpoint"
                        }
                        resp2 = requests.post(api_cfg["url"], headers=headers, json=next_payload, timeout=60)
                        if resp2.status_code == 200:
                            res = json_to_text(resp2.json())
                    return res
                else:
                    last_err = f"{resp.status_code}-{resp.text}"
            except Exception as e:
                last_err = str(e)
        time.sleep(1 + attempt * 0.5)
    return f"API failed after {tries} attempts. Last error: {last_err}"

def extract_difficulty_score(text):
    """Extract overall difficulty score from text (0-5 scale) - prioritize calculated score"""
    # First, try to find the calculated overall score from the comprehensive summary
    calculated_patterns = [
        r"Overall Difficulty Score\s*=\s*[\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\s*\/\s*4\s*=\s*(\d+\.\d+)",
        r"Overall.*?Score.*?=\s*\([\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\)\s*\/\s*4\s*=\s*(\d+\.\d+)",
        r"Overall Difficulty Score.*?=\s*(\d+\.\d+)",
        r"≈\s*(\d+\.\d+)",  # The approximate symbol in "≈ 3.67"
        r"Overall.*?Score.*?(\d+\.\d+)\s*\(.*?\)",  # "3.67 (Moderate)"
    ]
    
    for pattern in calculated_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                return min(5, max(0, score))
            except ValueError:
                continue
    
    # Fallback to other patterns if calculated score not found
    patterns = [
        r"Overall Difficulty Score.*?=.*?(\d+\.\d+)",
        r"Overall.*?Difficulty.*?Score.*?(\d+\.\d+)",
        r"difficulty score.*?(\d+\.\d+)",
        r"Score.*?(\d+\.\d+)\s*\/\s*5",
        r"(\d+\.\d+)\s*out of\s*5",
        r"Hardness[:\s]*(\d+(?:\.\d+)?)",
        r"Overall.*?Score.*?(\d+\.\d+)",
        r"Difficulty[:\s]*(\d+\.\d+)",
        r"Final Score[:\s]*(\d+\.\d+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                return min(5, max(0, score))
            except ValueError:
                continue
    
    # If no score found, calculate from dimension scores
    dimension_scores = extract_dimension_scores(text)
    if any(score > 0 for score in dimension_scores.values()):
        overall_score = sum(dimension_scores.values()) / len(dimension_scores)
        return min(5, max(0, overall_score))
    
    return 0.0

def extract_dimension_scores(text):
    """Extract VUIA dimension scores from the analysis text with decimal support"""
    scores = {
        "Volatility": 0.0,
        "Ambiguity": 0.0, 
        "Interconnectedness": 0.0,
        "Uncertainty": 0.0
    }
    
    # First try to extract calculated averages
    avg_patterns = {
        "Volatility": [
            r"Avg Volatility\s*=\s*\([\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\)\s*\/\s*3\s*=\s*(\d+\.\d+)",
            r"Avg.*?Volatility.*?=\s*(\d+\.\d+)",
            r"Volatility.*?average.*?(\d+\.\d+)"
        ],
        "Ambiguity": [
            r"Avg Ambiguity\s*=\s*\([\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\)\s*\/\s*3\s*=\s*(\d+\.\d+)",
            r"Avg.*?Ambiguity.*?=\s*(\d+\.\d+)",
            r"Ambiguity.*?average.*?(\d+\.\d+)"
        ],
        "Interconnectedness": [
            r"Avg Interconnectedness\s*=\s*\([\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\)\s*\/\s*3\s*=\s*(\d+\.\d+)",
            r"Avg.*?Interconnectedness.*?=\s*(\d+\.\d+)",
            r"Interconnectedness.*?average.*?(\d+\.\d+)"
        ],
        "Uncertainty": [
            r"Avg Uncertainty\s*=\s*\([\d\.]+\s*\+\s*[\d\.]+\s*\+\s*[\d\.]+\)\s*\/\s*3\s*=\s*(\d+\.\d+)",
            r"Avg.*?Uncertainty.*?=\s*(\d+\.\d+)",
            r"Uncertainty.*?average.*?(\d+\.\d+)"
        ]
    }
    
    # Try to get calculated averages first
    for dimension, pattern_list in avg_patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    scores[dimension] = score
                    break
                except ValueError:
                    continue
    
    # If we didn't get all averages, fall back to individual dimension patterns
    if not all(scores.values()):
        individual_patterns = {
            "Volatility": [
                r"Volatility\s*\(V\):\s*(\d+\.\d+)",
                r"Volatility.*?[Vv]:\s*(\d+\.\d+)",
                r"Volatility.*?(\d+\.\d+)",
                r"V:\s*(\d+\.\d+)"
            ],
            "Ambiguity": [
                r"Ambiguity\s*\(A\):\s*(\d+\.\d+)",
                r"Ambiguity.*?[Aa]:\s*(\d+\.\d+)",
                r"Ambiguity.*?(\d+\.\d+)",
                r"A:\s*(\d+\.\d+)"
            ],
            "Interconnectedness": [
                r"Interconnectedness\s*\(I\):\s*(\d+\.\d+)",
                r"Interconnectedness.*?[Ii]:\s*(\d+\.\d+)",
                r"Interconnectedness.*?(\d+\.\d+)",
                r"I:\s*(\d+\.\d+)"
            ],
            "Uncertainty": [
                r"Uncertainty\s*\(U\):\s*(\d+\.\d+)",
                r"Uncertainty.*?[Uu]:\s*(\d+\.\d+)",
                r"Uncertainty.*?(\d+\.\d+)",
                r"U:\s*(\d+\.\d+)"
            ]
        }
        
        for dimension, pattern_list in individual_patterns.items():
            if scores[dimension] == 0.0:  # Only if we didn't get it from averages
                for pattern in pattern_list:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        try:
                            score = float(match.group(1))
                            scores[dimension] = score
                            break
                        except ValueError:
                            continue
    
    return scores

def extract_individual_scores(text):
    """Extract individual question scores from the analysis text"""
    scores = {}
    for i in range(1, 13):
        patterns = [
            rf"Q{i}.*?[Ss]core.*?(\d+\.\d+)",
            rf"Question {i}.*?[Ss]core.*?(\d+\.\d+)",
            rf"Score.*?Q{i}.*?(\d+\.\d+)",
            rf"Q{i}.*?(\d+\.\d+)\s*\/\s*5",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    scores[f"Q{i}"] = float(match.group(1))  # Return exact decimal without rounding
                    break
                except ValueError:
                    continue
    return scores

def get_difficulty_level(score):
    """Get difficulty level based on the new ranges"""
    if score <= 3.0:
        return "Easy", "#4CAF50", "🟢"
    elif score <= 4.0:
        return "Moderate", "#FF9800", "🟡"
    else:
        return "Hard", "#F44336", "🔴"

def reset_application():
    """Reset all session state variables to their initial values"""
    st.session_state.outputs = {}
    st.session_state.analysis_complete = False
    st.session_state.difficulty_score = 0.0
    st.session_state.dimension_scores = {
        "Volatility": 0.0,
        "Ambiguity": 0.0,
        "Interconnectedness": 0.0,
        "Uncertainty": 0.0
    }
    st.session_state.individual_scores = {}
    st.session_state.current_page = "Page 1: Input"
    st.session_state.problem_statement = ""
    st.session_state.customer = "Select Customer"
    st.session_state.industry = "Select Industry"
    st.session_state.current_industry = "Select Industry"
    st.session_state.selected_vuia_dimension = None
    st.session_state.show_results_button = False
    st.session_state.show_vocabulary = False
    st.session_state.last_customer = ""
    st.session_state.last_problem = ""
    
    # Also clear any input-specific session states
    if 'page1_customer' in st.session_state:
        del st.session_state.page1_customer
    if 'page1_industry' in st.session_state:
        del st.session_state.page1_industry
    if 'page1_problem' in st.session_state:
        del st.session_state.page1_problem

# ----------------------------- PAGE CONFIG -----------------------------
# Create a unique favicon (brain with network connections)
favicon_svg = """
<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="brainGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#667eea"/>
            <stop offset="100%" stop-color="#764ba2"/>
        </linearGradient>
    </defs>
    <circle cx="16" cy="16" r="14" fill="url(#brainGradient)" opacity="0.9"/>
    <path d="M11 12 C11 10, 13 8, 16 8 C19 8, 21 10, 21 12 C21 14, 19 16, 16 16 C13 16, 11 14, 11 12" fill="white" opacity="0.8"/>
    <path d="M11 20 C11 18, 13 16, 16 16 C19 16, 21 18, 21 20 C21 22, 19 24, 16 24 C13 24, 11 22, 11 20" fill="white" opacity="0.8"/>
    <circle cx="14" cy="12" r="1" fill="#667eea"/>
    <circle cx="18" cy="12" r="1" fill="#667eea"/>
    <path d="M8 10 L6 8 M8 14 L6 16 M8 18 L6 20 M8 22 L6 24" stroke="white" stroke-width="1.5" opacity="0.7"/>
    <path d="M24 10 L26 8 M24 14 L26 16 M24 18 L26 20 M24 22 L26 24" stroke="white" stroke-width="1.5" opacity="0.7"/>
</svg>
"""

# Convert SVG to base64 for favicon
favicon_b64 = base64.b64encode(favicon_svg.encode('utf-8')).decode()

st.set_page_config(
    page_title="Business Problem Analyzer", 
    page_icon="💡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------- SESSION STATE -----------------------------
# Initialize all session state variables with proper default values
if 'outputs' not in st.session_state:
    st.session_state.outputs = {}
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'difficulty_score' not in st.session_state:
    st.session_state.difficulty_score = 0.0
if 'dimension_scores' not in st.session_state:
    st.session_state.dimension_scores = {
        "Volatility": 0.0,
        "Ambiguity": 0.0,
        "Interconnectedness": 0.0,
        "Uncertainty": 0.0
    }
if 'individual_scores' not in st.session_state:
    st.session_state.individual_scores = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Page 1: Input"
if 'problem_statement' not in st.session_state:
    st.session_state.problem_statement = ""
if 'customer' not in st.session_state:
    st.session_state.customer = "Select Customer"
if 'industry' not in st.session_state:
    st.session_state.industry = "Select Industry"
if 'current_industry' not in st.session_state:
    st.session_state.current_industry = "Select Industry"
if 'selected_vuia_dimension' not in st.session_state:
    st.session_state.selected_vuia_dimension = None
if 'show_results_button' not in st.session_state:
    st.session_state.show_results_button = False
if 'show_vocabulary' not in st.session_state:
    st.session_state.show_vocabulary = False
if 'last_customer' not in st.session_state:
    st.session_state.last_customer = ""
if 'last_problem' not in st.session_state:
    st.session_state.last_problem = ""

# ----------------------------- CUSTOM CSS -----------------------------
st.markdown(f"""
<style>
    /* Favicon */
    link[rel="icon"] {{
        type: image/svg+xml,
        href: "data:image/svg+xml;base64,{favicon_b64}"
    }}
    
    .main {{
        background-color: #f8f9fa;
        font-family: 'Inter', sans-serif;
    }}
    
    /* Enhanced Cards with better shadows and transitions */
    .analysis-card {{
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 6px 25px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        border-left: 5px solid #667eea;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border: 1px solid rgba(102, 126, 234, 0.1);
        backdrop-filter: blur(10px);
    }}
    
    .analysis-card:hover {{
        transform: translateY(-8px);
        box-shadow: 0 12px 40px rgba(102, 126, 234, 0.25);
        border-left: 5px solid #764ba2;
    }}
    
    .question-card {{
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin-bottom: 15px;
        border-left: 4px solid;
        transition: all 0.3s ease;
        border: 1px solid rgba(0,0,0,0.05);
        position: relative;
        overflow: hidden;
    }}
    
    .question-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.1), transparent);
        transition: left 0.5s ease;
    }}
    
    .question-card:hover::before {{
        left: 100%;
    }}
    
    .question-card:hover {{
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 8px 30px rgba(0,0,0,0.15);
    }}
    
    .score-badge {{
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 8px 16px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 0.9rem;
        display: inline-block;
        margin-left: 10px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
    }}
    
    .score-badge:hover {{
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }}
    
    /* Problem Display Card */
    .problem-display-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px;
        border-radius: 20px;
        margin: 20px 0;
        box-shadow: 0 12px 35px rgba(102, 126, 234, 0.4);
        border: 2px solid rgba(255,255,255,0.3);
        transition: all 0.4s ease;
        position: relative;
        overflow: hidden;
    }}
    
    .problem-display-card::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        transform: rotate(30deg);
        transition: all 0.6s ease;
    }}
    
    .problem-display-card:hover::before {{
        transform: rotate(45deg) scale(1.1);
    }}
    
    .problem-display-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 15px 45px rgba(102, 126, 234, 0.5);
    }}
    
    /* Enhanced Dimension Cards */
    .dimension-card {{
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        margin: 15px;
        text-align: center;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border-top: 5px solid;
        cursor: pointer;
        border: 1px solid rgba(0,0,0,0.05);
        position: relative;
        overflow: hidden;
    }}
    
    .dimension-card::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 0;
        background: linear-gradient(transparent, rgba(0,0,0,0.03));
        transition: height 0.3s ease;
    }}
    
    .dimension-card:hover::after {{
        height: 100%;
    }}
    
    .dimension-card:hover {{
        transform: translateY(-12px) scale(1.03);
        box-shadow: 0 15px 45px rgba(0,0,0,0.2);
    }}
    
    .dimension-card.selected {{
        transform: scale(1.05);
        box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        border: 3px solid;
        animation: pulse-glow 2s infinite;
    }}
    
    @keyframes pulse-glow {{
        0% {{ box-shadow: 0 0 20px rgba(102, 126, 234, 0.3); }}
        50% {{ box-shadow: 0 0 30px rgba(102, 126, 234, 0.6); }}
        100% {{ box-shadow: 0 0 20px rgba(102, 126, 234, 0.3); }}
    }}
    
    .volatility-card {{ 
        border-color: #ff6b6b;
        background: linear-gradient(135deg, #fff, #fff5f5);
    }}
    .ambiguity-card {{ 
        border-color: #4ecdc4;
        background: linear-gradient(135deg, #fff, #f0fffd);
    }}
    .interconnectedness-card {{ 
        border-color: #45b7d1;
        background: linear-gradient(135deg, #fff, #f0f9ff);
    }}
    .uncertainty-card {{ 
        border-color: #96ceb4;
        background: linear-gradient(135deg, #fff, #f7fff9);
    }}
    
    /* Enhanced Score Circles */
    .score-circle {{
        width: 90px;
        height: 90px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 15px;
        font-size: 2rem;
        font-weight: bold;
        color: white;
        box-shadow: 0 8px 25px rgba(0,0,0,0.2);
        transition: all 0.4s ease;
        position: relative;
        overflow: hidden;
    }}
    
    .score-circle::before {{
        content: '';
        position: absolute;
        top: -10px;
        left: -10px;
        right: -10px;
        bottom: -10px;
        background: inherit;
        filter: blur(15px);
        opacity: 0.6;
        z-index: -1;
    }}
    
    .score-circle:hover {{
        transform: scale(1.1) rotate(5deg);
        box-shadow: 0 12px 35px rgba(0,0,0,0.3);
    }}
    
    .volatility-score {{ 
        background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
    }}
    .ambiguity-score {{ 
        background: linear-gradient(135deg, #4ecdc4, #6de0d7);
    }}
    .interconnectedness-score {{ 
        background: linear-gradient(135deg, #45b7d1, #67c9e0);
    }}
    .uncertainty-score {{ 
        background: linear-gradient(135deg, #96ceb4, #b4e0c8);
    }}
    
    /* Enhanced Difficulty Card */
    .difficulty-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 40px;
        border-radius: 25px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        border: 3px solid rgba(255,255,255,0.2);
        transition: all 0.5s ease;
        position: relative;
        overflow: hidden;
    }}
    
    .difficulty-card::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
        transform: rotate(45deg);
        transition: all 0.6s ease;
    }}
    
    .difficulty-card:hover::before {{
        transform: rotate(45deg) translate(20px, 20px);
    }}
    
    .difficulty-card:hover {{
        transform: translateY(-8px);
        box-shadow: 0 20px 50px rgba(102, 126, 234, 0.6);
    }}
    
    /* Enhanced Progress Bars */
    .progress-container {{
        background: #f1f3f4;
        border-radius: 15px;
        height: 15px;
        margin: 15px 0;
        overflow: hidden;
        box-shadow: inset 0 2px 8px rgba(0,0,0,0.1);
    }}
    
    .progress-bar {{
        height: 100%;
        border-radius: 15px;
        transition: width 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        background: linear-gradient(90deg, #667eea, #764ba2);
        position: relative;
        overflow: hidden;
    }}
    
    .progress-bar::after {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        animation: shimmer 2s infinite;
    }}
    
    @keyframes shimmer {{
        0% {{ left: -100%; }}
        100% {{ left: 100%; }}
    }}
    
    /* Enhanced Navigation Buttons */
    .nav-button {{
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 14px 28px;
        border-radius: 15px;
        cursor: pointer;
        margin: 12px 8px;
        font-weight: 600;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
        font-size: 1rem;
    }}
    
    .nav-button::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s ease;
    }}
    
    .nav-button:hover::before {{
        left: 100%;
    }}
    
    .nav-button:hover {{
        transform: translateY(-5px) scale(1.05);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
    }}
    
    .nav-button:active {{
        transform: translateY(-2px) scale(1.02);
    }}
    
    /* Enhanced Feature Cards */
    .feature-card {{
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.1);
        margin: 15px 0;
        transition: all 0.4s ease;
        border: 1px solid rgba(102, 126, 234, 0.1);
        text-align: center;
        position: relative;
        overflow: hidden;
    }}
    
    .feature-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        transform: scaleX(0);
        transition: transform 0.4s ease;
    }}
    
    .feature-card:hover::before {{
        transform: scaleX(1);
    }}
    
    .feature-card:hover {{
        transform: translateY(-10px);
        box-shadow: 0 15px 45px rgba(102, 126, 234, 0.2);
    }}
    
    /* Summary Cards */
    .summary-card {{
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.1);
        margin: 20px 0;
        transition: all 0.4s ease;
        border-left: 5px solid;
        border-top: 1px solid rgba(0,0,0,0.05);
    }}
    
    .summary-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.15);
    }}
    
    .executive-summary {{ border-left-color: #667eea; }}
    
    /* Enhanced Select Boxes */
    .stSelectbox > div > div {{
        transition: all 0.3s ease;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }}
    
    .stSelectbox > div > div:hover {{
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.15);
        transform: translateY(-2px);
    }}
    
    /* Enhanced Text Areas */
    .stTextArea > div > div {{
        transition: all 0.3s ease;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }}
    
    .stTextArea > div > div:hover {{
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.15);
        transform: translateY(-2px);
    }}
    
    /* Enhanced Metrics */
    .stMetric {{
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        border-left: 4px solid #667eea;
    }}
    
    .stMetric:hover {{
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.15);
    }}
    
    /* Sidebar Enhancements */
    .css-1d391kg {{
        background: linear-gradient(135deg, #2c3e50, #34495e);
    }}
    
    .sidebar .sidebar-content {{
        background: linear-gradient(135deg, #2c3e50, #34495e);
    }}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: #f1f1f1;
        border-radius: 10px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 10px;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(135deg, #764ba2, #667eea);
    }}
</style>
""", unsafe_allow_html=True)

# ----------------------------- PAGE 1: INPUT -----------------------------
def render_page_1():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); padding: 40px; 
                border-radius: 15px; margin-bottom: 40px; box-shadow: 0 8px 25px rgba(13, 148, 136, 0.3);">
        <div style="text-align: center;">
            <h1 style="background: linear-gradient(45deg, #ffffff, #e0f2fe); -webkit-background-clip: text; 
                   -webkit-text-fill-color: transparent; font-size: 2.8rem; font-weight: 800; margin: 0; 
                   text-shadow: 0 4px 15px rgba(0,0,0,0.2); letter-spacing: 1px;">
                Business Problem Analyzer
            </h1>
            <p style="color: rgba(255,255,255,0.95); font-size: 1.2rem; margin: 15px 0 0 0; 
                      font-weight: 300; letter-spacing: 2px; text-transform: uppercase;">
                STRATEGIC COMPLEXITY ASSESSMENT
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style= box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 40px; border: 1px solid #e0e0e0; display: flex; justify-content: center; align-items: center; min-height: 80px;">
        <h2 style="color: #333; margin: 0; font-weight: 600;">Define Your Business Challenge</h2>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.problem_statement:
        st.markdown(f"""
        <div class="problem-display-card">
            <h4 style="color: white; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="margin-right: 10px; font-size: 1.5rem;">📝</span> Current Business Problem
            </h4>
            <div style="background: rgba(255,255,255,0.15); padding: 20px; border-radius: 15px; border-left: 4px solid rgba(255,255,255,0.4); backdrop-filter: blur(10px);">
                <p style="color: white; margin: 0; line-height: 1.6; font-size: 15px; font-weight: 500;">{st.session_state.problem_statement}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        # Use session state directly for customer selection
        customer = st.selectbox("🏢 Select Customer", ACCOUNTS, 
                               index=ACCOUNTS.index(st.session_state.customer) if st.session_state.customer in ACCOUNTS else 0,
                               key="customer_select")
        
        if customer != "Select Customer":
            auto_industry = CUSTOMER_INDUSTRY_MAP.get(customer, "Select Industry")
            st.session_state.current_industry = auto_industry
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #e8f5e8, #d4edda); border: 2px solid #4CAF50; border-radius: 15px; padding: 20px; margin: 15px 0; color: #2e7d32; font-weight: 600; box-shadow: 0 6px 20px rgba(76, 175, 80, 0.2); transition: all 0.3s ease;">
                🏭 Industry: <strong style="font-size: 1.1em;">{auto_industry}</strong>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.session_state.current_industry = "Select Industry"
    
    with col2:
        if customer != "Select Customer":
            st.markdown(f"""
            <div style="margin-bottom: 20px;">
                <label style="font-weight: 700; color: #333; font-size: 1.1em;">🏭 Industry</label>
                <div style="padding: 16px; background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-radius: 12px; border: 2px solid #dee2e6; color: #495057; font-weight: 600; box-shadow: 0 4px 15px rgba(0,0,0,0.08);">
                    {st.session_state.current_industry}
                </div>
            </div>
            """, unsafe_allow_html=True)
            industry = st.session_state.current_industry
        else:
            # Use session state directly for industry selection
            industry = st.selectbox("🏭 Select Industry", INDUSTRIES, 
                                   index=INDUSTRIES.index(st.session_state.industry) if st.session_state.industry in INDUSTRIES else 0,
                                   key="industry_select")
            st.session_state.current_industry = industry
    
    # Update session state with current selections
    st.session_state.customer = customer
    st.session_state.industry = st.session_state.current_industry
    
    # Check if we need to reset analysis (only if customer or problem actually changed)
    current_customer = st.session_state.customer
    current_problem = st.session_state.problem_statement
    
    if (current_customer != st.session_state.last_customer or 
        current_problem != st.session_state.last_problem):
        st.session_state.analysis_complete = False
        st.session_state.outputs = {}
        st.session_state.show_vocabulary = False
        st.session_state.show_results_button = False
        st.session_state.last_customer = current_customer
        st.session_state.last_problem = current_problem
    
    # Use session state directly for problem statement
    problem = st.text_area(
        "💬 Describe the Business Problem",
        value=st.session_state.problem_statement,
        height=200,
        placeholder="Describe your business challenge in detail...",
        key="problem_text_area"
    )
    
    # Update problem statement in session state
    if problem != st.session_state.problem_statement:
        st.session_state.problem_statement = problem
        # Trigger re-run to update the reset logic
        if st.session_state.analysis_complete:
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Enhanced Analyze Button
    if st.button("🚀 Analyze Business Problem", use_container_width=True, type="primary"):
        if customer == "Select Customer" or not problem.strip():
            st.warning("⚠️ Please select a customer and enter a detailed problem statement.")
        else:
            st.session_state.customer = customer
            st.session_state.industry = st.session_state.current_industry
            st.session_state.problem = problem
            
            run_analysis(problem)
            
            # Show results button instead of auto-redirecting
            st.session_state.show_results_button = True
            st.rerun()
    
    # Show View Results button if analysis is complete and we're on page 1
    if st.session_state.analysis_complete and st.session_state.show_results_button:
        st.markdown("---")
        st.markdown("### 📊 Analysis Complete!")
        st.success("✅ Your business problem has been analyzed successfully!")
        
        # Display Overall Difficulty Score and VUIA Scores in 2x2 grid
        score = st.session_state.difficulty_score
        difficulty_level, level_color, level_emoji = get_difficulty_level(score)
        
        # Overall Difficulty Score Card
        st.markdown(f"""
        <div class="difficulty-card">
            <h2 style="margin: 0; font-size: 4rem; font-weight: 800; text-shadow: 0 4px 8px rgba(0,0,0,0.2);">{score:.2f}<span style="font-size: 2rem; opacity: 0.8;">/5</span></h2>
            <p style="margin: 15px 0; font-size: 1.3rem; font-weight: 600;">Overall Difficulty Score</p>
            <div style="margin: 25px 0;">
                <span style="font-size: 1.4rem; font-weight: bold; color: {level_color}; padding: 12px 24px; background: rgba(255,255,255,0.2); border-radius: 25px; backdrop-filter: blur(10px); border: 2px solid rgba(255,255,255,0.3);">
                    {level_emoji} {difficulty_level}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Rest of your VUIA cards and buttons...
        # [Your existing VUIA cards code here]
        
        # 🎯 VUIA Scores in 2x2 Grid - UNDER THE OVERALL SCORE
        st.markdown("### 🎯 VUIA Dimension Scores")
        
        # Create 2x2 grid for VUIA scores
        col1, col2 = st.columns(2)
        
        with col1:
            # Volatility Score
            volatility_score = st.session_state.dimension_scores["Volatility"]
            volatility_level, volatility_color, volatility_emoji = get_difficulty_level(volatility_score)
            st.markdown(f"""
            <div class="dimension-card volatility-card" style="text-align: center; padding: 25px; margin: 10px 0;">
                <div class="score-circle volatility-score">{volatility_score:.2f}</div>
                <h3 style="margin: 15px 0 10px 0; color: #333;">🌪️ Volatility</h3>
                <p style="margin: 5px 0; color: #666; font-size: 0.9rem;">Change frequency & pace</p>
                <div style="margin-top: 10px;">
                    <span style="color: {volatility_color}; font-weight: 600; font-size: 1.1rem;">
                        {volatility_emoji} {volatility_level}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Uncertainty Score
            uncertainty_score = st.session_state.dimension_scores["Uncertainty"]
            uncertainty_level, uncertainty_color, uncertainty_emoji = get_difficulty_level(uncertainty_score)
            st.markdown(f"""
            <div class="dimension-card uncertainty-card" style="text-align: center; padding: 25px; margin: 10px 0;">
                <div class="score-circle uncertainty-score">{uncertainty_score:.2f}</div>
                <h3 style="margin: 15px 0 10px 0; color: #333;">❓ Uncertainty</h3>
                <p style="margin: 5px 0; color: #666; font-size: 0.9rem;">Predictability & patterns</p>
                <div style="margin-top: 10px;">
                    <span style="color: {uncertainty_color}; font-weight: 600; font-size: 1.1rem;">
                        {uncertainty_emoji} {uncertainty_level}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Interconnectedness Score
            interconnectedness_score = st.session_state.dimension_scores["Interconnectedness"]
            interconnectedness_level, interconnectedness_color, interconnectedness_emoji = get_difficulty_level(interconnectedness_score)
            st.markdown(f"""
            <div class="dimension-card interconnectedness-card" style="text-align: center; padding: 25px; margin: 10px 0;">
                <div class="score-circle interconnectedness-score">{interconnectedness_score:.2f}</div>
                <h3 style="margin: 15px 0 10px 0; color: #333;">🕸️ Interconnectedness</h3>
                <p style="margin: 5px 0; color: #666; font-size: 0.9rem;">System dependencies</p>
                <div style="margin-top: 10px;">
                    <span style="color: {interconnectedness_color}; font-weight: 600; font-size: 1.1rem;">
                        {interconnectedness_emoji} {interconnectedness_level}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Ambiguity Score
            ambiguity_score = st.session_state.dimension_scores["Ambiguity"]
            ambiguity_level, ambiguity_color, ambiguity_emoji = get_difficulty_level(ambiguity_score)
            st.markdown(f"""
            <div class="dimension-card ambiguity-card" style="text-align: center; padding: 25px; margin: 10px 0;">
                <div class="score-circle ambiguity-score">{ambiguity_score:.2f}</div>
                <h3 style="margin: 15px 0 10px 0; color: #333;">🎭 Ambiguity</h3>
                <p style="margin: 5px 0; color: #666; font-size: 0.9rem;">Clarity & definitions</p>
                <div style="margin-top: 10px;">
                    <span style="color: {ambiguity_color}; font-weight: 600; font-size: 1.1rem;">
                        {ambiguity_emoji} {ambiguity_level}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Vocabulary Button - Toggle functionality
        col1, col2 = st.columns([1, 1])
        with col1:
            # Show different button text based on current state
            if st.session_state.show_vocabulary:
                button_text = "🔒 Hide Vocabulary"
                button_help = "Hide the extracted vocabulary"
            else:
                button_text = "📚 Show Vocabulary"
                button_help = "View the extracted vocabulary from your problem statement"
            
            if st.button(button_text, key="toggle_vocab_btn", use_container_width=True, 
                        disabled=not st.session_state.analysis_complete,
                        help=button_help):
                # Toggle the vocabulary display state
                st.session_state.show_vocabulary = not st.session_state.show_vocabulary
                st.rerun()
        
        # Show vocabulary section if toggled and analysis is complete
        if st.session_state.show_vocabulary and st.session_state.outputs.get("vocabulary"):
            st.markdown("### 📚 Extracted Vocabulary")
            st.markdown(f"""
            <div class="analysis-card" style="background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-left: 5px solid #667eea; animation: fadeIn 0.5s ease-in;">
                <div style="color: #555; line-height: 1.6; font-size: 15px;">
                    {st.session_state.outputs["vocabulary"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # View Results Button
        if st.button("📊 View Detailed Analysis", use_container_width=True, type="secondary"):
            st.session_state.current_page = "Page 2: Analysis"
            st.session_state.show_results_button = False
            st.rerun()
# ----------------------------- PAGE 2: ANALYSIS -----------------------------
def render_page_2():
    st.title("📊 Analysis Results")
    
    if not st.session_state.analysis_complete:
        st.warning("No analysis completed yet. Please go to Page 1 to start an analysis.")
        return
    
    if st.session_state.problem_statement:
        st.markdown(f"""
        <div class="problem-display-card">
            <h4 style="color: white; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="margin-right: 10px; font-size: 1.5rem;">🎯</span> Business Problem Statement - {st.session_state.customer}
            </h4>
            <div style="background: rgba(255,255,255,0.15); padding: 20px; border-radius: 15px; border-left: 4px solid rgba(255,255,255,0.4); backdrop-filter: blur(10px);">
                <p style="color: white; margin: 0; line-height: 1.6; font-size: 15px; font-weight: 500;">{st.session_state.problem_statement}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Enhanced Overall Difficulty Score Card
    score = st.session_state.difficulty_score
    difficulty_level, level_color, level_emoji = get_difficulty_level(score)

    st.markdown(f"""
    <div class="difficulty-card">
        <h2 style="margin: 0; font-size: 4rem; font-weight: 800; text-shadow: 0 4px 8px rgba(0,0,0,0.2);">{score:.2f}<span style="font-size: 2rem; opacity: 0.8;">/5</span></h2>
        <p style="margin: 15px 0; font-size: 1.3rem; font-weight: 600;">Overall Difficulty Score</p>
        <div style="margin: 25px 0;">
            <span style="font-size: 1.4rem; font-weight: bold; color: {level_color}; padding: 12px 24px; background: rgba(255,255,255,0.2); border-radius: 25px; backdrop-filter: blur(10px); border: 2px solid rgba(255,255,255,0.3);">
                {level_emoji} {difficulty_level}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Enhanced Problem Context
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🏢 Customer", st.session_state.customer)
    with col2:
        st.metric("🏭 Industry", st.session_state.industry)
    
    # Current System Analysis only - WITH BOLDED HEADING
    if st.session_state.outputs.get("current_system"):
        st.markdown("### 🔄 **Current System Analysis**")  # Added bold formatting
        st.markdown(f'<div class="analysis-card">{st.session_state.outputs["current_system"]}</div>', unsafe_allow_html=True)
    
    # Enhanced Navigation - WITH UNIQUE KEYS
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Back to Input", use_container_width=True, key="page2_back_to_input"):
            st.session_state.current_page = "Page 1: Input"
            st.rerun()
    with col2:
        if st.button("🔍 View VUIA Dimensions", use_container_width=True, type="secondary", key="page2_view_vuia"):
            st.session_state.current_page = "Page 3: VUIA Dimensions"
            st.rerun()
    with col3:
        if st.button("📋 View Summary ➡️", use_container_width=True, type="primary", key="page2_view_summary"):
            st.session_state.current_page = "Page 4: Summary"
            st.rerun()

def get_dimension_icon(dimension):
    """Get icon for VUIA dimension"""
    icons = {
        "Volatility": "🌪️",      
	"Ambiguity": "🎭",
	"Interconnectedness": "🕸️", 
        "Uncertainty": "❓"
    }
    return icons.get(dimension, "📊")

def display_question_details(question_key):
    """Display detailed question information without scores for ALL questions"""
    if st.session_state.outputs.get(question_key):
        # Get question description from API_CONFIGS
        q_description = ""
        for api in API_CONFIGS:
            if api['name'] == question_key:
                q_description = api['description']
                break
        
        # Get the answer text
        answer_text = st.session_state.outputs[question_key]
        
        # Remove ONLY the specific score lines and score mentions, but keep the explanations
        # More targeted score removal patterns
        score_patterns = [
            # Remove standalone score lines
            r'^Score:\s*\d+(?:\.\d+)?\s*\/\s*5\s*$',
            r'^Score\s*\(?0–5\)?\s*:\s*\d+(?:\.\d+)?\s*$',
            r'^Overall Score:\s*\d+(?:\.\d+)?\s*$',
            r'^Rating:\s*\d+(?:\.\d+)?\s*$',
            r'^\d+(?:\.\d+)?\s*out of\s*5\s*$',
            r'^\d+(?:\.\d+)?\s*\/\s*5\s*$',
            
            # Remove score mentions at the end of paragraphs but preserve content before them
            r'\s*Score:\s*\d+(?:\.\d+)?\s*\/\s*5\s*$',
            r'\s*Score\s*\(?0–5\)?\s*:\s*\d+(?:\.\d+)?\s*$',
            r'\s*Overall Score:\s*\d+(?:\.\d+)?\s*$',
            
            # Remove parenthetical scores
            r'\(\s*Score:\s*\d+(?:\.\d+)?\s*\/\s*5\s*\)',
            r'\(\s*\d+(?:\.\d+)?\s*\/\s*5\s*\)',
            r'\[\s*\d+(?:\.\d+)?\s*\/\s*5\s*\]',
        ]
        
        # Apply score removal patterns
        for pattern in score_patterns:
            answer_text = re.sub(pattern, '', answer_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove "Justification" sections that only contain score information
        # But keep justifications that have actual content
        justification_patterns = [
            r'Justification:\s*(?:The\s+)?score\s+(?:of\s+)?\d+(?:\.\d+)?.*?(?=\n\n|\n[A-Z]|$)',
            r'Justification:\s*(?:This\s+)?(?:results?\s+in\s+a\s+)?score\s+of\s+\d+(?:\.\d+)?.*?(?=\n\n|\n[A-Z]|$)',
            r'Justification:\s*\d+(?:\.\d+)?.*?(?=\n\n|\n[A-Z]|$)',
        ]
        
        for pattern in justification_patterns:
            answer_text = re.sub(pattern, '', answer_text, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up any resulting double newlines or empty lines
        answer_text = re.sub(r'\n\s*\n', '\n\n', answer_text)
        answer_text = answer_text.strip()
        
        # If the answer text became empty after removing scores, show a message
        if not answer_text.strip():
            answer_text = "No detailed explanation available beyond the score assessment."
        
        # Process the answer to make explanations bold (for all questions)
        patterns_to_bold = [
            r'(Explanation:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Analysis:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Key Findings:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Summary:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Conclusion:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Recommendation:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Justification:.*?)(?=\n\n|\n[A-Z]|$)',
            r'(Rationale:.*?)(?=\n\n|\n[A-Z]|$)',
        ]
        
        # Apply bolding to explanation sections
        for pattern in patterns_to_bold:
            matches = list(re.finditer(pattern, answer_text, re.IGNORECASE | re.DOTALL))
            for match in reversed(matches):  # Process in reverse to avoid position issues
                start, end = match.span()
                section_text = match.group(1)
                # Only bold if the section has meaningful content beyond just score mentions
                if len(section_text.strip()) > 20:  # Minimum content length
                    bolded_section = f"**{section_text}**"
                    answer_text = answer_text[:start] + bolded_section + answer_text[end:]
        
        # Also bold common section headers
        section_headers = [
            'Explanation', 'Analysis', 'Key Findings', 'Summary', 
            'Conclusion', 'Recommendation', 'Justification', 'Rationale'
        ]
        
        for header in section_headers:
            answer_text = re.sub(
                rf'({header}:)',
                r'**\1**',
                answer_text,
                flags=re.IGNORECASE
            )
        
        st.markdown(f"""
        <div class="question-card">
            <h4 style="margin: 0 0 15px 0; color: #333; font-weight: 700;">{q_description}</h4>
            <div style="color: #555; line-height: 1.6; background: linear-gradient(135deg, #f8f9fa, #ffffff); padding: 20px; border-radius: 12px; border-left: 4px solid #667eea; box-shadow: inset 0 2px 10px rgba(0,0,0,0.05);">
        """, unsafe_allow_html=True)
        
        # Use markdown to render the bold text properly
        st.markdown(answer_text)
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)

def extract_score_from_answer_text(text):
    """Extract score specifically from the answer text using targeted patterns"""
    # More specific patterns to find scores in answer explanations
    patterns = [
        r'Score\s*\(?0–5\)?\s*:\s*(\d+(?:\.\d+)?)',  # "Score (0–5): 4"
        r'Score:\s*(\d+(?:\.\d+)?)',                 # "Score: 4"
        r'Score\s*=\s*(\d+(?:\.\d+)?)',              # "Score = 4"
        r'Overall Score:\s*(\d+(?:\.\d+)?)',         # "Overall Score: 4"
        r'Rating:\s*(\d+(?:\.\d+)?)',                # "Rating: 4"
        r'(\d+(?:\.\d+)?)\s*out of\s*5',             # "4 out of 5"
        r'(\d+(?:\.\d+)?)\s*\/\s*5',                 # "4/5"
        r'Score.*?(\d+(?:\.\d+)?)\s*\/\s*5',         # "Score 4/5"
        r'Justification.*?score of\s*(\d+(?:\.\d+)?)', # "Justification: The score of 4"
        r'score of\s*(\d+(?:\.\d+)?)',               # "score of 4"
        r'Score.*?(\d+)',                            # "Score 4"
        r'rating of\s*(\d+(?:\.\d+)?)',              # "rating of 4"
    ]
    
    # Look for all score mentions and take the most relevant one
    all_scores = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                score = float(match)
                if 0 <= score <= 5:
                    all_scores.append(score)
            except ValueError:
                continue
    
    # If we found multiple scores, use some logic to pick the right one
    if all_scores:
        # Prefer scores that appear later in the text (usually the final score)
        return f"{all_scores[-1]:.1f}"
    
    return "N/A"

def update_individual_scores_from_answers():
    """Update individual scores from the actual answer texts to ensure consistency"""
    for i in range(1, 13):
        question_key = f"Q{i}"
        if st.session_state.outputs.get(question_key):
            answer_text = st.session_state.outputs[question_key]
            extracted_score = extract_score_from_answer_text(answer_text)
            if extracted_score != "N/A":
                st.session_state.individual_scores[question_key] = float(extracted_score)

# ----------------------------- PAGE 3: VUIA DIMENSIONS -----------------------------
def render_page_3():
    st.title("🔍 VUIA Dimension Analysis")
    
    if not st.session_state.analysis_complete:
        st.warning("No analysis completed yet. Please go to Page 1 to start an analysis.")
        return
    
    if st.session_state.problem_statement:
        st.markdown(f"""
        <div class="problem-display-card">
            <h4 style="color: white; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="margin-right: 10px; font-size: 1.5rem;">🎯</span> Business Problem Statement - {st.session_state.customer}
            </h4>
            <div style="background: rgba(255,255,255,0.15); padding: 20px; border-radius: 15px; border-left: 4px solid rgba(255,255,255,0.4); backdrop-filter: blur(10px);">
                <p style="color: white; margin: 0; line-height: 1.6; font-size: 15px; font-weight: 500;">{st.session_state.problem_statement}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("### 📊 Four Dimensions of Problem Complexity")
    st.markdown("Click on any dimension card to view its detailed questions and analysis")
    
    # Enhanced VUIA Cards in 2x2 grid
    col1, col2 = st.columns(2)
    
    with col1:
        # Volatility Card
        volatility_score = st.session_state.dimension_scores["Volatility"]
        volatility_level, volatility_color, volatility_emoji = get_difficulty_level(volatility_score)
        
        if st.button(f"**🌪️ Volatility**\n\n**Score: {volatility_score:.2f}/5**\n\n*{volatility_level}*", 
                    key="volatility_btn_page3",
                    use_container_width=True,
                    help="Click to view Volatility questions (Q1-Q3)"):
            st.session_state.selected_vuia_dimension = "Volatility"
            st.rerun()
        
        # Ambiguity Card
        ambiguity_score = st.session_state.dimension_scores["Ambiguity"]
        ambiguity_level, ambiguity_color, ambiguity_emoji = get_difficulty_level(ambiguity_score)
        
        if st.button(f"**🎭 Ambiguity**\n\n**Score: {ambiguity_score:.2f}/5**\n\n*{ambiguity_level}*", 
                    key="ambiguity_btn_page3",
                    use_container_width=True,
                    help="Click to view Ambiguity questions (Q4-Q6)"):
            st.session_state.selected_vuia_dimension = "Ambiguity"
            st.rerun()
    
    with col2:
        # Interconnectedness Card
        interconnectedness_score = st.session_state.dimension_scores["Interconnectedness"]
        interconnectedness_level, interconnectedness_color, interconnectedness_emoji = get_difficulty_level(interconnectedness_score)
        
        if st.button(f"**🕸️ Interconnectedness**\n\n**Score: {interconnectedness_score:.2f}/5**\n\n*{interconnectedness_level}*", 
                    key="interconnectedness_btn_page3",
                    use_container_width=True,
                    help="Click to view Interconnectedness questions (Q7-Q9)"):
            st.session_state.selected_vuia_dimension = "Interconnectedness"
            st.rerun()
        
        # Uncertainty Card
        uncertainty_score = st.session_state.dimension_scores["Uncertainty"]
        uncertainty_level, uncertainty_color, uncertainty_emoji = get_difficulty_level(uncertainty_score)
        
        if st.button(f"**❓ Uncertainty**\n\n**Score: {uncertainty_score:.2f}/5**\n\n*{uncertainty_level}*", 
                    key="uncertainty_btn_page3",
                    use_container_width=True,
                    help="Click to view Uncertainty questions (Q10-Q12)"):
            st.session_state.selected_vuia_dimension = "Uncertainty"
            st.rerun()
    
    # Display selected dimension's questions
    if st.session_state.selected_vuia_dimension:
        st.markdown(f"---")
        st.markdown(f"### 📋 {st.session_state.selected_vuia_dimension} Questions")
        st.markdown(f"*{get_dimension_description(st.session_state.selected_vuia_dimension)}*")
        
        questions = VUIA_MAPPING[st.session_state.selected_vuia_dimension]
        for q in questions:
            display_question_details(q)
    
    # Enhanced Navigation - WITH UNIQUE KEYS
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Back to Analysis", use_container_width=True, key="page3_back_to_analysis"):
            st.session_state.current_page = "Page 2: Analysis"
            st.rerun()
    with col3:
        if st.button("📋 View Summary ➡️", use_container_width=True, type="primary", key="page3_view_summary"):
            st.session_state.current_page = "Page 4: Summary"
            st.rerun()

def get_dimension_description(dimension):
    """Get description for VUIA dimension"""
    descriptions = {
        "Volatility": "Measures the frequency and pace of change in key business inputs",
        "Ambiguity": "Assesses clarity of definitions, objectives, and stakeholder understanding", 
        "Interconnectedness": "Evaluates the complexity of system dependencies and relationships",
        "Uncertainty": "Analyzes predictability, feedback mechanisms, and validation standards"
    }
    return descriptions.get(dimension, "")

# ----------------------------- PAGE 4: SUMMARY -----------------------------
def render_page_4():
    st.title("📋 Executive Summary")
    
    if not st.session_state.analysis_complete:
        st.warning("No analysis completed yet. Please go to Page 1 to start an analysis.")
        return
    
    if st.session_state.problem_statement:
        st.markdown(f"""
        <div class="problem-display-card">
            <h4 style="color: white; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="margin-right: 10px; font-size: 1.5rem;">🎯</span> Business Problem Statement - {st.session_state.customer}
            </h4>
            <div style="background: rgba(255,255,255,0.15); padding: 20px; border-radius: 15px; border-left: 4px solid rgba(255,255,255,0.4); backdrop-filter: blur(10px);">
                <p style="color: white; margin: 0; line-height: 1.6; font-size: 15px; font-weight: 500;">{st.session_state.problem_statement}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Executive Summary Content with VUIA breakdown
    render_executive_summary()
    
    # Detailed Analysis Summary Section - Only 🎯 Recommendations tab
    render_detailed_analysis_summary()
    
    # Enhanced Navigation - WITH UNIQUE KEYS
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back to VUIA Analysis", use_container_width=True, key="page4_back_to_vuia"):
            st.session_state.current_page = "Page 3: VUIA Dimensions"
            st.rerun()
    with col2:
        if st.button("🔄 New Analysis", use_container_width=True, type="primary", key="page4_new_analysis"):
            reset_application()
            st.rerun()

def render_executive_summary():
    """Render executive summary with visual scorecards and dimension breakdowns"""
    st.markdown("### 📊 Executive Summary")
    
    # Overall Score Card
    score = st.session_state.difficulty_score
    difficulty_level, level_color, level_emoji = get_difficulty_level(score)
    
    if score <= 3.0:
        recommendation = "This problem can be addressed with standard solutions and minimal organizational changes."
    elif score <= 4.0:
        recommendation = "This problem requires careful planning and may involve cross-functional coordination."
    else:
        recommendation = "This problem demands significant organizational changes and strategic intervention."
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card executive-summary">
            <h4 style="color: #667eea; margin-bottom: 15px;">🏆 Overall Score</h4>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: 800; color: {level_color}; margin: 10px 0;">{score:.2f}<span style="font-size: 1.5rem; opacity: 0.8;">/5</span></div>
                <div style="font-size: 1.2rem; color: {level_color}; font-weight: 600;">{difficulty_level}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Highest Dimension
        dimension_scores = st.session_state.dimension_scores
        highest_dimension = max(dimension_scores, key=dimension_scores.get)
        highest_score = dimension_scores[highest_dimension]
        highest_level, highest_color, highest_emoji = get_difficulty_level(highest_score)
        
        st.markdown(f"""
        <div class="summary-card executive-summary">
            <h4 style="color: #667eea; margin-bottom: 15px;">📈 Primary Challenge</h4>
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: 800; color: #333; margin: 10px 0;">{highest_dimension}</div>
                <div style="font-size: 1.5rem; color: {highest_color}; font-weight: 600;">{highest_score:.2f}<span style="font-size: 1rem; opacity: 0.8;">/5</span></div>
                <div style="font-size: 1rem; color: #666;">{highest_level}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Industry Context
        industry = st.session_state.industry
        st.markdown(f"""
        <div class="summary-card executive-summary">
            <h4 style="color: #667eea; margin-bottom: 15px;">🏭 Industry Context</h4>
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: 800; color: #333; margin: 10px 0;">{industry}</div>
                <div style="font-size: 1rem; color: #666;">Industry-specific challenges considered</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # VUIA Dimension Scores - Enhanced Visual Breakdown
    st.markdown("### 📊 VUIA Dimension Breakdown")
    
    # Create a more comprehensive dimension breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        # Dimension Scores with Progress Bars
        st.markdown("#### 📈 Dimension Scores")
        dimensions = ["Volatility", "Uncertainty", "Interconnectedness", "Ambiguity"]
        colors = ["#ff6b6b", "#96ceb4", "#45b7d1", "#4ecdc4"]
        icons = ["🌪️", "❓", "🕸️", "🎭"]
        
        for dimension, color, icon in zip(dimensions, colors, icons):
            score = st.session_state.dimension_scores[dimension]
            percentage = (score / 5) * 100
            level, level_color, level_emoji = get_difficulty_level(score)
            
            st.markdown(f"""
            <div style="margin: 20px 0;">
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 600; color: #333; font-size: 1.1rem;">
                        {icon} {dimension}
                    </span>
                    <span style="font-weight: 700; color: {color}; font-size: 1.2rem;">
                        {score:.2f}<span style="font-size: 0.9rem; opacity: 0.8;">/5</span>
                    </span>
                </div>
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 5px;">{level}</div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {percentage}%; background: {color};"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        # Dimension Comparison Radar Chart (Visual Representation)
        st.markdown("#### 🎯 Complexity Assessment")
        
        # Create a simple radar chart representation using metrics
        dimension_scores = st.session_state.dimension_scores
        
        # Calculate overall complexity insights
        avg_score = sum(dimension_scores.values()) / len(dimension_scores)
        max_score = max(dimension_scores.values())
        min_score = min(dimension_scores.values())
        
        st.markdown(f"""
        <div class="summary-card executive-summary">
            <h5 style="color: #667eea; margin-bottom: 15px;">📊 Complexity Insights</h5>
            <div style="margin: 15px 0;">
                <div style="display: flex; justify-content: space-between; margin: 10px 0;">
                    <span>Average Dimension Score:</span>
                    <span style="font-weight: 700; color: #667eea;">{avg_score:.2f}<span style="font-size: 0.8rem; opacity: 0.8;">/5</span></span>
                </div>
                <div style="display: flex; justify-content: space-between; margin: 10px 0;">
                    <span>Highest Dimension:</span>
                    <span style="font-weight: 700; color: #ff6b6b;">{max(dimension_scores, key=dimension_scores.get)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin: 10px 0;">
                    <span>Lowest Dimension:</span>
                    <span style="font-weight: 700; color: #4ecdc4;">{min(dimension_scores, key=dimension_scores.get)}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recommendation based on scores
        st.markdown(f"""
        <div class="summary-card executive-summary">
            <h5 style="color: #667eea; margin-bottom: 15px;">💡 Strategic Insight</h5>
            <div style="color: #666; line-height: 1.6; font-size: 0.95rem;">
                {recommendation}
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_detailed_analysis_summary():
    """Render detailed analysis summary from all APIs"""
    st.markdown("## 📝 Detailed Analysis Summary")
    
    # Create tabs for different sections of the analysis - Keep only tab4
    tab4 = st.tabs(["🎯 Recommendations"])[0]
    
    with tab4:        
        # Overall hardness summary
        if st.session_state.outputs.get("hardness_summary"):
            st.markdown("#### 📋 Comprehensive Summary")
            st.markdown(f'<div class="analysis-card">{st.session_state.outputs["hardness_summary"]}</div>', unsafe_allow_html=True)
        
        # Generate strategic recommendations based on scores
        overall_score = st.session_state.difficulty_score
        dimension_scores = st.session_state.dimension_scores
        
        # Overall recommendation based on total score
        if overall_score <= 3.0:
            st.markdown("""
            <div class="analysis-card" style="border-left-color: #4CAF50;">
                <h4 style="color: #4CAF50;">🟢 Low Complexity Recommendation</h4>
                <p>This problem can be addressed with standard solutions and minimal organizational changes. Focus on:</p>
                <ul>
                    <li>Implementing best practices</li>
                    <li>Leveraging existing frameworks</li>
                    <li>Minimal process adjustments</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        elif overall_score <= 4.0:
            st.markdown("""
            <div class="analysis-card" style="border-left-color: #FF9800;">
                <h4 style="color: #FF9800;">🟡 Moderate Complexity Recommendation</h4>
                <p>This problem requires careful planning and may involve cross-functional coordination. Consider:</p>
                <ul>
                    <li>Structured project management</li>
                    <li>Cross-departmental collaboration</li>
                    <li>Phased implementation approach</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="analysis-card" style="border-left-color: #F44336;">
                <h4 style="color: #F44336;">🔴 High Complexity Recommendation</h4>
                <p>This problem demands significant organizational changes and strategic intervention. Essential actions:</p>
                <ul>
                    <li>Executive sponsorship and oversight</li>
                    <li>Comprehensive change management</li>
                    <li>Significant resource allocation</li>
                    <li>Long-term strategic planning</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        # Dimension-specific recommendations
        highest_dimension = max(dimension_scores, key=dimension_scores.get)
        highest_score = dimension_scores[highest_dimension]
        
        st.markdown(f"""
        <div class="analysis-card">
            <h4>🎯 Priority Focus Area</h4>
            <p>Your primary challenge is in <strong>{highest_dimension}</strong> with a score of {highest_score:.2f}/5.</p>
            <p><strong>Recommended focus:</strong> {get_dimension_focus_recommendation(highest_dimension, highest_score)}</p>
        </div>
        """, unsafe_allow_html=True)

def get_dimension_focus_recommendation(dimension, score):
    """Get specific recommendations for each dimension"""
    recommendations = {
        "Volatility": {
            "low": "Monitor change patterns and maintain current adaptability measures.",
            "medium": "Develop contingency plans for moderate frequency changes.",
            "high": "Implement robust change management and rapid response systems."
        },
        "Uncertainty": {
            "low": "Continue with current decision-making frameworks.",
            "medium": "Enhance data collection and scenario planning.",
            "high": "Implement advanced forecasting and risk management systems."
        },
        "Interconnectedness": {
            "low": "Maintain current system integration levels.",
            "medium": "Strengthen cross-functional communication channels.",
            "high": "Develop comprehensive system mapping and dependency management."
        },
        "Ambiguity": {
            "low": "Continue with clear communication protocols.",
            "medium": "Enhance requirement documentation and stakeholder alignment.",
            "high": "Implement rigorous clarification processes and validation frameworks."
        }
    }
    
    level = "low" if score <= 3.0 else "medium" if score <= 4.0 else "high"
    return recommendations[dimension][level]

def get_dimension_color(dimension):
    """Get color for each dimension"""
    colors = {
        "Volatility": "#ff6b6b",        # Red for volatility/change
        "Uncertainty": "#96ceb4",       # Green for uncertainty/predictability  
        "Interconnectedness": "#45b7d1", # Blue for interconnectedness
        "Ambiguity": "#9C27B0"          # Purple for ambiguity
    }
    return colors.get(dimension, "#667eea")

# ----------------------------- ANALYSIS FUNCTION -----------------------------

def show_magic_wand_loader():
    """Magical transformation loader"""
    magic_frames = [
        "✨ Gathering business insights...",
        "🔮 Analyzing patterns...",
        "🌟 Revealing opportunities...",
        "💫 Crafting solutions...",
        "🎯 Focusing recommendations..."
    ]
    
    placeholder = st.empty()
    for i in range(12):
        frame = magic_frames[i % len(magic_frames)]
        
        placeholder.markdown(f"""
        <div style="text-align: center; padding: 40px;">
            <div style="font-size: 2.5rem; margin-bottom: 30px;">
                                {frame}
            </div>
            <div style="display: flex; justify-content: center; gap: 10px; margin: 30px 0;">
                <div style="width: 15px; height: 15px; background: #667eea; border-radius: 50%; animation: bounce 0.6s infinite alternate; animation-delay: 0s"></div>
                <div style="width: 15px; height: 15px; background: #667eea; border-radius: 50%; animation: bounce 0.6s infinite alternate; animation-delay: 0.2s"></div>
                <div style="width: 15px; height: 15px; background: #667eea; border-radius: 50%; animation: bounce 0.6s infinite alternate; animation-delay: 0.4s"></div>
                <div style="width: 15px; height: 15px; background: #667eea; border-radius: 50%; animation: bounce 0.6s infinite alternate; animation-delay: 0.6s"></div>
                <div style="width: 15px; height: 15px; background: #667eea; border-radius: 50%; animation: bounce 0.6s infinite alternate; animation-delay: 0.8s"></div>
            </div>
            <div style="font-size: 1.1rem; color: #666; font-style: italic;">
                Working magic on your problem statement...
            </div>
        </div>
        <style>
        @keyframes sparkle {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.5; transform: scale(1.2); }}
        }}
        @keyframes bounce {{
            0% {{ transform: translateY(0px); opacity: 0.3; }}
            100% {{ transform: translateY(-15px); opacity: 1; }}
        }}
        </style>
        """, unsafe_allow_html=True)
        time.sleep(0.5)



def show_creative_loader():
    """Randomly select and show one of the creative loaders"""
    loaders = [
        show_magic_wand_loader
    ]
    
    # Select a random loader
    selected_loader = random.choice(loaders)
    selected_loader()

# Then modify the run_analysis function to use the creative loader:

def run_analysis(problem):
    """Run the complete analysis and store results in session state"""
    placeholder = st.empty()
    
    try:
        # Show initial loader
        with placeholder.container():
            show_creative_loader()
        
        outputs = {}
        st.session_state.outputs = {}
        st.session_state.difficulty_score = 0.0
        st.session_state.dimension_scores = {
            "Volatility": 0.0,
            "Ambiguity": 0.0,
            "Interconnectedness": 0.0,
            "Uncertainty": 0.0
        }
        st.session_state.individual_scores = {}
        st.session_state.selected_vuia_dimension = None
        st.session_state.show_vocabulary = False
        
        total_apis = len(API_CONFIGS)
        
        # Process APIs one by one
        for i, api in enumerate(API_CONFIGS):
            # Update progress in loader
            with placeholder.container():
                show_progress_loader(i, total_apis, api['description'])
            
            result = call_api(api, problem, outputs)
            result_clean = clean_output(result)
            outputs[api['name']] = result_clean
        
        st.session_state.outputs = outputs
        
        # Update individual scores from the actual answer texts
        update_individual_scores_from_answers()
        
        # Extract scores from hardness_summary API
        if outputs.get('hardness_summary'):
            st.session_state.difficulty_score = extract_difficulty_score(outputs['hardness_summary'])
            st.session_state.dimension_scores = extract_dimension_scores(outputs['hardness_summary'])
        
        st.session_state.analysis_complete = True
        
        # Clear the loader
        placeholder.empty()
        st.success("✅ Analysis Complete!")
        
    except Exception as e:
        # Clear the loader on error too
        placeholder.empty()
        st.error(f"❌ An error occurred during analysis: {str(e)}")
        st.session_state.analysis_complete = False

def show_progress_loader(current, total, current_task):
    """Show progress loader with current task"""
    progress = (current) / total
    loader_frames = ["⏳", "⏳", "⏳", "⌛", "⌛", "⌛"]
    current_frame = loader_frames[current % len(loader_frames)]
    
    st.markdown(f"""
    <div style="text-align: center; padding: 40px;">
        <div style="font-size: 3rem; margin-bottom: 20px;">{current_frame}</div>
        <h3 style="color: #333; margin-bottom: 20px;">Analyzing Your Business Problem</h3>
        <div style="width: 100%; background: #f0f0f0; border-radius: 10px; height: 20px; margin: 20px auto;">
            <div style="width: {progress * 100}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); 
                     border-radius: 10px; transition: width 0.3s ease;"></div>
        </div>
        <div style="margin-top: 10px; font-size: 1.1rem; color: #666;">
            {int(progress * 100)}% Complete
        </div>
        <div style="margin-top: 15px; font-size: 1rem; color: #888; font-style: italic;">
            Current: {current_task}
        </div>
        <div style="margin-top: 10px; font-size: 0.9rem; color: #999;">
            Step {current} of {total}
        </div>
    </div>
    """, unsafe_allow_html=True)
    time.sleep(0.1)  

# Small delay to show the update# ----------------------------- SIDEBAR NAVIGATION -----------------------------
# In the sidebar section, update the New Analysis button:
with st.sidebar:

# Mu-Sigma Logo in Navigation
    st.markdown(f'''
    <div style="text-align: center; margin-bottom: 20px;">
        <a href="#" class="musigma-logo-link">
            <div class="musigma-logo">
                <img src="https://upload.wikimedia.org/wikipedia/en/0/0c/Mu_Sigma_Logo.jpg" width="120" height="100" style="border-radius: 8px;">
            </div>
        </a>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown("### 🧭 Navigation")
    
    pages = {
        "Page 1: Input": "🏠 Home",
        "Page 2: Analysis": "📊 Analysis", 
        "Page 3: VUIA Dimensions": "🔍 VUIA Analysis",
        "Page 4: Summary": "📋 Summary"
    }
    
    for page_key, page_name in pages.items():
        if st.button(page_name, 
                    use_container_width=True, 
                    type="primary" if st.session_state.current_page == page_key else "secondary",
                    key=f"sidebar_{page_key.replace(' ', '_').replace(':', '')}"):
            st.session_state.current_page = page_key
            st.rerun()
    
    # Add New Analysis button in the navigation section
    st.markdown("---")
    if st.button("🔄 New Analysis", use_container_width=True, type="secondary", key="sidebar_new_analysis"):
        reset_application()
        st.rerun()  # Force a rerun to reflect the reset
    
    # Rest of your sidebar code...
    
    st.markdown("---")
    
    if st.session_state.analysis_complete:
        st.markdown("### 📈 Analysis Status")
        st.success("✅ Analysis Complete")
        
        score = st.session_state.difficulty_score
        level, color, emoji = get_difficulty_level(score)
        st.metric("Overall Difficulty Score", f"{score:.2f}")
        
        st.markdown("### 🎯 VUIA Scores")
        cols = st.columns(2)
        dimension_scores = st.session_state.dimension_scores
        with cols[0]:
            st.metric("Volatility", f"{dimension_scores['Volatility']:.2f}")
            st.metric("Ambiguity", f"{dimension_scores['Ambiguity']:.2f}")
        with cols[1]:
            st.metric("Interconnectedness", f"{dimension_scores['Interconnectedness']:.2f}")
            st.metric("Uncertainty", f"{dimension_scores['Uncertainty']:.2f}")
        
        if st.session_state.problem_statement:
            problem_preview = st.session_state.problem_statement[:100] + "..." if len(st.session_state.problem_statement) > 100 else st.session_state.problem_statement
            st.markdown("### 📝 Problem Preview")
            st.info(f"{st.session_state.customer}: {problem_preview}")
    else:
        st.warning("⏳ No analysis completed")

# ----------------------------- MAIN APP ROUTING -----------------------------
def main():
    if st.session_state.current_page == "Page 1: Input":
        render_page_1()
    elif st.session_state.current_page == "Page 2: Analysis":
        render_page_2()
    elif st.session_state.current_page == "Page 3: VUIA Dimensions":
        render_page_3()
    elif st.session_state.current_page == "Page 4: Summary":
        render_page_4()

if __name__ == "__main__":
    main()