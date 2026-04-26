import os
import json
from typing import TypedDict
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from agents.gap_analysis_agent import GapAnalysisResult
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

LEVEL_LABELS = {1: "None", 2: "Beginner", 3: "Intermediate", 4: "Advanced", 5: "Expert"}


class PlannerState(TypedDict):
    gap_analysis:     dict
    extracted_skills: dict
    assessment:       dict
    skill_plans:      list
    weekly_schedule:  list
    final_report:     dict
    error:            str


def get_llm(temperature=0):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=temperature,
        google_api_key=GOOGLE_API_KEY,
    )



def strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.find("\n"):].strip()
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    return raw



NODE1_PROMPT = """\
You are a career coach. Do two things in one response:

1. Prioritise skill gaps for this candidate
2. Generate a learning plan for each gap

Candidate: {candidate_name}
Target Role: {target_role} ({domain})
Readiness: {readiness_score}/100 ({readiness_label})

Skill Gaps identified:
{gaps_text}

Missing Skills (not assessed): {missing_skills}

Return a JSON array of skill learning plans (max 4 skills, priority order):
[
  {{
    "skill": "LangChain",
    "current_level": "Beginner",
    "target_level": "Intermediate",
    "estimated_weeks": 3,
    "priority": "Critical",
    "gap_size": 2,
    "why_important": "Core framework for the role",
    "learning_path": ["Understand chains & prompts", "Build a RAG app", "Use agents & tools"],
    "resources": [
      {{
        "title": "LangChain Crash Course",
        "url": "https://www.youtube.com/results?search_query=LangChain+tutorial+2024",
        "type": "Video",
        "platform": "YouTube",
        "duration": "3 hours",
        "is_free": true
      }},
      {{
        "title": "LangChain Official Docs",
        "url": "https://python.langchain.com/docs/get_started/introduction",
        "type": "Documentation",
        "platform": "LangChain",
        "duration": "Self-paced",
        "is_free": true
      }}
    ],
    "practice_project": "Build a document Q&A chatbot using LangChain + Gemini"
  }}
]

Rules:
- Max 4 skills only (keep it fast)
- Max 2 resources per skill
- Only skills with gap_size > 0
- Use real URLs: YouTube search = https://www.youtube.com/results?search_query=SKILL+tutorial
- Coursera search = https://www.coursera.org/search?query=SKILL
- estimated_weeks: 1-2 (small), 3-4 (medium), 5-6 (large gap)
- priority: Critical / High / Medium / Low

Return ONLY the JSON array. No markdown. No explanation.
"""


def node_prioritise_and_plan(state: PlannerState) -> PlannerState:
    print("[LangGraph Node 1] Prioritising gaps + generating plans (single call)...")

    gap       = state["gap_analysis"]
    extracted = state["extracted_skills"]

    gaps_text = "\n".join([
        f"  - {g['skill']} | {g.get('current_score',1)}/5 → {g.get('required_score',3)}/5 "
        f"| gap={g.get('gap_size',2)} | {g.get('priority','High')} | required={g.get('is_required',True)}"
        for g in gap.get("skill_gaps", [])
    ]) or "  No scored gaps — use missing skills below"

    prompt = ChatPromptTemplate.from_template(NODE1_PROMPT)
    chain  = prompt | get_llm(temperature=0.1)

    response = chain.invoke({
        "candidate_name":  gap.get("candidate_name", "Candidate"),
        "target_role":     gap.get("target_role", "the role"),
        "domain":          extracted.get("jd_requirements", {}).get("domain", "Software Engineering"),
        "readiness_score": gap.get("overall_readiness_score", 50),
        "readiness_label": gap.get("readiness_label", "Partially Ready"),
        "gaps_text":       gaps_text,
        "missing_skills":  ", ".join(gap.get("missing_skills", [])) or "None",
    })

    try:
        skill_plans = json.loads(strip_json(response.content))
        if not isinstance(skill_plans, list):
            raise ValueError("Expected JSON array")
    except Exception as e:
        print(f"Node 1 parse error: {e} — building fallback")
        skill_plans = [
            {
                "skill":           g["skill"],
                "current_level":   LEVEL_LABELS.get(g.get("current_score", 1), "Beginner"),
                "target_level":    LEVEL_LABELS.get(g.get("required_score", 3), "Intermediate"),
                "estimated_weeks": 3,
                "priority":        g.get("priority", "High"),
                "gap_size":        g.get("gap_size", 2),
                "why_important":   f"Required for {gap.get('target_role','the role')}",
                "learning_path":   [f"Learn {g['skill']} basics", f"Build a project with {g['skill']}"],
                "resources": [{
                    "title":    f"{g['skill']} Tutorial",
                    "url":      f"https://www.youtube.com/results?search_query={g['skill'].replace(' ', '+')}+tutorial",
                    "type":     "Video",
                    "platform": "YouTube",
                    "duration": "3 hours",
                    "is_free":  True,
                }],
                "practice_project": f"Build a working mini-project using {g['skill']}",
            }
            for g in gap.get("skill_gaps", [])[:4]
        ]

    return {**state, "skill_plans": skill_plans}



