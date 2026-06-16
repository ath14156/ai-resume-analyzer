import re
import json
import streamlit as st
import pdfplumber
from docx import Document
import boto3

st.set_page_config(page_title="AI Resume Analyzer", layout="centered")

# AWS Bedrock Client
bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)

st.title("🤖 AI Resume Analyzer")
st.write("Upload a resume and paste a job description to compare skills and generate AI feedback.")

skills = [
    "python", "sql", "java", "matlab", "aws",
    "machine learning", "data analysis", "data visualization",
    "predictive analytics", "statistical analysis", "automation",
    "systems engineering", "industrial engineering",
    "requirements analysis", "testing", "validation", "verification",
    "networking", "linux", "docker", "git", "simulation",
    "anylogic", "arena", "powersim", "vensim", "system dynamics",
    "troubleshooting", "documentation", "stakeholder communication",
    "project management", "hardware", "software", "system testing",
    "requirements", "configuration management", "risk analysis",
    "technical documentation", "communication", "leadership",
    "problem solving", "customer support", "performance analysis"
]

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s+#.]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text

def find_skills(text, skills_list):
    text = clean_text(text)
    found = []

    for skill in skills_list:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text):
            found.append(skill)

    return sorted(found)

def extract_text_from_pdf(uploaded_file):
    text = ""

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text

def extract_text_from_docx(uploaded_file):
    text = ""

    doc = Document(uploaded_file)

    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"

    return text

def extract_text_from_txt(uploaded_file):
    return uploaded_file.read().decode("utf-8")

def generate_local_feedback(score, matched_skills, missing_skills, resume_skills):
    strengths = []
    recommendations = []

    if matched_skills:
        strengths.append(
            "Your resume aligns with the job in these areas: "
            + ", ".join(matched_skills)
            + "."
        )

    if len(resume_skills) >= 10:
        strengths.append(
            "Your resume shows a broad technical skill set."
        )

    if "systems engineering" in resume_skills:
        strengths.append(
            "Your systems engineering background is valuable for requirements, testing, and validation roles."
        )

    if "python" in resume_skills:
        strengths.append(
            "Python experience supports automation, analytics, and AI-related work."
        )

    if missing_skills:
        for skill in missing_skills:
            recommendations.append(
                f"Add stronger evidence of {skill} if you have that experience."
            )
    else:
        recommendations.append(
            "Your resume covers the main tracked skills from this job description."
        )

    if score >= 75:
        readiness = "9/10"
        summary = "Strong match. Your resume aligns well with this job description."
    elif score >= 50:
        readiness = "7/10"
        summary = "Moderate match. Your resume has relevant experience, but needs stronger alignment."
    else:
        readiness = "5/10"
        summary = "Weak match. Your resume needs better alignment with the role."

    return strengths, recommendations, readiness, summary

def get_bedrock_feedback(resume_text, job_text, matched_skills, missing_skills):
    prompt = f"""
You are an experienced technical recruiter.

Analyze this resume against the job description.

Resume:
{resume_text[:3500]}

Job Description:
{job_text[:3500]}

Matched Skills:
{matched_skills}

Missing Skills:
{missing_skills}

Give a concise response with:
1. Strengths
2. Weaknesses
3. Missing skills
4. Resume improvement suggestions
5. Interview readiness score from 1 to 10

Do not be too long.
"""

    try:
        response = bedrock.invoke_model(
            modelId="amazon.nova-lite-v1:0",
            body=json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "max_new_tokens": 700,
                    "temperature": 0.4
                }
            }),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]

    except Exception as e:
        return f"""
AWS Bedrock feedback could not be generated.

Possible reasons:
- AWS credentials are not configured
- Bedrock model access is not enabled
- Region is incorrect
- Model access for Amazon Nova Lite is not approved

Error:
{e}
"""

uploaded_resume = st.file_uploader(
    "Upload Resume",
    type=["pdf", "docx", "txt"]
)

resume = ""

if uploaded_resume:

    if uploaded_resume.name.endswith(".pdf"):
        resume = extract_text_from_pdf(uploaded_resume)

    elif uploaded_resume.name.endswith(".docx"):
        resume = extract_text_from_docx(uploaded_resume)

    elif uploaded_resume.name.endswith(".txt"):
        resume = extract_text_from_txt(uploaded_resume)

    st.success("Resume uploaded successfully.")

    with st.expander("View Extracted Resume Text"):
        st.text(resume[:3000])

job = st.text_area("Job Description", height=250)

if st.button("Analyze Resume"):

    if not resume.strip() or not job.strip():
        st.warning("Please upload a resume and paste a job description.")

    else:
        resume_skills = find_skills(resume, skills)
        job_skills = find_skills(job, skills)

        matched_skills = sorted(set(resume_skills).intersection(set(job_skills)))
        missing_skills = sorted(set(job_skills).difference(set(resume_skills)))

        if len(job_skills) == 0:
            score = 0
        else:
            score = round((len(matched_skills) / len(job_skills)) * 100, 2)

        st.subheader("Resume Analysis Results")

        st.metric("Skill Match Score", f"{score}%")

        col1, col2, col3 = st.columns(3)

        col1.metric("Resume Skills Found", len(resume_skills))
        col2.metric("Job Skills Required", len(job_skills))
        col3.metric("Matched Skills", len(matched_skills))

        st.write("### ✅ Matched Skills")
        if matched_skills:
            st.success(", ".join(matched_skills))
        else:
            st.error("No matched skills found.")

        st.write("### ⚠️ Missing Skills From Job Description")
        if missing_skills:
            st.warning(", ".join(missing_skills))
        else:
            st.success("No major missing skills found from the tracked skill list.")

        st.write("### 📌 Resume Skills Detected")
        if resume_skills:
            st.write(", ".join(resume_skills))
        else:
            st.write("No tracked skills detected in resume.")

        strengths, recommendations, readiness, summary = generate_local_feedback(
            score,
            matched_skills,
            missing_skills,
            resume_skills
        )

        st.write("## 🤖 AI Resume Assessment")

        st.write("### 💪 Strengths")
        for item in strengths:
            st.success(item)

        st.write("### 🚀 Recommendations")
        for item in recommendations:
            st.info(item)

        st.write("### 🎯 Interview Readiness")
        st.metric("Readiness Score", readiness)

        st.write("### 🧠 Final Summary")
        if score >= 75:
            st.success(summary)
        elif score >= 50:
            st.warning(summary)
        else:
            st.error(summary)

        st.write("## ☁️ AWS Bedrock Feedback")

        with st.spinner("Generating feedback with AWS Bedrock..."):
            bedrock_feedback = get_bedrock_feedback(
                resume,
                job,
                matched_skills,
                missing_skills
            )

        st.write(bedrock_feedback)