import streamlit as st
from pypdf import PdfReader
from docx import Document
from groq import Groq
import json
import pandas as pd
import io
import base64

# Page Layout Configuration
st.set_page_config(
    page_title="AI Contract & NDA Risk Analyzer",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ AI Contract & NDA Risk Analyzer")
st.markdown("Upload a client contract, NDA, or service agreement (**PDF, Word DOCX, PNG, JPG**) below. The AI will audit it for predatory clauses, assign a risk score, and suggest safer alternatives.")

# Sidebar Configuration with safe local & cloud fallback
st.sidebar.header("Configuration")
api_key = ""
try:
    if "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
        st.sidebar.success("API Key loaded securely from Secrets!")
except Exception:
    pass

if not api_key:
    api_key = st.sidebar.text_input(
        "Enter Groq API Key (Free):", 
        value="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", 
        type="password"
    )
st.sidebar.markdown("[Get a free Groq API key here](https://console.groq.com/)")

def extract_text_or_process_file(uploaded_file, api_key):
    """Extracts text from PDF/DOCX or processes images via Groq Vision for high precision."""
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    system_prompt = (
        "You are an expert contract lawyer and legal risk auditor AI. "
        "Analyze the provided legal document thoroughly. Read every single word, clause, condition, and fine print. "
        "Identify hidden traps, predatory clauses, unilateral termination rights, unfair non-competes, "
        "unlimited liability, and intellectual property overreaches. "
        "Return a clean JSON object with the following keys: "
        "document_title, overall_risk_score (Integer from 1 to 10, where 10 is extremely high risk), "
        "executive_summary (string), "
        "red_flags (an array of objects, each containing: clause_title, risk_level [High/Medium/Low], explanation, recommended_counter_clause)."
    )
    
    client = Groq(api_key=api_key)

    if file_extension == 'pdf':
        pdf_reader = PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contract Text:\n{text}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content), text

    elif file_extension in ['docx', 'doc']:
        doc = Document(uploaded_file)
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text:
                text += paragraph.text + "\n"
                
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contract Text:\n{text}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content), text

    elif file_extension in ['png', 'jpg', 'jpeg']:
        image_bytes = uploaded_file.read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt + "\nRead every word precisely from this contract image and analyze its legal risks."},
                        {"type": "image_url", "image_url": {"url": f"data:image/{file_extension};base64,{base64_image}"}}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content), "[Image-based contract processed via Vision]"

def answer_legal_question(contract_context, question, api_key):
    """Allows users to ask custom questions about the contract text."""
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "You are an expert AI legal assistant. Answer the user's question accurately based strictly on the provided contract data."
            },
            {
                "role": "user",
                "content": f"Contract Context:\n{contract_context}\n\nQuestion: {question}"
            }
        ]
    )
    return response.choices[0].message.content

# --- Main Application UI ---
uploaded_file = st.file_uploader(
    "📂 Drop your contract, NDA, or scan here (PDF, Word DOCX, PNG, JPG)", 
    type=["pdf", "docx", "png", "jpg", "jpeg"]
)

if uploaded_file:
    st.success(f"📄 Loaded file: {uploaded_file.name}")
    
    if "contract_analysis" not in st.session_state or st.session_state.get("current_contract") != uploaded_file.name:
        st.session_state["current_contract"] = uploaded_file.name
        st.session_state["contract_analysis"] = None
        st.session_state["contract_text"] = ""

    if st.button("🚀 Run Legal Risk Audit"):
        if not api_key:
            st.error("Please enter a valid Groq API Key.")
        else:
            with st.spinner("Analyzing every word and auditing clauses via Groq AI..."):
                try:
                    uploaded_file.seek(0)
                    analysis_data, raw_text = extract_text_or_process_file(uploaded_file, api_key)
                    st.session_state["contract_analysis"] = analysis_data
                    st.session_state["contract_text"] = raw_text
                    st.success("Legal Audit Complete!")
                except Exception as e:
                    st.error(f"Error analyzing contract: {e}")

    # Display Audit Results
    if st.session_state.get("contract_analysis"):
        data = st.session_state["contract_analysis"]
        
        st.divider()
        st.subheader("📊 Audit Dashboard")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            risk_score = data.get("overall_risk_score", 5)
            st.metric(label="Overall Risk Score (1-10)", value=f"{risk_score} / 10")
        with col2:
            st.markdown(f"**Executive Summary:** {data.get('executive_summary', 'N/A')}")
            
        st.subheader("🚩 Flagged Risky Clauses")
        red_flags = data.get("red_flags", [])
        
        if red_flags:
            for flag in red_flags:
                level = flag.get("risk_level", "Medium")
                color_icon = "🔴" if level == "High" else "🟡" if level == "Medium" else "🟢"
                
                with st.expander(f"{color_icon} [{level} Risk] {flag.get('clause_title', 'Clause')}"):
                    st.markdown(f"**Why it's risky:** {flag.get('explanation', '')}")
                    st.markdown(f"**Suggested Counter-Clause:** `{flag.get('recommended_counter_clause', '')}`")
        else:
            st.info("No major red flags found in this document.")
            
        # Export Report Option
        st.divider()
        try:
            df_flags = pd.DataFrame(red_flags)
            csv_data = df_flags.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Risk Audit Report as CSV",
                data=csv_data,
                file_name=f"{uploaded_file.name}_risk_audit.csv",
                mime="text/csv"
            )
        except Exception:
            pass

        # Interactive Chat Section
        st.divider()
        st.subheader("💬 Chat with this Contract")
        user_question = st.text_input("Ask a specific legal question about this document (e.g., 'What are the termination conditions?'):")
        if user_question:
            if not api_key:
                st.error("Please enter your API key to use the chat feature.")
            else:
                with st.spinner("Analyzing contract text for answers..."):
                    answer = answer_legal_question(st.session_state["contract_text"], user_question, api_key)
                    st.markdown(f"**Answer:** {answer}")