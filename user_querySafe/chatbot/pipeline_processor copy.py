import os
import time
import fitz
import re
import json
import faiss
import numpy as np
from collections import defaultdict
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from google import genai

# ----- Paths -----
BASE_DIR = "documents"
PDF_DIR = os.path.join(BASE_DIR, "files_uploaded")
IMAGE_DIR = os.path.join(BASE_DIR, "files_images")
TEXT_DIR = os.path.join(BASE_DIR, "files_captions")
CHUNK_DIR = os.path.join(BASE_DIR, "files_chunks")
INDEX_DIR = os.path.join(BASE_DIR, "vector_index")
META_DIR = os.path.join(BASE_DIR, "chunk-metadata")

# Create folders if they don't exist
for folder in [IMAGE_DIR, TEXT_DIR, CHUNK_DIR, INDEX_DIR, META_DIR]:
    os.makedirs(folder, exist_ok=True)

# ----- Models & Config -----
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
PROJECT_ID = "metricvibes-1718777660306"
REGION = "us-central1"
client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

# ----- Helper: Build Gemini Prompt -----
def build_prompt(image_data):
    return [{
        "role": "user",
        "parts": [
            {
                "text": (
                    "You are a visual analysis expert. Extract and describe every element in the image including:\n"
                    "- Text (as-is)\n"
                    "- Tables (as plain readable text)\n"
                    "- Charts/graphs (with insights and data)\n"
                    "- Images/diagrams (detailed description)\n"
                    "Output must be clean, complete, and human-readable."
                )
            },
            {"inline_data": {"mime_type": "image/png", "data": image_data}},
        ]
    }]

# ----- Wait for File Uploads to Stabilize -----
def wait_for_file_uploads(chatbot_id, wait_duration=10, check_interval=2):
    """
    Wait until the latest modification time for PDFs (of the given chatbot)
    is older than wait_duration seconds, meaning no new file upload is occurring.
    """
    print(f"\nWaiting for file uploads to finish for chatbot {chatbot_id}...")
    while True:
        files = [f for f in os.listdir(PDF_DIR)
                 if f.startswith(chatbot_id + "_") and f.lower().endswith(".pdf")]
        if not files:
            print("  No files found yet; waiting...")
            time.sleep(check_interval)
            continue
        mod_times = [os.path.getmtime(os.path.join(PDF_DIR, f)) for f in files]
        latest_mod = max(mod_times)
        elapsed = time.time() - latest_mod
        if elapsed >= wait_duration:
            break
        else:
            print(f"  Waiting... last upload was {elapsed:.1f} sec ago")
            time.sleep(check_interval)
    print("File uploads are stable. Proceeding with pipeline.")

# ===============================================
# STEP 1: Convert PDFs to Images (Sequential)
def convert_pdf_to_images(chatbot_id):
    print(f"\nSTEP 1: Converting PDFs to Images for chatbot {chatbot_id}")
    pdf_files = [f for f in os.listdir(PDF_DIR)
                 if f.startswith(chatbot_id + "_") and f.lower().endswith(".pdf")]
    if not pdf_files:
        print("  ⚠️  No PDFs found to convert.")
        return
    for pdf_file in pdf_files:
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        print(f"  ➤ Converting {pdf_file}...")
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=200)
                image_filename = f"{base_name}_page{page_num+1}.png"
                image_path = os.path.join(IMAGE_DIR, image_filename)
                pix.save(image_path)
                print(f"     ✓ Saved page {page_num+1} as {image_filename}")
            doc.close()
            print(f"  ✓ {pdf_file} converted successfully.")
        except Exception as e:
            print(f"  ✗ Error converting {pdf_file}: {e}")
    print("STEP 1 complete: All PDFs converted to images.")

# ===============================================
# STEP 2: Generate Captions (Sequential)
def generate_captions(chatbot_id):
    print(f"\nSTEP 2: Generating Captions for chatbot {chatbot_id}")
    grouped = defaultdict(list)
    img_files = sorted([f for f in os.listdir(IMAGE_DIR)
                        if f.startswith(chatbot_id + "_") and f.endswith(".png")])
    if not img_files:
        print("  ⚠️  No images found to generate captions.")
        return
    for img in img_files:
        base = "_".join(img.split("_")[:-1])
        grouped[base].append(img)
    for base, images in grouped.items():
        print(f"  ➤ Generating caption for {base}...")
        full_text = ""
        for img in sorted(images):
            image_path = os.path.join(IMAGE_DIR, img)
            try:
                with open(image_path, "rb") as f:
                    image_data = f.read()
                prompt = build_prompt(image_data)
                response = client.models.generate_content(
                    model="gemini-2.0-flash-001",
                    contents=prompt
                )
                caption = response.text.strip()
                full_text += f"\n--- Page: {img} ---\n{caption}\n\n"
                print(f"     ✓ Caption generated for {img}")
            except Exception as e:
                full_text += f"\n--- Page: {img} ---\nError: {e}\n\n"
                print(f"     ✗ Error generating caption for {img}: {e}")
        caption_filename = f"{base}.txt"
        caption_path = os.path.join(TEXT_DIR, caption_filename)
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"  ✓ Captions saved to {caption_filename}")
    print("STEP 2 complete: All images captioned.")

