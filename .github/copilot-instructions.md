# QuerySafe Copilot Instructions

## Project Overview
**QuerySafe** is a Django-based SaaS platform for building AI chatbots trained on user-provided documents. The system combines document processing (PDF/DOCX/images), vector embeddings, and Google Vertex AI for semantic search and generative responses.

### Key Architecture
- **Frontend**: Django templates with Material Dashboard CSS, interactive JS widgets
- **Backend**: Django 5.2 with custom User model (not Django auth), SQLite3 database
- **AI/ML**: Google Vertex AI Gemini + sentence-transformers embeddings + FAISS vector index
- **Document Pipeline**: PDF extraction → OCR → text chunking → embeddings → vector storage
- **Task Queue**: Celery for background document processing

---

## Critical Components & Data Flow

### 1. **User Authentication System** (`user_querySafe/models.py`, `user_querySafe/views.py`)
- **Custom User Model**: `User` with `user_id` (auto-generated "PC" prefix IDs), email, password stored as plain text (security concern)
- **Flow**: Register → OTP email verification (`EmailOTP`) → user activated → login via session
- **Key Patterns**:
  - Session-based auth: `request.session['user_id']` stores user ID, checked via `@login_required` decorator
  - OTP valid for 10 minutes, 6-digit code
  - Activation codes for self-service registration (up to 5 uses)
  - Activity logging via `Activity.log()` for audit trail

### 2. **Chatbot & Document Processing** (`user_querySafe/models.py`, `user_querySafe/chatbot/pipeline_processor.py`)
- **Chatbot Model**: Has `chatbot_id` (6-char alphanumeric), user FK, name, status (training/ready)
- **Document Pipeline** (`pipeline_processor.py`):
  1. File upload → rename with chatbot_id prefix → store in `documents/files_uploaded/`
  2. Extract text: PDF (PyMuPDF) → split to images → OCR (Google Gemini vision) → text extraction
  3. Text chunking: `RecursiveCharacterTextSplitter` (langchain) with overlapping chunks
  4. Embeddings: `sentence-transformers/all-MiniLM-L6-v2` model → 384-dim vectors
  5. Storage: FAISS `.index` file + JSON metadata in `documents/vector_index/` and `documents/chunk-metadata/`
- **Trigger**: Automatic via `run_pipeline_background()` when `ChatbotDocument.save()`

### 3. **Chat & Query Resolution** (`user_querySafe/views.py` - `chat_message()`)
- **Query Flow**: User message → embedding with same model → FAISS similarity search → retrieve top chunks → Vertex AI Gemini context + query → bot response
- **Storage**: `Conversation` (per session/user + chatbot) → `Message` (bot=True/False)
- **Key Pattern**: Semantic search chains retrieved chunks for RAG-style responses

### 4. **Subscription & Usage Limits** (`user_querySafe/models.py`)
- **Models**: `SubscriptionPlan` (master plans) → `UserPlanAlot` (per-user allocations with expiry)
- **Limits Enforced**: Max chatbots, queries per bot, documents per bot, doc size
- **Validation Points**: Chatbot creation, document upload (`views.py` - `create_chatbot()`)

### 5. **Widget & Public Interface** (`user_querySafe/views.py` - `chatbot_view()`, `serve_widget_js()`)
- **Embedded Widget**: `snippet_code` property generates iframe-injectable JS code
- **Public Chat**: Chatbot accessible without auth if `chatbot_id` is known, tracked by `user_id` (session/IP)
- **CORS Enabled**: Headers set for cross-domain widget embedding

---

## Project-Specific Conventions

### Naming & ID Generation
- **User IDs**: "PC" + 3-6 random alphanumerics (e.g., `PC0J05C7`)
- **Chatbot IDs**: 6-char alphanumeric (e.g., `GSQCJ2`)
- **Conversation IDs**: 10-char alphanumeric, unique globally
- **File Names**: `{chatbot_id}_{original_filename}` to avoid collisions

### Directory Structure
```
documents/
├── files_uploaded/      # Raw uploaded documents
├── files_images/        # Extracted images from PDFs
├── files_captions/      # OCR text from images
├── files_chunks/        # Text chunks (metadata backup)
├── vector_index/        # FAISS index files (.index)
└── chunk-metadata/      # Chunk metadata as JSON
```

### Database & Schema
- SQLite3 primary database, no migrations visible (assume `0001_initial.py` covers all)
- Custom storage: `FileSystemStorage(location=documents/files_uploaded/)`
- ForeignKeys use `on_delete=models.CASCADE` (chatbots/conversations deleted with user)

