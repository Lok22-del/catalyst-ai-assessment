import os
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError(
        "GOOGLE_API_KEY not found. "
        "Create a .env file with: GOOGLE_API_KEY=your_key_here\n"
        "Get a free key at: https://aistudio.google.com/apikey"
    )


class ResumeSkills(BaseModel):
    candidate_name: str = Field(description="Candidate's full name")
    technical_skills: list[str] = Field(description="All technical skills: languages, frameworks, tools, platforms")
    soft_skills: list[str] = Field(description="Soft skills: communication, teamwork, leadership, etc.")
    total_years_experience: float = Field(description="Total years of professional experience")
    education_level: str = Field(description="Highest education qualification")
    domains_worked_in: list[str] = Field(description="Domains/industries the candidate has worked in")
    notable_projects: list[str] = Field(description="Notable projects with one-line descriptions")


class JDRequirements(BaseModel):
    job_title: str = Field(description="Exact job title")
    company: str = Field(default="", description="Company name if present")
    required_skills: list[str] = Field(description="Must-have technical skills")
    preferred_skills: list[str] = Field(default_factory=list, description="Nice-to-have skills")
    required_years_experience: str = Field(description="e.g. '3-5 years' or '2+ years'")
    experience_level: str = Field(description="Junior / Mid / Senior / Lead")
    key_responsibilities: list[str] = Field(description="Core job responsibilities")
    education_requirement: str = Field(default="", description="Required degree/qualification")
    domain: str = Field(description="Domain: AI/ML, Web Dev, DevOps, Data Engineering, etc.")


class ExtractedSkills(BaseModel):
    resume_skills: ResumeSkills
    jd_requirements: JDRequirements
    all_required_skills: list[str] = Field(
        description="Unified list of ALL skills required by JD (required + preferred combined)"
    )


def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
    )


RESUME_PROMPT = """\
You are an expert resume analyser. Extract ALL skills and information from this resume.
Be exhaustive — include every tool, language, framework, platform mentioned anywhere.

{format_instructions}

Resume Text:
\"\"\"
{resume_text}
\"\"\"

Return ONLY valid JSON. No markdown, no explanation.
"""

JD_PROMPT = """\
You are an expert job description analyser. Extract all requirements from this JD.
Separate required skills (must-have) from preferred skills (nice-to-have).

{format_instructions}

Job Description:
\"\"\"
{jd_text}
\"\"\"

Return ONLY valid JSON. No markdown, no explanation.
"""


def extract_resume_skills(resume_text: str) -> ResumeSkills:
    parser = PydanticOutputParser(pydantic_object=ResumeSkills)
    prompt = ChatPromptTemplate.from_template(RESUME_PROMPT)
    chain = prompt | get_llm() | parser
    return chain.invoke({
        "resume_text": resume_text,
        "format_instructions": parser.get_format_instructions(),
    })


def extract_jd_requirements(jd_text: str) -> JDRequirements:
    parser = PydanticOutputParser(pydantic_object=JDRequirements)
    prompt = ChatPromptTemplate.from_template(JD_PROMPT)
    chain = prompt | get_llm() | parser
    return chain.invoke({
        "jd_text": jd_text,
        "format_instructions": parser.get_format_instructions(),
    })


def run_skill_extractor(resume_text: str, jd_text: str) -> ExtractedSkills:
    print("[Agent 1] Extracting skills from Resume...")
    resume_skills = extract_resume_skills(resume_text)

    print("[Agent 1] Extracting requirements from JD...")
    jd_requirements = extract_jd_requirements(jd_text)

    all_required = list(set(jd_requirements.required_skills + jd_requirements.preferred_skills))

    return ExtractedSkills(
        resume_skills=resume_skills,
        jd_requirements=jd_requirements,
        all_required_skills=all_required,
    )
