import asyncio
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.db.session import get_db
from app.db.models import MedicalKnowledge
from langchain_huggingface import HuggingFaceEndpointEmbeddings

async def seed_database():
    print("1. 📄 Scanning the Medical PDF...")
    loader = PyPDFLoader("clinical_guidelines.pdf") 
    pages = loader.load()
    print(f"   -> Successfully loaded {len(pages)} pages!")

    print("2. ✂️ Chopping pages into digestible chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents(pages)
    print(f"   -> Created {len(chunks)} knowledge chunks.")

    print("3. 🌐 Connecting to Hugging Face Cloud API...")
    embeddings = HuggingFaceEndpointEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2",
        task="feature-extraction",
        huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY 
    )

    chunk_texts = [chunk.page_content for chunk in chunks]
    print(f"   -> Submitting all {len(chunk_texts)} chunks for bulk batch embedding...")
    vectors = await embeddings.aembed_documents(chunk_texts)
    print("   -> Vectors generated successfully!")

    print("4. 💾 Saving vector matrices to Neon cloud database...")
    async for db in get_db():
        for chunk, vector in zip(chunks, vectors):
            source_page = f"Page {chunk.metadata.get('page', 'Unknown')}"
            
            # Maps explicitly to valid table properties
            new_knowledge = MedicalKnowledge(
                disease_condition=f"Clinical Guideline Context ({source_page})",
                symptoms_summary=chunk.page_content,
                recommended_specialty="General Physician", 
                embedding=vector
            )
            db.add(new_knowledge)
        
        await db.commit()
        print("🚀 SUCCESS! Medical knowledge base is fully loaded and active inside Neon.")
        break

if __name__ == "__main__":
    asyncio.run(seed_database())