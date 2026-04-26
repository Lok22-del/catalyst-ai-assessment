import os
import json
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from agents.skill_extractor import ExtractedSkills
from agents.assessment_agent import SkillAssessmentResult

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError(
        "GOOGLE_API_KEY not found. "
        "Create a .env file with: GOOGLE_API_KEY=your_key_here\n"
        "Get a free key at: https://aistudio.google.com/apikey"
    )


class SkillGap(BaseModel):
    skill: str
    current_score: int = Field(description="Candidate's current score 1-5")
    required_score: int = Field(description="Minimum score needed for the role (3=Mid, 4=Senior)")
    gap_size: int = Field(description="required_score - current_score (0 if no gap)")
    priority: str = Field(description="Critical / High / Medium / Low based on JD importance")
    is_required: bool = Field(description="True if this is a must-have skill in the JD")


class AdjacentSkill(BaseModel):
    skill: str
    why_adjacent: str = Field(description="Why this skill is learnable given current profile")
    effort_level: str = Field(description="Low / Medium / High effort to acquire")
    relevance_to_role: str = Field(description="How relevant this is to the target role")


class GapAnalysisResult(BaseModel):
    candidate_name: str
    target_role: str
    overall_readiness_score: float = Field(description="0-100 score")
    readiness_label: str = Field(description="Not Ready / Partially Ready / Ready / Highly Ready")
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    strong_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    adjacent_skills: list[AdjacentSkill] = Field(default_factory=list)
    strengths_summary: str = Field(default="")
    gaps_summary: str = Field(default="")


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.find("\n"):].strip()
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    return raw


def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
    )



GAP_ANALYSIS_PROMPT = """\
You are a career advisor performing a detailed skill gap analysis.

Candidate: {candidate_name}
Target Role: {job_title} at {company}
Role Domain: {domain}
Required Experience Level: {experience_level}

JD Required Skills: {required_skills}
JD Preferred Skills: {preferred_skills}
Candidate Total Experience: {total_years} years

Assessment Scores (1-5 scale):
{assessment_scores}

Candidate Resume Skills: {resume_skills}

Instructions:
- For required skills: minimum score needed is 3 (Mid-level) or 4 (Senior)
- For preferred skills: minimum score needed is 2
- overall_readiness_score: 0-100, weighted — required skills 70%, preferred 30%
- adjacent_skills: 3-5 skills the candidate is close to knowing
- missing_skills: required skills with score 0 or 1
- priority values: Critical / High / Medium / Low only

Return a single JSON object with this exact structure:
{{
  "candidate_name": "...",
  "target_role": "...",
  "overall_readiness_score": 65.0,
  "readiness_label": "Partially Ready",
  "skill_gaps": [
    {{
      "skill": "...",
      "current_score": 2,
      "required_score": 4,
      "gap_size": 2,
      "priority": "Critical",
      "is_required": true
    }}
  ],
  "strong_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "adjacent_skills": [
    {{
      "skill": "...",
      "why_adjacent": "...",
      "effort_level": "Medium",
      "relevance_to_role": "..."
    }}
  ],
  "strengths_summary": "...",
  "gaps_summary": "..."
}}

Return ONLY the JSON object. No markdown fences, no explanation.
"""


def run_gap_analysis(
    extracted: ExtractedSkills,
    assessment: SkillAssessmentResult,
) -> GapAnalysisResult:
    print("[Agent 3] Running gap analysis...")

    score_lines = []
    for s in assessment.skills_assessed:
        score_lines.append(
            f"  - {s.skill}: {s.score}/5 ({s.level_label}) — {s.evidence[:80]}"
        )
    assessment_scores_text = "\n".join(score_lines) or "  No scores available"

    prompt = ChatPromptTemplate.from_template(GAP_ANALYSIS_PROMPT)
    chain = prompt | get_llm()

    response = chain.invoke({
        "candidate_name": extracted.resume_skills.candidate_name,
        "job_title": extracted.jd_requirements.job_title,
        "company": extracted.jd_requirements.company or "the company",
        "domain": extracted.jd_requirements.domain,
        "experience_level": extracted.jd_requirements.experience_level,
        "required_skills": ", ".join(extracted.jd_requirements.required_skills),
        "preferred_skills": ", ".join(extracted.jd_requirements.preferred_skills) or "None",
        "total_years": extracted.resume_skills.total_years_experience,
        "assessment_scores": assessment_scores_text,
        "resume_skills": ", ".join(extracted.resume_skills.technical_skills),
    })

    raw = _strip_json(response.content)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[Agent 3] JSON parse error: {e}\nRaw:\n{raw[:300]}")
        data = {
            "candidate_name": extracted.resume_skills.candidate_name,
            "target_role": extracted.jd_requirements.job_title,
            "overall_readiness_score": 50.0,
            "readiness_label": "Partially Ready",
            "skill_gaps": [],
            "strong_skills": extracted.resume_skills.technical_skills[:5],
            "missing_skills": extracted.jd_requirements.required_skills[:3],
            "adjacent_skills": [],
            "strengths_summary": "Assessment data could not be fully processed.",
            "gaps_summary": "Please review the JD requirements manually.",
        }

    return GapAnalysisResult(**data)
