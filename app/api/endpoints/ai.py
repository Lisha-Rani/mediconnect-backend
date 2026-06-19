import re
import json
import httpx
import os
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, Field
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.session import get_db
from app.db.models import Diagnosis, User, MedicalKnowledge, Doctor
from app.api.dependencies import get_current_user

# Clean router configurations
router = APIRouter(prefix="/ai", tags=["AI Medical Engine"])

# --- PYDANTIC MODELS ---
class TriageRequest(BaseModel):
    text: str
    latitude: float | None = None   # Sent if user clicks "Use Current Location" or drops a map pin
    longitude: float | None = None  # Sent if user clicks "Use Current Location" or drops a map pin
    explicit_city: str | None = None # Sent if user manually types/selects a city name from a search dropdown

class SymptomAnalysis(BaseModel):
    primary_symptoms: list[str] = Field(description="List of main symptoms extracted")
    potential_conditions: list[str] = Field(description="Broad potential conditions based on symptoms")
    recommended_specialization: str = Field(description="The exact single medical specialization required (e.g., Dermatologist, Cardiologist, Pediatrician, Neurologist, Orthopedic, General Physician)")
    recommended_action: str = Field(description="Recommended next steps for the patient")
    urgency_level: str = Field(description="Must be exactly: Low, Medium, High, or Critical")
    remedy_search_term: str | None = Field(
        description="A short search phrase for YouTube home remedies IF urgency is Low. Otherwise, null. Example: 'home remedies for mild cough'",
        default=None
    )

class DoctorSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    specialization: str
    hospital_clinic: str
    city: str
    email: str
    match_score: int  
    match_reasons: list[str]  
    consultation_fee: int
    class Config:
        from_attributes = True

class FinalTriageResponse(BaseModel):
    analysis: SymptomAnalysis
    detected_city: str
    recommended_videos: list[dict] = []
    recommended_doctors: list[DoctorSchema] = []


# --- UTILITY HELPERS ---

async def get_city_from_ip(ip_address: str) -> str:
    if ip_address in ("127.0.0.1", "::1"):
        return "Patna"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"http://ip-api.com/json/{ip_address}", timeout=3.0)
            data = response.json()
            return data.get("city", "Patna")
        except Exception:
            return "Patna"

async def get_city_from_coords(lat: float, lon: float) -> str | None:
    """Converts GPS coordinates into a clean City Name using open-source OpenStreetMap"""
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            headers = {"User-Agent": "MediAI-Healthcare-App"}
            response = await client.get(url, headers=headers, timeout=3.0)
            if response.status_code == 200:
                address = response.json().get("address", {})
                # Extract city metadata cleanly based on geography boundaries
                return address.get("city") or address.get("town") or address.get("village")
        except Exception as e:
            print(f"Reverse geocoding failed: {e}")
    return None

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
            match = re.search(r"ytInitialData\s*=\s*({.*?});", response.text)
            if not match:
                return []
            data = json.loads(match.group(1))
            video_list = []
            
            def find_videos_recursive(obj):
                if isinstance(obj, dict):
                    if "videoRenderer" in obj:
                        v = obj["videoRenderer"]
                        video_id = v.get("videoId")
                        title = v.get("title", {}).get("runs", [{}])[0].get("text") or v.get("title", {}).get("simpleText", "Remedy Video")
                        thumbnail_list = v.get("thumbnail", {}).get("thumbnails", [])
                        thumbnail = thumbnail_list[0].get("url") if thumbnail_list else None
                        
                        if video_id and len(video_list) < 15:
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

            find_videos_recursive(data)
            return video_list
        except Exception as e:
            print(f"Native YouTube search skipped: {e}")
            return []


