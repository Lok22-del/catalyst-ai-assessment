import os
import json
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from pipeline import Pipeline

app = FastAPI(title="Catalyst — AI Skill Assessment Agent")

_pipeline = Pipeline()


class ChatRequest(BaseModel):
    message: str


class StatusResponse(BaseModel):
    stage: str
    message: str


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path("templates/index.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse("<h1>Frontend not found. Place index.html in templates/</h1>")


@app.post("/upload")
async def upload_and_extract(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
):
    """
    Stage 1: Upload resume PDF + JD text, run Skill Extractor Agent.
    """
    global _pipeline
    _pipeline = Pipeline()  

    suffix = Path(resume.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(resume.file, tmp)
        tmp_path = tmp.name

    try:
        extracted = _pipeline.run_extraction(tmp_path, jd_text)
        os.unlink(tmp_path)

        return JSONResponse({
            "success": True,
            "stage": "extracted",
            "candidate_name": extracted.resume_skills.candidate_name,
            "job_title": extracted.jd_requirements.job_title,
            "company": extracted.jd_requirements.company,
            "domain": extracted.jd_requirements.domain,
            "resume_skills": extracted.resume_skills.technical_skills,
            "required_skills": extracted.jd_requirements.required_skills,
            "preferred_skills": extracted.jd_requirements.preferred_skills,
            "skills_to_assess": extracted.all_required_skills[:10],
            "total_years": extracted.resume_skills.total_years_experience,
        })

    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/start-assessment")
async def start_assessment():
    """
    Stage 2: Start the conversational assessment session.
    Returns first question from the AI assessor.
    """
    if _pipeline.stage != "extracted":
        raise HTTPException(status_code=400, detail="Upload resume and JD first.")

    try:
        first_question = _pipeline.start_assessment()
        return JSONResponse({
            "success": True,
            "message": first_question,
            "is_complete": False,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Stage 2 (continued): Send a message to the assessment agent.
    Returns the next question or completion signal.
    """
    if _pipeline.stage != "assessing":
        raise HTTPException(status_code=400, detail="Assessment not active.")

    try:
        reply, is_complete = _pipeline.chat(request.message)

        if is_complete:
            _pipeline.finalise_assessment()

        return JSONResponse({
            "success": True,
            "message": reply,
            "is_complete": is_complete,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-report")
async def generate_report():
    """
    Stages 3 + 4: Run Gap Analysis + Learning Plan generation.
    Returns the full structured report.
    """
    if not _pipeline.assessment_result:
        raise HTTPException(status_code=400, detail="Complete the assessment first.")

    try:
        _pipeline.run_gap_analysis()
        report = _pipeline.run_learning_plan()

        return JSONResponse({
            "success": True,
            "report": report,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    return JSONResponse({"stage": _pipeline.stage})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