### Authentication & Decorators
- **Custom Decorators**:
  - `@login_required`: Checks `request.session['user_id']`, redirects to login with `next_url` stored
  - `@redirect_authenticated_user`: Redirects logged-in users away from auth pages
  - No Django's built-in `@login_required` - use app's custom version

### Error Handling & Messaging
- Uses Django messages framework (`messages.error/success/info/warning`)
- HTML `alert-link` class for inline action links in messages

---

## Critical Workflows

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations (if needed)
python manage.py migrate

# Start development server
python manage.py runserver

# Test with local SQLite DB
```

### Production Deployment
- **Deployment**: Gunicorn + Nginx (see readme.md for config)
- **Socket**: `unix:/home/querysafe/querysafe.sock`
- **Static/Media**: Nginx serves from `/staticfiles/` and `/media/`
- **Restart Commands**:
  ```bash
  sudo systemctl restart gunicorn
  sudo systemctl restart nginx
  sudo journalctl -u gunicorn -f  # Live logs
  ```

### Key Environment Variables (`.env`)
- `SECRET_KEY`: Django secret
- `DEBUG`: 'True'/'False'
- `ALLOWED_HOSTS`: Comma-separated (no protocol)
- `WEBSITE_URL`: Base URL for widget code generation
- `PROJECT_ID`, `REGION`: Google Vertex AI credentials
- `EMAIL_*`: SMTP settings (Hostinger SSL on port 465)

### Document Processing Background Jobs
- Triggered immediately on upload via `run_pipeline_background(chatbot_id)`
- **Wait Logic**: `wait_for_file_uploads()` detects when file writes stabilize before processing
- Status transitions: `training` → `ready` on pipeline completion

---

## Integration Points

### Google Vertex AI
- **Client**: `genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)`
- **Models**: `sentence-transformers` for embeddings, Gemini for OCR + generation
- **Usage**: Vision API (image → text), text generation API (chat responses)

### External Dependencies
- **LangChain**: Text splitting, no LLM chains used (direct API calls)
- **FAISS**: Vector similarity search (CPU version)
- **sentence-transformers**: Dense embeddings
- **PyMuPDF (fitz)**: PDF text extraction
- **Pillow + python-docx**: Image/document handling

---

## Code Patterns to Follow

### Models & Auto-Generated IDs
```python
def save(self, *args, **kwargs):
    if not self.id_field:
        while True:
            new_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not ModelName.objects.filter(id_field=new_id).exists():
                self.id_field = new_id
                break
    super().save(*args, **kwargs)
```

### File Upload with Custom Storage
```python
document = models.FileField(upload_to='', storage=custom_storage)
# Rename before save, construct with prefix: `{chatbot_id}_{original}`
```

### Session-Based View Protection
```python
@login_required
def protected_view(request):
    user = User.objects.get(user_id=request.session['user_id'])
    # ...
```

### Async Pipeline Trigger
```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    run_pipeline_background(self.chatbot.chatbot_id)  # Background job
```

---

## Common Debugging Points

1. **File Upload Issues**: Check `documents/files_uploaded/` permissions and `wait_for_file_uploads()` timing
2. **Embedding Mismatch**: Ensure same `sentence-transformers` model version for training & querying
3. **FAISS Index Corruption**: Delete `.index` file and regenerate via document re-upload
4. **OTP Expiry**: 10-minute window; resend creates new OTP and deletes old via `EmailOTP.objects.filter(...).delete()`
5. **Session Loss**: Check `MIDDLEWARE` order and `SESSION_COOKIE_HTTPONLY`; custom session check via `'user_id' in request.session`

---

## Quick Reference: Key Files
- **Models**: `user_querySafe/models.py` (~380 lines, all model definitions)
- **Main Views**: `user_querySafe/views.py` (~777 lines, auth + dashboard + chat)
- **Pipeline**: `user_querySafe/chatbot/pipeline_processor.py` (~478 lines, OCR + embedding + indexing)
- **Chatbot Views**: `user_querySafe/chatbot/views.py` (~164 lines, creation + status)
- **Settings**: `querySafe/settings.py` (FAISS paths, Vertex AI config, email SMTP)
- **URLs**: `querySafe/urls.py` (root), `user_querySafe/urls.py` (app), `user_querySafe/chatbot/urls.py` (chatbot routes)

