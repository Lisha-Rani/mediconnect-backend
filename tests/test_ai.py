import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.anyio
async def test_root_endpoint(async_client):
    """
    Tests that the basic root endpoint responds properly.
    """
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "project" in data

@pytest.mark.anyio
async def test_voice_endpoint_invalid_file_type(async_client):
    """
    Tests that the voice endpoint correctly rejects non-audio file types.
    """
    # Create a dummy text file payload
    files = {"audio": ("test.txt", b"not an audio file data", "text/plain")}
    
    response = await async_client.post("/api/v1/ai/voice-symptom-check", files=files)
    assert response.status_code == 400
    assert "Must be an audio file" in response.json()["detail"]

@pytest.mark.anyio
@patch("app.services.ai_service.AISymptomChecker.transcribe_audio", new_callable=AsyncMock)
async def test_voice_endpoint_success(mock_transcribe, async_client):
    """
    Tests a successful voice upload workflow using a mocked Whisper response.
    """
    # Mock the transcription result so we don't call the live OpenAI API
    mock_transcribe.return_value = "I have a severe headache and high fever."
    
    # Create a dummy audio file payload
    files = {"audio": ("symptoms.webm", b"fake-audio-binary-data", "audio/webm")}
    
    response = await async_client.post("/api/v1/ai/voice-symptom-check", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["transcript"] == "I have a severe headache and high fever."
    assert "analysis" in data
    assert data["analysis"]["severity"] == "MILD"  # Matching our current service fallback mock