NODE2_PROMPT = """\
You are a career advisor. Do two things in one response:
1. Create a week-by-week learning schedule
2. Write the final assessment report text

Candidate: {candidate_name}
Target Role: {target_role} at {company}
Readiness: {readiness_score}/100 ({readiness_label})
Total learning weeks: {total_weeks} at 2 hrs/day

Skills to learn (in order):
{skills_summary}

Strong skills: {strong_skills}
Adjacent skills to explore: {adjacent_skills}

Return a single JSON object:
{{
  "weekly_schedule": [
    {{
      "week_number": 1,
      "focus_skills": ["skill1"],
      "daily_hours_needed": 2.0,
      "milestones": ["Complete intro tutorial", "Set up dev environment"],
      "deliverable": "Can write basic skill1 code from scratch"
    }}
  ],
  "executive_summary": "3-4 sentences: current state, key gaps, path forward",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "final_advice": "2-3 sentences of practical, motivational closing advice"
}}

Rules for schedule:
- Exactly {total_weeks} week entries
- Max 2 focus skills per week
- Each deliverable is specific and measurable

Return ONLY the JSON object. No markdown. No explanation.
"""


def node_timeline_and_report(state: PlannerState) -> PlannerState:
    print("[LangGraph Node 2] Building timeline + compiling report (single call)...")

    gap         = state["gap_analysis"]
    skill_plans = state["skill_plans"]
    extracted   = state["extracted_skills"]

    total_weeks = min(sum(p.get("estimated_weeks", 3) for p in skill_plans), 12)
    if total_weeks == 0:
        total_weeks = 4

    skills_summary = "\n".join([
        f"  {i+1}. {p['skill']} — {p.get('estimated_weeks',3)} weeks ({p.get('priority','High')} priority)"
        for i, p in enumerate(skill_plans)
    ]) or "  No specific skills identified"

    adjacent = [a.get("skill", "") for a in gap.get("adjacent_skills", [])]

    prompt = ChatPromptTemplate.from_template(NODE2_PROMPT)
    chain  = prompt | get_llm(temperature=0.1)

    response = chain.invoke({
        "candidate_name":  gap.get("candidate_name", "Candidate"),
        "target_role":     gap.get("target_role", "the role"),
        "company":         extracted.get("jd_requirements", {}).get("company", "the company"),
        "readiness_score": gap.get("overall_readiness_score", 50),
        "readiness_label": gap.get("readiness_label", "Partially Ready"),
        "total_weeks":     total_weeks,
        "skills_summary":  skills_summary,
        "strong_skills":   ", ".join(gap.get("strong_skills", [])) or "Not identified",
        "adjacent_skills": ", ".join(adjacent) or "None",
    })

    try:
        compiled = json.loads(strip_json(response.content))
        if not isinstance(compiled, dict):
            raise ValueError("Expected JSON object")
    except Exception as e:
        print(f" Node 2 parse error: {e} — building fallback")
        compiled = {
            "weekly_schedule": [
                {
                    "week_number":        w + 1,
                    "focus_skills":       [skill_plans[min(w // 2, len(skill_plans) - 1)]["skill"]] if skill_plans else ["Review"],
                    "daily_hours_needed": 2.0,
                    "milestones":         ["Complete tutorial", "Practice exercise"],
                    "deliverable":        f"Week {w+1} milestone achieved",
                }
                for w in range(total_weeks)
            ],
            "executive_summary": (
                f"{gap.get('candidate_name','The candidate')} is {gap.get('readiness_label','partially ready')} "
                f"for the {gap.get('target_role','target')} role with a readiness score of "
                f"{gap.get('overall_readiness_score',50)}/100. A {total_weeks}-week learning plan has been prepared."
            ),
            "strengths":    gap.get("strong_skills", [])[:4],
            "final_advice": "Stay consistent with your learning plan and build projects to demonstrate progress.",
        }

    final_report = {
        "candidate_name":         gap.get("candidate_name", ""),
        "target_role":            gap.get("target_role", ""),
        "company":                extracted.get("jd_requirements", {}).get("company", ""),
        "overall_readiness_score": gap.get("overall_readiness_score", 50),
        "readiness_label":        gap.get("readiness_label", "Partially Ready"),
        "total_learning_weeks":   total_weeks,
        "daily_hours_commitment": 2.0,
        "executive_summary":      compiled.get("executive_summary", ""),
        "strengths":              compiled.get("strengths", gap.get("strong_skills", [])),
        "final_advice":           compiled.get("final_advice", ""),
        "skill_plans":            skill_plans,
        "weekly_schedule":        compiled.get("weekly_schedule", []),
        "adjacent_skills_to_explore": adjacent,
    }

    return {**state, "weekly_schedule": compiled.get("weekly_schedule", []), "final_report": final_report}


def build_learning_plan_graph():
    graph = StateGraph(PlannerState)

    graph.add_node("prioritise_and_plan",   node_prioritise_and_plan)
    graph.add_node("timeline_and_report",   node_timeline_and_report)

    graph.set_entry_point("prioritise_and_plan")
    graph.add_edge("prioritise_and_plan", "timeline_and_report")
    graph.add_edge("timeline_and_report", END)

    return graph.compile()


def run_learning_plan_agent(
    gap_analysis:     GapAnalysisResult,
    extracted_skills: ExtractedSkills,
    assessment:       SkillAssessmentResult,
) -> dict:
    print("[Agent 4] Starting LangGraph pipeline (2-node optimised)...")

    graph_app = build_learning_plan_graph()

    initial_state: PlannerState = {
        "gap_analysis":     gap_analysis.model_dump(),
        "extracted_skills": extracted_skills.model_dump(),
        "assessment":       assessment.model_dump(),
        "skill_plans":      [],
        "weekly_schedule":  [],
        "final_report":     {},
        "error":            "",
    }

    final_state = graph_app.invoke(initial_state)
    print("[Agent 4] Learning plan complete.")
    return final_state["final_report"]
