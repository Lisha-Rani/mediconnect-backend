import os
import tempfile
from fastapi import UploadFile
from openai import AsyncOpenAI
from app.core.config import settings

# Initialize the async OpenAI client for Whisper
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class AISymptomChecker:
        
    async def transcribe_audio(self, file: UploadFile) -> str:
        """
        Converts uploaded audio file to text using OpenAI's Whisper model.
        """
        # Create a temporary file because the OpenAI API requires a physical file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            # Read the async upload stream and write to the temp file
            content = await file.read()
            temp_audio.write(content)
            temp_path = temp_audio.name

        try:
            # Send to OpenAI Whisper
            with open(temp_path, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
            return transcript.text
        finally:
            # Always clean up the temporary file to prevent server bloat
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def analyze_symptoms(self, patient_input: str) -> dict:
        """
        Analyzes text symptoms. 
        (Mocked here for structure; replace with actual LangChain/GPT logic).
        """
        return {
            "severity": "MILD",
            "explanation": f"Based on the transcription: '{patient_input}', these symptoms appear mild.",
            "precautions": ["Rest", "Drink fluids"],
            "recommend_doctor": False,
            "disclaimer": "This is AI guidance, not a medical diagnosis."
        }