# ===============================================
# STEP 3: Chunk Captions into a Single File per PDF (Sequential)
def chunk_text(chatbot_id):
    print(f"\nSTEP 3: Chunking Caption Files for chatbot {chatbot_id}")
    files = [f for f in os.listdir(TEXT_DIR)
             if f.startswith(chatbot_id + "_") and f.endswith(".txt")]
    if not files:
        print("  ⚠️  No caption files found to chunk.")
        return
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    for file in files:
        caption_path = os.path.join(TEXT_DIR, file)
        with open(caption_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        chunks = splitter.split_text(raw_text)
        chunk_filename = file.replace(".txt", "-chunks.txt")
        chunk_path = os.path.join(CHUNK_DIR, chunk_filename)
        with open(chunk_path, "w", encoding="utf-8") as out:
            for idx, chunk in enumerate(chunks, 1):
                out.write(f"--- Chunk {idx} ---\n{chunk}\n\n")
        print(f"  ✓ {file} chunked into {chunk_filename}")
    print("STEP 3 complete: All caption files chunked.")

# ===============================================
# STEP 4: Embed Chunks and Build a Single FAISS Index (Sequential)
def embed_chunks(chatbot_id):
    print(f"\nSTEP 4: Embedding Chunks for chatbot {chatbot_id}")
    all_chunks = []
    chunk_files = [f for f in os.listdir(CHUNK_DIR)
                   if f.startswith(chatbot_id + "_") and f.endswith("-chunks.txt")]
    if not chunk_files:
        print("  ⚠️  No chunk files found for embedding.")
        return
    for file in chunk_files:
        chunk_path = os.path.join(CHUNK_DIR, file)
        with open(chunk_path, "r", encoding="utf-8") as f:
            content = f.read()
        chunks = re.split(r'--- Chunk \d+ ---\n', content)
        all_chunks.extend([c.strip() for c in chunks if c.strip()])
    if not all_chunks:
        print("  ❌ No text chunks available to embed.")
        return
    print(f"  ➤ Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = embedding_model.encode(all_chunks, show_progress_bar=True)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    index_path = os.path.join(INDEX_DIR, f"{chatbot_id}-index.index")
    meta_path = os.path.join(META_DIR, f"{chatbot_id}-chunks.json")
    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)
    print(f"  ✓ FAISS index and metadata saved for chatbot {chatbot_id}")
    print("STEP 4 complete: Embedding done.")

# ===============================================
# MAIN PIPELINE FUNCTION (Sequential Flow)
def process_pipeline(chatbot_id):
    try:
        print(f"\n🚀 Starting processing pipeline for chatbot: {chatbot_id}")
        # Ensure file uploads are complete before starting the pipeline
        wait_for_file_uploads(chatbot_id)
        convert_pdf_to_images(chatbot_id)
        generate_captions(chatbot_id)
        chunk_text(chatbot_id)
        embed_chunks(chatbot_id)
        print(f"\n🎉 Pipeline completed for chatbot {chatbot_id}")
        
        # Update chatbot status and dataset name
        from user_querySafe.models import Chatbot
        chatbot_obj = Chatbot.objects.get(chatbot_id=chatbot_id)
        
        # Set status to trained
        chatbot_obj.status = "trained"
        
        # Set dataset name to the vector DB filename
        vector_db_name = f"{chatbot_id}-index.index"
        chatbot_obj.dataset_name = vector_db_name
        
        chatbot_obj.save()
        print(f"✅ Chatbot {chatbot_id} updated:")
        print(f"   • Status: trained")
        print(f"   • Dataset: {vector_db_name}")
        
    except Exception as e:
        print(f"\n❌ Pipeline error for chatbot {chatbot_id}: {e}")

# ===============================================
# RUN PIPELINE IN BACKGROUND (with a simple lock to avoid duplicate runs)
_pipeline_locks = {}
def run_pipeline_background(chatbot_id):
    from threading import Thread, Lock
    lock = _pipeline_locks.setdefault(chatbot_id, Lock())
    if lock.locked():
        print(f"Pipeline already running for chatbot {chatbot_id}.")
        return
    def pipeline_wrapper():
        with lock:
            process_pipeline(chatbot_id)
    Thread(target=pipeline_wrapper, daemon=True).start()
