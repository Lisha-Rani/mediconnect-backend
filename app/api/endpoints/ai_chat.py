from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ai_service import AISymptomChecker

router = APIRouter()
ai_checker = AISymptomChecker()

@router.post("/voice-symptom-check")
async def analyze_voice_symptoms(audio: UploadFile = File(...)):
    """
    Accepts an audio file from the user's microphone, converts it to text, 
    and returns the AI symptom analysis.
    """
    # 1. Validate file type to ensure it's an audio file
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Must be an audio file."
        )
        
    try:
        # 2. Convert Voice to Text
        transcript_text = await ai_checker.transcribe_audio(audio)
        
        # 3. Feed the transcribed text into our existing symptom analyzer
        analysis = await ai_checker.analyze_symptoms(transcript_text)
        
        # 4. Return both the transcript (so the user sees what they said) and the analysis
        return {
            "success": True,
            "transcript": transcript_text,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")