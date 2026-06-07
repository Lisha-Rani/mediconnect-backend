import re
import json
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.session import get_db
from app.db.models import Diagnosis, User, MedicalKnowledge
from app.api.dependencies import get_current_user

router = APIRouter()

# --- PYDANTIC MODELS ---
class SymptomRequest(BaseModel):
    transcribed_text: str

class SymptomAnalysis(BaseModel):
    primary_symptoms: list[str] = Field(description="List of main symptoms extracted")
    potential_conditions: list[str] = Field(description="Broad potential conditions based on symptoms")
    recommended_action: str = Field(description="Recommended next steps for the patient")
    urgency_level: str = Field(description="Must be exactly: Low, Medium, High, or Critical")
    remedy_search_term: str | None = Field(
        description="A short search phrase for YouTube home remedies IF urgency is Low. Otherwise, null. Example: 'home remedies for mild cough'",
        default=None
    )

class FinalTriageResponse(BaseModel):
    analysis: SymptomAnalysis
    recommended_videos: list[dict] = []

# --- NATIVE YOUTUBE EXTRACTOR (Bypasses dependency conflicts) ---
# --- NATIVE YOUTUBE EXTRACTOR (Self-healing recursive parsing) ---
async def fetch_youtube_remedies(search_term: str) -> list[dict]:
    query = search_term.replace(" ", "+")
    url = f"https://www.youtube.com/results?search_query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=5.0)
            if response.status_code != 200:
                return []
            
            # Extract initial data object
            match = re.search(r"ytInitialData\s*=\s*({.*?});", response.text)
            if not match:
                return []
                
            data = json.loads(match.group(1))
            video_list = []
            
            # Dynamic recursive search function to hunt down video objects anywhere in the tree
            def find_videos_recursive(obj):
                if isinstance(obj, dict):
                    if "videoRenderer" in obj:
                        v = obj["videoRenderer"]
                        video_id = v.get("videoId")
                        title = v.get("title", {}).get("runs", [{}])[0].get("text") or v.get("title", {}).get("simpleText", "Remedy Video")
                        thumbnail_list = v.get("thumbnail", {}).get("thumbnails", [])
                        thumbnail = thumbnail_list[0].get("url") if thumbnail_list else None
                        
                        if video_id and len(video_list) < 3:
                            video_list.append({
                                "title": title,
                                "link": f"https://www.youtube.com/watch?v={video_id}",
                                "thumbnail": thumbnail
                            })
                    else:
                        for value in obj.values():
                            find_videos_recursive(value)
                elif isinstance(obj, list):
                    for item in obj:
                        find_videos_recursive(item)

            # Kick off the search tree crawl
            find_videos_recursive(data)
            return video_list
            
        except Exception as e:
            print(f"Native YouTube search skipped: {e}")
            return []

# --- ENDPOINTS ---
@router.post("/voice-symptom-check")
async def analyze_voice_symptoms(
    request: SymptomRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # --- PHASE 3: THE RETRIEVER ---
        embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            task="feature-extraction",
            huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY 
        )
        user_vector = await embeddings.aembed_query(request.transcribed_text)
        
        result = await db.execute(
            select(MedicalKnowledge)
            .order_by(MedicalKnowledge.embedding.cosine_distance(user_vector))
            .limit(2)
        )
        relevant_docs = result.scalars().all()
        context_text = "\n\n".join([doc.content for doc in relevant_docs])

        # --- PHASE 4: THE PROMPT UPGRADE (Hybrid RAG) ---
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0,
            api_key=settings.GOOGLE_API_KEY
        )
        
        parser = JsonOutputParser(pydantic_object=SymptomAnalysis)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert AI medical triage assistant.\n\n"
                       "RULE 1: Always prioritize the provided MEDICAL GUIDELINES. If the patient's symptoms match the guidelines, follow them strictly for your diagnosis.\n"
                       "RULE 2: If the symptoms DO NOT match the guidelines, evaluate severity.\n"
                       " - If MILD, suggest safe home care, set urgency to 'Low', and generate a short search phrase in 'remedy_search_term' (e.g., 'home remedies for headache').\n"
                       " - If SEVERE, strongly advise professional medical care and leave 'remedy_search_term' null.\n\n"
                       "MEDICAL GUIDELINES:\n{context}\n\n"
                       "Format Instructions:\n{format_instructions}"),
            ("human", "Patient transcript: {transcript}")
        ])
        
        chain = prompt | llm | parser
        
        ai_diagnosis = await chain.ainvoke({
            "transcript": request.transcribed_text,
            "context": context_text,
            "format_instructions": parser.get_format_instructions()
        })

        # --- PHASE 5: FETCH YOUTUBE VIDEOS NATIVELY ---
        video_list = []
        search_term = ai_diagnosis.get("remedy_search_term")
        if search_term:
            print(f"Fetching videos natively for: {search_term}")
            video_list = await fetch_youtube_remedies(search_term)

        # Combine payload
        final_payload = FinalTriageResponse(
            analysis=ai_diagnosis,
            recommended_videos=video_list
        )
        
        # Save to database
        new_diagnosis = Diagnosis(
            user_id=current_user.id,
            transcript=request.transcribed_text,
            ai_analysis=final_payload.model_dump()
        )
        db.add(new_diagnosis)
        await db.commit()
        
        return final_payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_patient_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Diagnosis)
            .where(Diagnosis.user_id == current_user.id)
            .order_by(Diagnosis.created_at.desc())
        )
        diagnoses = result.scalars().all()
        return diagnoses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))