import asyncio
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.db.session import get_db
from app.db.models import MedicalKnowledge

# FIX 1: Import the exact Endpoint version!
from langchain_huggingface import HuggingFaceEndpointEmbeddings

async def seed_database():
    print("1. Scanning the Medical PDF...")
    loader = PyPDFLoader("clinical_guidelines.pdf") 
    pages = loader.load()
    print(f"   -> Successfully loaded {len(pages)} pages!")

    print("2. Chopping pages into digestible chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents(pages)
    print(f"   -> Created {len(chunks)} knowledge chunks.")

    print("3. Connecting to Hugging Face Cloud API...")
    embeddings = HuggingFaceEndpointEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2",
        task="feature-extraction",
        # FIX 2: Correctly pull the key from your settings!
        huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY 
    )

    print("4. Converting text to vectors and saving to Neon database...")
    async for db in get_db():
        for chunk in chunks:
            vector = await embeddings.aembed_query(chunk.page_content)
            
            # Save the text, the vector, and the PDF name/page number
            source_info = f"{chunk.metadata.get('source')} - Page {chunk.metadata.get('page')}"
            
            new_knowledge = MedicalKnowledge(
                content=chunk.page_content,
                embedding=vector,
                source=source_info
            )
            db.add(new_knowledge)
        
        await db.commit()
        print("SUCCESS! Real medical PDF is fully loaded into the brain.")
        break

if __name__ == "__main__":
    asyncio.run(seed_database())