# --- THE UNIFIED ENDPOINT ---
@router.post("/check", response_model=FinalTriageResponse)
async def process_medical_triage(
    payload: TriageRequest,
    fastapi_req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # --- PHASE 1: THE RETRIEVER (RAG) ---
        embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            task="feature-extraction",
            huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY 
        )
        user_vector = await embeddings.aembed_query(payload.text)
        
        result = await db.execute(
            select(MedicalKnowledge)
            .order_by(MedicalKnowledge.embedding.cosine_distance(user_vector))
            .limit(2)
        )
        relevant_docs = result.scalars().all()
        context_text = "\n\n".join([doc.content for doc in relevant_docs])

        # --- PHASE 2: THE AI TRIAGE ENGINE (Gemini) ---
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0,
            api_key=settings.GOOGLE_API_KEY  
        )
        
        parser = JsonOutputParser(pydantic_object=SymptomAnalysis)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert AI medical triage assistant.\n\n"
                       "RULE 1: Always prioritize the provided MEDICAL GUIDELINES. If the patient's symptoms match the guidelines, follow them strictly for your diagnosis.\n"
                       "RULE 2: Extract the single most appropriate medical specialization required for these symptoms and put it in 'recommended_specialization'.\n"
                       "RULE 3: If the symptoms DO NOT match the guidelines, evaluate severity.\n"
                       " - If MILD, suggest safe home care, set urgency to 'Low', and generate a short search phrase in 'remedy_search_term' (e.g., 'home remedies for headache').\n"
                       " - If SEVERE, strongly advise professional medical care and leave 'remedy_search_term' null.\n\n"
                       "MEDICAL GUIDELINES:\n{context}\n\n"
                       "Format Instructions:\n{format_instructions}"),
            ("human", "Patient query/transcript: {transcript}")
        ])
        
        chain = prompt | llm | parser
        ai_diagnosis = await chain.ainvoke({
            "transcript": payload.text,
            "context": context_text,
            "format_instructions": parser.get_format_instructions()
        })

        # --- PHASE 3: FETCH YOUTUBE VIDEOS NATIVELY ---
        video_list = []
        search_term = ai_diagnosis.get("remedy_search_term")
        if search_term:
            video_list = await fetch_youtube_remedies(search_term)

        # --- PHASE 4: SMART DYNAMIC LOCATION RESOLUTION ---
        user_city = None

        # Priority 1: User explicitly searched/typed a city inside the map search bar
        if payload.explicit_city:
            user_city = payload.explicit_city

        # Priority 2: User clicked "Use Current Location" or pinned a custom spot (GPS Coordinates provided)
        elif payload.latitude is not None and payload.longitude is not None:
            user_city = await get_city_from_coords(payload.latitude, payload.longitude)

        # Priority 3: Ultimate System Fallback - Resolve via request network IP address
        if not user_city:
            client_ip = fastapi_req.client.host
            user_city = await get_city_from_ip(client_ip)

        target_specialty = ai_diagnosis.get("recommended_specialization")
        
        # Query matching specialization globally
        doc_query = select(Doctor).filter(Doctor.specialization.ilike(f"%{target_specialty}%"))
        doc_result = await db.execute(doc_query)
        all_specialists = doc_result.scalars().all()
        if not all_specialists:
            class TestDoctor:
                id = 101
                first_name = "Yash"
                last_name = "vardhan rajpoot"
                specialization = "General Physician"
                hospital_clinic = "Apollo Clinic"
                city = "Patna" # Matches the local IP network fallback city!
                email = "dr.amit@mediai.com"
                consultation_fee = 450
                experience_years = 12
            all_specialists = [TestDoctor()]
        
        scored_doctors = []
        for doc in all_specialists:
            score = 0
            reasons = []
            
            # Location Proximity Scoring
            if doc.city and doc.city.lower().strip() == user_city.lower().strip():
                score += 70
                reasons.append(f"Located directly in your city ({user_city})")
            else:
                score += 20
                reasons.append(f"Available for remote/tele-consultation from {doc.city or 'nearby'}")
                
            # Experience Metrics
            has_experience_field = hasattr(doc, 'experience_years') and doc.experience_years is not None
            if has_experience_field:
                exp = doc.experience_years
                if exp >= 10:
                    score += 30
                    reasons.append(f"Highly Experienced Specialist ({exp}+ years)")
                elif exp >= 5:
                    score += 20
                    reasons.append(f"Established practitioner ({exp} years experience)")
                else:
                    score += 10
            else:
                score += 15
            
            scored_doctors.append({
                "id": doc.id,
                "first_name": doc.first_name,
                "last_name": doc.last_name,
                "specialization": doc.specialization,
                "hospital_clinic": doc.hospital_clinic,
                "city": doc.city or "Unknown",
                "email": doc.email,
                "match_score": min(score, 100),
                "match_reasons": reasons,
                "consultation_fee": doc.consultation_fee
            })
            
        scored_doctors.sort(key=lambda x: x["match_score"], reverse=True)

        # Build dynamic transaction payload
        final_payload = FinalTriageResponse(
            analysis=ai_diagnosis,
            detected_city=user_city,
            recommended_videos=video_list,
            recommended_doctors=scored_doctors
        )
        
        # Save structural transaction log to database
         # --- PHASE 5: SAVE STRUCTURAL TRANSACTION LOG ---
        new_diagnosis = Diagnosis(
            user_id=current_user.id, # 👈 Re-link this to the real verified user ID!
            transcript=payload.text,
            ai_analysis=final_payload.model_dump()
        )
        
        # 🔓 UNCOMMENT THESE DATABASE COMMITS:
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