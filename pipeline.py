"""
pipeline.py
-----------
Orchestrates the full 4-agent pipeline:
  Resume + JD → [Agent 1] Skill Extractor
              → [Agent 2] Conversational Assessment (returns session)
              → [Agent 3] Gap Analysis
              → [Agent 4] Learning Plan (LangGraph)
              → Final Report
"""

from utils.pdf_extractor import extract_text_safe
from agents.skill_extractor import run_skill_extractor, ExtractedSkills
from agents.assessment_agent import AssessmentSession, SkillAssessmentResult
from agents.gap_analysis_agent import run_gap_analysis, GapAnalysisResult
from agents.learning_plan_agent import run_learning_plan_agent


class Pipeline:
    """
    Full pipeline state manager.
    Designed to work with a web API — holds state between HTTP requests.
    """

    def __init__(self):
        self.extracted_skills: ExtractedSkills | None = None
        self.assessment_session: AssessmentSession | None = None
        self.assessment_result: SkillAssessmentResult | None = None
        self.gap_analysis: GapAnalysisResult | None = None
        self.final_report: dict | None = None
        self.stage: str = "idle"  # idle → extracted → assessing → analysing → complete

    # ── Stage 1 ──────────────────────────────

    def run_extraction(self, resume_path: str, jd_text: str) -> ExtractedSkills:
        """Run Agent 1: Extract skills from resume and JD."""
        print("\n══════════════════════════════")
        print("  STAGE 1: Skill Extraction")
        print("══════════════════════════════")

        resume_text = extract_text_safe(resume_path)
        self.extracted_skills = run_skill_extractor(resume_text, jd_text)
        self.stage = "extracted"
        return self.extracted_skills

    # ── Stage 2 ──────────────────────────────

    def start_assessment(self) -> str:
        """
        Initialise Agent 2 assessment session.
        Returns the first question from the assessor.
        """
        if not self.extracted_skills:
            raise ValueError("Run extraction first.")

        print("\n══════════════════════════════")
        print("  STAGE 2: Assessment Started")
        print("══════════════════════════════")

        skills_to_assess = self.extracted_skills.all_required_skills[:5]  # Cap at 5 skills

        self.assessment_session = AssessmentSession(
            candidate_name=self.extracted_skills.resume_skills.candidate_name,
            job_title=self.extracted_skills.jd_requirements.job_title,
            skills_to_assess=skills_to_assess,
            max_questions=5,
        )
        self.stage = "assessing"
        return self.assessment_session.start()

    def chat(self, user_message: str) -> tuple[str, bool]:
        """
        Send a message to the assessment agent.
        Returns (ai_response, is_complete).
        """
        if not self.assessment_session:
            raise ValueError("Assessment not started.")

        reply = self.assessment_session.chat(user_message)
        is_done = self.assessment_session.is_complete()
        return reply, is_done

    def finalise_assessment(self) -> SkillAssessmentResult:
        """Score the assessment conversation."""
        if not self.assessment_session:
            raise ValueError("No active session.")
        self.assessment_result = self.assessment_session.get_results()
        return self.assessment_result

    # ── Stage 3 ──────────────────────────────

    def run_gap_analysis(self) -> GapAnalysisResult:
        """Run Agent 3: Gap Analysis."""
        print("\n══════════════════════════════")
        print("  STAGE 3: Gap Analysis")
        print("══════════════════════════════")

        if not self.extracted_skills or not self.assessment_result:
            raise ValueError("Run extraction and assessment first.")

        self.gap_analysis = run_gap_analysis(self.extracted_skills, self.assessment_result)
        self.stage = "analysing"
        return self.gap_analysis

    # ── Stage 4 ──────────────────────────────

    def run_learning_plan(self) -> dict:
        """Run Agent 4: Learning Plan (LangGraph)."""
        print("\n══════════════════════════════")
        print("  STAGE 4: Learning Plan")
        print("══════════════════════════════")

        if not self.gap_analysis:
            raise ValueError("Run gap analysis first.")

        self.final_report = run_learning_plan_agent(
            self.gap_analysis,
            self.extracted_skills,
            self.assessment_result,
        )
        self.stage = "complete"
        return self.final_report

    # ── Full Auto Run (non-interactive) ──────

    def run_full_pipeline_demo(self, resume_path: str, jd_text: str) -> dict:
        """
        Run the full pipeline with simulated assessment answers.
        Useful for testing without a live user.
        """
        self.run_extraction(resume_path, jd_text)

        first_q = self.start_assessment()
        print(f"\nAssessor: {first_q}")

        # Simulate a few demo answers
        demo_answers = [
            "I have 2 years of experience with Python, mainly for data processing and building REST APIs with FastAPI.",
            "I've used React for frontend development in 3 projects, comfortable with hooks and state management.",
            "I understand the basics of machine learning — I've done a Coursera course and built a simple classifier.",
            "I've worked with Docker in development environments, but not much Kubernetes in production.",
            "I use Git daily — branching, PRs, resolving merge conflicts.",
            "I've built a small RAG pipeline using LangChain and Pinecone for a hackathon project.",
        ]

        for answer in demo_answers:
            print(f"\nCandidate: {answer}")
            reply, done = self.chat(answer)
            print(f"Assessor: {reply}")
            if done:
                break

        self.finalise_assessment()
        self.run_gap_analysis()
        return self.run_learning_plan()
