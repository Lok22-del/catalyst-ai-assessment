import os
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage
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


class SkillScore(BaseModel):
    skill: str
    score: int = Field(description="Proficiency score 1-5: 1=None, 2=Beginner, 3=Intermediate, 4=Advanced, 5=Expert")
    evidence: str = Field(description="What the candidate said that justifies this score")
    level_label: str = Field(description="None / Beginner / Intermediate / Advanced / Expert")


class SkillAssessmentResult(BaseModel):
    candidate_name: str
    skills_assessed: list[SkillScore]
    overall_score: float = Field(description="Weighted average score across all skills (1.0-5.0)")
    assessment_summary: str = Field(description="2-3 line summary of the candidate's overall profile")



def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.4,
        google_api_key=GOOGLE_API_KEY,
    )



ASSESSMENT_SYSTEM_PROMPT = """\
You are an expert technical interviewer doing a BRIEF skill assessment.

Candidate: {candidate_name}
Job Role: {job_title}
Skills to assess: {skills_list}

IMPORTANT: You have only {max_questions} questions total. Be efficient.

Rules:
1. Ask ONE question at a time — no multi-part questions
2. Each question must cover a DIFFERENT skill from the list
3. Ask practical/scenario-based questions (not just "do you know X?")
4. Skip the warm-up — go straight into skill questions from question 1
5. After {max_questions} exchanges OR once all skills are covered, say exactly: "ASSESSMENT_COMPLETE"
6. Keep your questions short and direct (1-2 sentences max)

Current exchange: {exchange_count} of {max_questions}
Skills still to assess: {remaining_skills}

Be concise. One focused question per message. No filler text.
"""

SCORING_PROMPT = """\
You are evaluating a technical interview. Based on the conversation below, 
score the candidate's proficiency on each skill from 1-5.

Scoring rubric:
1 = No knowledge / never used it
2 = Beginner — heard of it, basic awareness only  
3 = Intermediate — used it in projects, understands core concepts
4 = Advanced — strong hands-on experience, can handle edge cases
5 = Expert — deep mastery, can teach others, knows internals

Skills to score: {skills_list}
Candidate name: {candidate_name}

{format_instructions}

Interview Conversation:
\"\"\"
{conversation_text}
\"\"\"

Return ONLY valid JSON. No markdown, no explanation.
"""




class AssessmentSession:

    def __init__(
        self,
        candidate_name: str,
        job_title: str,
        skills_to_assess: list[str],
        max_questions: int = 5,
    ):
        self.candidate_name = candidate_name
        self.job_title = job_title
        self.skills_to_assess = skills_to_assess
        self.max_questions = max_questions
        self.exchange_count = 0
        self.history: list[dict] = []   
        self.complete = False
        self.llm = get_llm()
        self._assessed_skills: list[str] = []

    def _build_messages(self, user_input: str) -> list:
        remaining = [s for s in self.skills_to_assess if s not in self._assessed_skills]

        system_content = ASSESSMENT_SYSTEM_PROMPT.format(
            candidate_name=self.candidate_name,
            job_title=self.job_title,
            skills_list=", ".join(self.skills_to_assess),
            max_questions=self.max_questions,
            exchange_count=self.exchange_count,
            remaining_skills=", ".join(remaining) if remaining else "All covered",
        )

        messages = [{"role": "system", "content": system_content}]

        for msg in self.history:
            messages.append(msg)

        messages.append({"role": "user", "content": user_input})

        return messages

    def start(self) -> str:
        opening_prompt = (
            f"Hello! I'm ready to begin. Please introduce yourself and ask your first question."
        )
        messages = self._build_messages(opening_prompt)
        response = self.llm.invoke(messages)
        ai_reply = response.content

        self.history.append({"role": "user", "content": opening_prompt})
        self.history.append({"role": "assistant", "content": ai_reply})

        if "ASSESSMENT_COMPLETE" in ai_reply:
            self.complete = True
            ai_reply = ai_reply.replace("ASSESSMENT_COMPLETE", "").strip()

        return ai_reply

    def chat(self, user_message: str) -> str:
        """
        Process a user message and return the assessor's next response.

        Args:
            user_message: The candidate's response

        Returns:
            The assessor's next question or closing message
        """
        if self.complete:
            return "Assessment is already complete. Call get_results() to see scores."

        self.exchange_count += 1

        messages = self._build_messages(user_message)
        response = self.llm.invoke(messages)
        ai_reply = response.content

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": ai_reply})

        if "ASSESSMENT_COMPLETE" in ai_reply or self.exchange_count >= self.max_questions:
            self.complete = True
            ai_reply = ai_reply.replace("ASSESSMENT_COMPLETE", "").strip()
            if not ai_reply:
                ai_reply = (
                    "Thank you! That wraps up our assessment. "
                    "I'll now analyse your responses and generate your personalised report."
                )

        return ai_reply

    def is_complete(self) -> bool:
        return self.complete

    def get_conversation_text(self) -> str:
        lines = []
        for msg in self.history:
            role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
            lines.append(f"{role}: {msg['content']}")
        return "\n\n".join(lines)

    def get_results(self) -> SkillAssessmentResult:
        """
        Score the conversation and return structured assessment results.
        Called after assessment is complete.
        """
        print("[Agent 2] Scoring assessment conversation...")
        conversation_text = self.get_conversation_text()

        parser = PydanticOutputParser(pydantic_object=SkillAssessmentResult)
        prompt = ChatPromptTemplate.from_template(SCORING_PROMPT)
        chain = prompt | get_llm() | parser

        result = chain.invoke({
            "skills_list": ", ".join(self.skills_to_assess),
            "candidate_name": self.candidate_name,
            "conversation_text": conversation_text,
            "format_instructions": parser.get_format_instructions(),
        })

        return result
