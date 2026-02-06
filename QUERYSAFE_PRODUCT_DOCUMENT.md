# QuerySafe — Complete Product Documentation

> **Version:** 1.0
> **Last Updated:** February 2026
> **Prepared by:** Metric Vibes
> **Classification:** Internal + Sales

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Platform Overview](#2-platform-overview)
3. [Complete Feature List](#3-complete-feature-list)
   - 3.1 [User Authentication & Onboarding](#31-user-authentication--onboarding)
   - 3.2 [Dashboard](#32-dashboard)
   - 3.3 [Chatbot Creation](#33-chatbot-creation)
   - 3.4 [Chatbot Editing & Retraining](#34-chatbot-editing--retraining)
   - 3.5 [RAG Training Pipeline](#35-rag-training-pipeline)
   - 3.6 [Chat Interface & Embeddable Widget](#36-chat-interface--embeddable-widget)
   - 3.7 [Conversation History](#37-conversation-history)
   - 3.8 [Analytics Dashboard](#38-analytics-dashboard)
   - 3.9 [Subscription & Billing](#39-subscription--billing)
   - 3.10 [Profile & Account Management](#310-profile--account-management)
   - 3.11 [Help & Support](#311-help--support)
   - 3.12 [Administration Panel](#312-administration-panel)
   - 3.13 [Email Notification System](#313-email-notification-system)
4. [Privacy & Security Promise](#4-privacy--security-promise)
   - 4.1 [Core Privacy Commitments](#41-core-privacy-commitments)
   - 4.2 [Infrastructure Security](#42-infrastructure-security-google-cloud)
   - 4.3 [Compliance Framework](#43-compliance-framework)
   - 4.4 [Trust Signals in Product](#44-trust-signals-embedded-in-product)
5. [Pricing & Plans](#5-pricing--plans)
   - 5.1 [Plan Structure](#51-plan-structure)
   - 5.2 [Plan Tiers](#52-plan-tiers)
   - 5.3 [Enterprise & On-Premise](#53-enterprise--on-premise-option)
   - 5.4 [Discounts & Trials](#54-discounts--trials)
   - 5.5 [Billing Flow](#55-billing-flow)
6. [Technical Architecture](#6-technical-architecture)
   - 6.1 [Technology Stack](#61-technology-stack)
   - 6.2 [Document Processing Pipeline](#62-document-processing-pipeline)
   - 6.3 [Chat Inference Flow](#63-chat-inference-flow)
   - 6.4 [Widget Architecture](#64-widget-architecture)
   - 6.5 [Data Models](#65-data-models)
   - 6.6 [API Endpoints](#66-api-endpoints)
   - 6.7 [Dependencies](#67-dependencies)
7. [How QuerySafe Benefits Users](#7-how-querysafe-benefits-users)
8. [Future Roadmap](#8-future-roadmap)
9. [Contact & Links](#9-contact--links)
10. [Appendix](#10-appendix)

---

## 1. Executive Summary

**QuerySafe** is a privacy-first AI chatbot builder that enables businesses to create intelligent, document-trained chatbots and embed them on their websites — without ever compromising on data privacy.

In an era where businesses need AI-powered customer support but fear their sensitive documents and customer data being used to train third-party language models, QuerySafe offers a fundamentally different approach. Every document uploaded, every conversation held, and every piece of data processed stays within a secure, isolated Google Cloud environment. Your data is **never** used for LLM training. Period.

### Core Value Proposition

| What | How |
|------|-----|
| **Privacy-First AI** | Zero LLM training on your data. AES-256 encryption. Isolated workspaces. |
| **Multi-Source Training** | Train chatbots on PDFs, Word docs, images, text files, website URLs, and sitemaps |
| **One-Line Embed** | Add an AI chatbot to any website with a single `<script>` tag |
| **Full Control** | Custom bot personality, starter questions, branding, and retraining on demand |
| **Actionable Analytics** | Track conversations, satisfaction ratings, peak hours, and top questions |
| **Enterprise Ready** | On-premise deployment, SSO, custom implementation, dedicated support |

### Target Audience

- **Small & Medium Businesses** needing AI customer support without technical complexity
- **SaaS Companies** wanting to offer in-app help powered by their documentation
- **Healthcare & Legal Firms** requiring strict data privacy compliance
- **E-commerce** businesses needing 24/7 product Q&A on their websites
- **Enterprises** seeking on-premise AI chatbot solutions with full data sovereignty

---

## 2. Platform Overview

QuerySafe is a Software-as-a-Service (SaaS) platform built on Google Cloud infrastructure, designed for production-grade reliability and enterprise-level security.

### Architecture at a Glance

```
User's Website                    QuerySafe Platform
+-------------------+            +------------------------------------------+
|                   |            |  Google Cloud Run (Serverless)            |
| <script> Widget --+--HTTPS--->|  Django 5.2 Backend                      |
|                   |            |    +---> Vertex AI (Gemini 2.0 Flash)    |
+-------------------+            |    +---> FAISS Vector Index              |
                                 |    +---> Google Cloud Storage            |
QuerySafe Console                |    +---> SentenceTransformer Embeddings  |
+-------------------+            |                                          |
| console.querysafe +--HTTPS--->|  SQLite3 Database (Persistent Volume)    |
| .in               |            |  WhiteNoise Static File Serving          |
+-------------------+            +------------------------------------------+
```

### Key URLs

| Resource | URL |
|----------|-----|
| **Console (App)** | [console.querysafe.in](https://console.querysafe.in) |
| **Marketing Website** | [querysafe.ai](https://querysafe.ai) |
| **Documentation** | [docs.querysafe.in](https://docs.querysafe.in) |
| **Privacy Policy** | [querysafe.ai/privacy](https://querysafe.ai/privacy) |

### Infrastructure Highlights

- **Compute:** Google Cloud Run — serverless, auto-scaling, zero cold-start overhead
- **AI Inference:** Google Vertex AI — Gemini 2.0 Flash for both chat and vision processing
- **Storage:** Google Cloud Storage — mounted as persistent volume for documents, indexes, and database
- **Deployment:** Containerized Docker deployment with Gunicorn WSGI server
- **Static Assets:** WhiteNoise middleware for compressed, cache-friendly static file serving
- **Security:** HTTPS everywhere, CSRF protection, secure cookies, `X-Frame-Options` headers

---

## 3. Complete Feature List

### 3.1 User Authentication & Onboarding

QuerySafe uses a custom authentication system (not Django's built-in auth) with email-based registration and OTP verification.

#### Registration Flow

1. **Sign Up** — User provides name, email, and password
   - Password confirmation validation
   - Email uniqueness check
   - Passwords are hashed using bcrypt before storage
2. **OTP Verification** — 6-digit OTP sent to email
   - OTP is valid for 10 minutes
   - Resend available after 30-second cooldown (AJAX-powered)
   - Dedicated verification page with countdown timer
3. **Account Activation** — On successful OTP verification:
   - Account status changes from `registered` to `activated`
   - `activated_at` timestamp recorded
   - Welcome email sent with dashboard link
   - Auto-login and redirect to dashboard

#### Login

- Email + password authentication
- **Legacy password migration**: Automatically detects and upgrades plain-text passwords to bcrypt hashes on successful login
- **"Remember Me"** option: Extends session expiry for persistent login
- **Post-login redirect**: If user was trying to access a protected page, redirects there after login
- **Active plan detection**: Checks for valid subscription on login

#### Session Management

- Django session-based authentication with custom `@login_required` decorator
- `@redirect_authenticated_user` decorator prevents logged-in users from accessing login/register pages
- Session stores: `user_id`, `user_name`, `user_email`

#### Onboarding Stepper

New users see a 3-step getting started guide on the dashboard:

| Step | Name | Status Logic |
|------|------|-------------|
| 1 | **Choose a Plan** | Completed when user has an active `QSPlanAllot` |
| 2 | **Create Your Chatbot** | Completed when user has at least one chatbot |
| 3 | **Embed on Website** | Completed when any chatbot status is `trained` |

- Visual progress bar showing completion percentage
- Each step has pending/done/locked icon states
- Steps link to relevant pages (subscriptions, create chatbot, my chatbots)

---

### 3.2 Dashboard

The dashboard is the central hub for authenticated users, providing an at-a-glance overview of their entire QuerySafe account.

#### Welcome Section

- Personalized greeting with user's name
- User avatar (first letter of name, gradient background)
- Active plan badge (plan name displayed)
- User metadata: User ID, email, member since date
- Quick-action "New Chatbot" button

#### Statistics Cards (4 Cards)

| Card | Metric | Sub-metric |
|------|--------|-----------|
| **Total Chatbots** | Count of all user's chatbots | Number currently in `trained` status |
| **Total Conversations** | All conversations across chatbots | Conversations started in last 24 hours |
| **Total Documents** | All uploaded documents | Documents in trained chatbots |
| **Total Messages** | All messages across conversations | Messages in last 24 hours |

Each card features:
- Material icon with gradient background
- Large number display
- Secondary metric with contextual icon
- Color-coded scheme (primary, success, info, warning)

#### Recent Chatbots Table

- Shows user's most recent chatbots
- Columns: Chatbot Name, Status (color-coded badge), Conversations count, Messages count
- Training spinner animation for bots currently being trained
- Clickable rows for quick navigation

#### Privacy Trust Banner

A prominent, expandable trust section reinforcing QuerySafe's privacy commitments:

**Always-visible trust pills:**
- AES-256 Encrypted Storage
- Zero LLM Training on Your Data
- Documents Never Leave Your Workspace
- Full Data Deletion on Request

**Expandable detail cards (click "Learn more"):**

| Card | Details |
|------|---------|
| **Zero-Training Guarantee** | Your data is processed by Google Vertex AI (Gemini) which does not use customer data for model training |
| **Isolated Data Environment** | Each chatbot's documents, vectors, and conversations are stored in completely isolated workspaces |
| **Enterprise-Grade Encryption** | AES-256 encryption at rest, TLS 1.3 in transit |
| **Right to Delete** | Request complete data deletion at any time — documents, conversations, and all derived data |

**Compliance badges strip:**
- ISO/IEC 27001
- SOC 2 Type II
- GDPR Ready
- HIPAA Ready

"Powered by Google Cloud" badge in header, with link to full Privacy Policy at querysafe.ai/privacy.

---

### 3.3 Chatbot Creation

The chatbot creation flow allows users to configure, upload training data, and deploy an AI chatbot in a single form submission.

#### Basic Details

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| **Logo** | Image upload | No | Custom chatbot avatar (max 2MB, drag-and-drop). Falls back to default logo. |
| **Chatbot Name** | Text | Yes | Display name shown in widget header and management pages |
| **Description** | Textarea | Yes | Brief description of the chatbot's purpose |
| **Bot Instructions** | Textarea | No | Custom system prompt for the AI (personality, tone, restrictions, domain focus) |
| **Starter Questions** | Textarea | No | One question per line. Displayed as clickable pills in the chat widget. |

**Bot Instructions example:**
```
You are a friendly customer support agent for an e-commerce store.
Always be polite and professional. If you don't know the answer,
suggest the customer contact support at help@example.com.
Never discuss competitor products.
```

#### Website URL Training

Users can train their chatbot on website content in addition to documents:

| Input | Description |
|-------|-------------|
| **Page URLs** | Textarea — enter one URL per line. Each URL's text content is crawled and used for training. |
| **Sitemap URL** | Single URL input with **"Preview"** button. Parses XML sitemap and shows discovered page URLs before training. |

**Sitemap Preview:** When the user enters a sitemap URL and clicks "Preview," QuerySafe:
1. Fetches and parses the XML sitemap (supports nested sitemap indexes)
2. Displays the first 20 discovered URLs
3. Shows total count if more than 20 pages exist
4. User can review before including in training

#### Training Data (Document Upload)

| Feature | Detail |
|---------|--------|
| **Upload Method** | Drag-and-drop zone + file picker button |
| **Supported Formats** | PDF, DOCX, DOC, TXT, JPG, JPEG, PNG, GIF, BMP |
| **Validation** | File type whitelist, size limit (per plan), count limit (per plan), duplicate detection |
| **Preview** | Selected files shown with name, size, and remove button |
| **Quota Display** | Shows remaining file slots and max size based on active plan |

**Trust strip** appears above the upload area:
> "Your data is safe: AES-256 encrypted | Never used for LLM training | Isolated workspace"

#### Submission

On form submission:
1. Chatbot record created in database with status `training`
2. Documents saved to disk with `{chatbot_id}_` prefix
3. URL records created as `ChatbotURL` entries
4. Background RAG pipeline triggered (threaded)
5. User redirected to "My Chatbots" page
6. Activity logged: "Created chatbot: {name}"
7. Email notification sent when training completes

---

### 3.4 Chatbot Editing & Retraining

Every chatbot can be fully edited after creation — settings, documents, URLs, and retraining.

#### Edit Page Layout

**Header Section:**
- Chatbot name with status badge (Trained/Training/Inactive/Failed)
- Last trained timestamp
- Created date
- Back button to My Chatbots

**Editable Sections:**

| Section | Capabilities |
|---------|-------------|
| **Basic Details** | Edit name, description, logo, bot instructions, starter questions |
| **Website URLs** | View existing URLs with status (crawled/error/pending), delete individual URLs, add new page URLs, add new sitemap URL with preview |
| **Existing Documents** | View list with filename + upload date, delete individual documents (AJAX with SweetAlert2 confirmation) |
| **Upload New Documents** | Same drag-and-drop interface as create, quota-aware |

#### Document Management

- Each existing document shown with:
  - Document icon
  - Filename
  - Upload date
  - Delete button (trash icon)
- Deletion is AJAX-powered:
  - SweetAlert2 confirmation dialog
  - Removes physical file from disk
  - Removes database record
  - Updates document count in UI

#### URL Management

- Each existing URL shown with:
  - Type badge (Page/Sitemap)
  - URL text
  - Status icon (green check for crawled, red X for error, yellow clock for pending)
  - Delete button
- Deletion via AJAX with confirmation

#### Save vs. Retrain

| Action | What It Does |
|--------|-------------|
| **Save Changes** | Updates chatbot settings (name, description, instructions, etc.) + uploads new documents/URLs. Does NOT retrain. |
| **Retrain Bot** | Triggers full RAG pipeline re-run. Rebuilds vector index from all current documents + URLs. SweetAlert2 confirmation required. |

On retrain:
1. Status set to `training`
2. Pipeline runs in background thread
3. `last_trained_at` updated on completion
4. Activity logged
5. Email notification sent

---

### 3.5 RAG Training Pipeline

The Retrieval-Augmented Generation (RAG) pipeline is the core engine that transforms raw documents and web content into a searchable knowledge base for each chatbot.

#### Pipeline Steps

```
Step 1: File Discovery
    ↓
Step 2: File Classification (text vs. image)
    ↓
Step 3: Text Extraction (PDF, DOCX, DOC, TXT)
    ↓
Step 4: Vision Processing (scanned PDFs, images → Gemini)
    ↓
Step 5: URL Content Extraction (web pages, sitemaps)
    ↓
Step 6: Text Chunking (LangChain splitter)
    ↓
Step 7: Embedding Generation (SentenceTransformer)
    ↓
Step 8: FAISS Index Creation & Storage
    ↓
Step 9: Status Update & Notification
```

#### Step-by-Step Detail

**Step 1 — File Discovery:**
- Scans document directory for files prefixed with `{chatbot_id}_`
- Also checks for `ChatbotURL` records in database
- If no files AND no URLs exist, pipeline returns early

**Step 2 — File Classification:**
- **Text-based:** `.pdf`, `.docx`, `.doc`, `.txt`
- **Image-based:** `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`

**Step 3 — Text Extraction:**

| Format | Method | Details |
|--------|--------|---------|
| PDF | PyMuPDF (fitz) | Extracts text per page. Pages with <50 characters flagged as "scanned" |
| DOCX | python-docx | Extracts paragraphs + table cell content |
| TXT | Plain read | Direct file content |
| DOC (legacy) | LibreOffice (Linux) or Win32COM (Windows) | Converts to PDF first, then extracts |

**Step 4 — Vision Processing:**
- Scanned PDF pages and image files are sent to Gemini 2.0 Flash Vision API
- Concurrent processing with up to 3 workers (ThreadPoolExecutor)
- Gemini extracts: text content, tables, charts, diagrams, handwritten notes
- Each page/image converted to base64 before API call

**Step 5 — URL Content Extraction:**

| Source | Process |
|--------|---------|
| **Regular URLs** | httpx GET → lxml HTML parsing → strip boilerplate tags → extract body text |
| **Sitemaps** | Parse XML → discover page URLs (max 50) → crawl each page |

Boilerplate tags removed: `script`, `style`, `nav`, `footer`, `header`, `aside`, `iframe`, `noscript`, `svg`, `form`, `button`

Crawling parameters:
- Max pages per sitemap: 50
- Delay between requests: 1 second
- Timeout per page: 15 seconds
- Minimum content length: 50 characters
- User-Agent: `QuerySafe-Bot/1.0`

**Step 6 — Text Chunking:**
- Uses LangChain `RecursiveCharacterTextSplitter`
- Chunk size: 1,500 characters
- Chunk overlap: 200 characters
- Each chunk tagged with source attribution (filename or URL)

**Step 7 — Embedding Generation:**
- Model: SentenceTransformer (loaded once, cached)
- Generates dense vector embeddings for each text chunk

**Step 8 — FAISS Index Creation:**
- Creates `IndexFlatL2` (L2/Euclidean distance) FAISS index
- Stores index file: `{chatbot_id}-index.index`
- Stores chunk metadata: `{chatbot_id}-chunks.json`
- Stores raw text: `{chatbot_id}.txt`

**Step 9 — Status Update:**
- On success: chatbot status → `trained`, `last_trained_at` → now
- On failure: chatbot status → `error`
- Activity logged in `Activity` model
- Email notification sent to user

#### Concurrency & Safety

- Each pipeline run executes in a **daemon thread**
- **Per-chatbot locking** prevents duplicate concurrent runs
- If a pipeline is already running for a chatbot, new requests are safely rejected

#### Output Files (Per Chatbot)

| File | Location | Purpose |
|------|----------|---------|
| `{id}-index.index` | `INDEX_DIR` | FAISS vector index |
| `{id}-chunks.json` | `META_DIR` | Chunk metadata (text + source) |
| `{id}.txt` | `TEXT_DIR` | Combined extracted text |
| `{id}-chunks.txt` | `CHUNK_DIR` | Debug: chunks with source labels |

---

### 3.6 Chat Interface & Embeddable Widget

The chat widget is QuerySafe's customer-facing product — a lightweight, embeddable AI chatbot that website visitors interact with directly.

#### Embedding

Website owners add a single script tag to their HTML:

```html
<script src="https://console.querysafe.in/widget/{chatbot_id}/querySafe.js"></script>
```

This loads a self-contained IIFE (Immediately Invoked Function Expression) that:
1. Injects all required HTML and CSS into the page
2. Creates the floating chat button
3. Handles all chat interactions
4. Requires zero additional dependencies from the host site

#### Widget UI Components

**Floating Action Button (FAB):**
- 56px circular button, bottom-right corner
- Purple gradient background matching QuerySafe branding
- Chat icon that transforms to close icon when open
- Subtle shadow and hover effects

**Chat Modal Window:**
- 370px width × 620px height (responsive on mobile)
- Smooth slide-up animation on open

**Header:**
- Chatbot logo/avatar (custom or default)
- Chatbot name
- Close button

**Message Area:**
- Scrollable message history
- User messages: right-aligned, purple background
- Bot messages: left-aligned, light gray background
- Timestamp on each message
- Auto-scroll to latest message

**Input Area:**
- Textarea for message composition
- Send button with arrow icon
- Enter key to send (Shift+Enter for new line)

**Starter Questions:**
- Displayed as clickable pills when chat opens
- One pill per starter question configured by chatbot owner
- Clicking a pill sends it as the first message

**Typing Indicator:**
- Animated three-dot indicator while bot is processing
- Matches bot message styling

#### Advanced Features

| Feature | Implementation |
|---------|---------------|
| **Markdown Rendering** | marked.js library — bot responses support bold, italic, lists, code blocks, links |
| **XSS Protection** | DOMPurify sanitization on all rendered content |
| **Conversation Tracking** | Unique conversation_id maintained across messages in a session |
| **Session Awareness** | Tracks session start time and message count |
| **Rate Limiting** | 10 messages per 60-second window |

#### Feedback System

The widget includes a built-in feedback collection system:

**Trigger Conditions:** Feedback prompt appears when:
- User has sent 3+ messages in the conversation
- Session has been active for 3+ seconds

**Feedback UI:**
- Star rating (1-5 stars, interactive)
- Optional text comment
- Submit button
- Submitted via AJAX to `/chat/feedback/` endpoint

**Data Stored:**
- `feedback_id` (unique, format: `FB{8 chars}`)
- Linked to conversation
- Star rating (1-5)
- Optional description text
- Timestamp

#### Trust & Branding

- **Trust bar** at bottom of chat: *"Private & secure — your data is encrypted and never used for AI training"*
- **Branding:** "Powered by QuerySafe" with link to querysafe.ai
- **Disclaimer:** "NOTE: This is AI and may make mistakes. Please verify important information."

#### CORS & Security

- Widget JS served with permissive CORS headers for cross-origin embedding
- Chat API endpoint (`/chat/`) accepts cross-origin requests
- Feedback endpoint (`/chat/feedback/`) similarly CORS-enabled
- CSRF token handling for secure form submissions

---

### 3.7 Conversation History

A WhatsApp-style conversation viewer that gives chatbot owners full visibility into every interaction.

#### Three-Panel Layout

```
+----------------+------------------+---------------------------+
| Chatbots (280) | Conversations    | Chat Thread               |
|                | (300px)          | (flex)                    |
| [Bot 1]        | [Conv #1]        | [User msg]     [timestamp]|
| [Bot 2] ←      | [Conv #2] ←      | [Bot msg]      [timestamp]|
| [Bot 3]        | [Conv #3]        | [User msg]     [timestamp]|
|                |                  |                           |
+----------------+------------------+---------------------------+
```

**Left Panel — Chatbot List:**
- Shows all user's chatbots
- Each item: circular avatar, name, status badge
- Active chatbot highlighted with purple left border
- Click to load that chatbot's conversations

**Middle Panel — Conversations:**
- Lists all conversations for selected chatbot
- Each row: numbered visitor avatar, visitor label, last message preview (10 words), time ago
- Count badge in header
- Active conversation highlighted

**Right Panel — Chat Thread:**
- Full message history for selected conversation
- User messages: left-aligned, white background
- Bot messages: right-aligned, purple background, white text
- Timestamps below each message
- Header shows chatbot name + "Visitor Chat" + start date

**Empty States:**
- No chatbot selected: "Select a chatbot" with large icon
- No conversation selected: "Select a conversation" prompt
- No conversations exist: "No conversations yet" message

**Responsive Behavior:**
- On mobile: Collapses to single-column layout
- Touch-friendly navigation

---

### 3.8 Analytics Dashboard

A comprehensive analytics system that helps chatbot owners understand usage patterns, measure satisfaction, and identify improvement opportunities.

#### Filters

| Filter | Options | Default |
|--------|---------|---------|
| **Chatbot** | Dropdown of all user's chatbots + "All Chatbots" | All Chatbots |
| **Date Range** | 7 days, 30 days, 90 days, All time | 7 days |

#### Summary Cards (4 Cards)

| Card | Main Metric | Sub-metric | Icon |
|------|------------|------------|------|
| **Conversations** | Total count | Last 24 hours | chat (blue) |
| **Messages** | Total count | User + Bot breakdown | message (cyan) |
| **Satisfaction** | Average rating /5 | Total feedback count | star (orange) |
| **Response Rate** | Percentage | Avg messages per conversation | speed (green) |

#### Charts (Powered by Chart.js)

| Chart | Type | Description |
|-------|------|-------------|
| **Conversations Over Time** | Line chart (purple) | Daily conversation count over selected period |
| **Messages Per Day** | Bar chart (cyan) | Daily message volume |
| **Peak Usage Hours** | Bar chart (orange) | Message count by hour of day (0-23) |
| **Satisfaction Distribution** | Doughnut chart (multi-color) | Breakdown of 1-5 star ratings |

All charts load dynamically via AJAX from the `/api/analytics/chart-data/` endpoint. Charts respect the selected chatbot filter and date range.

#### Top Questions Table

- Ranked list of the most frequently asked user questions
- Columns: Rank, Question text, Times asked (badge)
- Up to 20 questions displayed
- HTML-escaped for XSS protection

#### CSV Export

- **"Export CSV"** button in header
- Downloads a CSV file containing:
  - Conversation ID
  - Chatbot name
  - User session identifier
  - Started at timestamp
  - Total message count
  - Bot message count
  - User message count
- Filtered by selected chatbot and date range

---

### 3.9 Subscription & Billing

QuerySafe uses a flexible, admin-configurable plan system with Razorpay payment gateway integration for Indian Rupee (INR) transactions.

#### Plan Selection Page

- Displays available plans in a 3-column card grid
- Each plan card shows:
  - Plan name
  - Price (with strikethrough for discounted/trial plans)
  - Validity period
  - Feature checklist with check/X icons
  - CTA button ("Start Free Trial" or "Select Plan")
- **"Most Popular"** ribbon on recommended plan
- **"Current Plan"** badge and disabled button on active plan
- **Enterprise/On-Premise** card with "Contact Sales" CTA

**Feature Comparison per Plan:**
- Messages per month
- Number of chatbots
- Files per chatbot
- Maximum file size
- Gemini 2.0 Flash access
- Zero-Training Guarantee
- Remove branding (higher tiers)

#### Trial vs. Paid Plans

| Aspect | Trial Plans | Paid Plans |
|--------|------------|------------|
| `is_trial` | True | False |
| `parent_plan` | References the full-price plan | NULL |
| Price | 0.00 or reduced | Full price |
| Display | "Start {N}-Day FREE Trial" | "Select Plan" |
| Activation code | Optional (`require_act_code`) | No |

#### Billing Flow

```
1. User clicks "Select Plan"
         ↓
2. Checkout page loads (QSCheckout created)
         ↓
3. User enters billing details:
   - Full name, email, phone
   - Address, city, state, PIN
         ↓
4. QSBillingDetails saved
         ↓
   [IF amount > 0]              [IF amount = 0 (Free)]
         ↓                              ↓
5a. Razorpay order created      5b. QSOrder created with
    QSOrder with status              status 'completed'
    'pending'                         ↓
         ↓                      6b. QSPlanAllot created
6a. Razorpay checkout modal          immediately
    opens (card/UPI/netbanking)       ↓
         ↓                      7b. Redirect to success
7a. Payment callback received
    Signature verified
    QSOrder → 'completed'
         ↓
8a. QSPlanAllot created
         ↓
9. Plan activation email sent
```

#### Plan Allocation (QSPlanAllot)

When a plan is activated, a `QSPlanAllot` record is created that **snapshots** the plan's limits at the time of purchase:

| Field | Description |
|-------|-------------|
| `plan_name` | Copied from plan (frozen) |
| `no_of_bot` | Chatbot limit |
| `no_of_query` | Query limit per chatbot |
| `no_of_files` | File limit per chatbot |
| `file_size` | Max file size in MB |
| `start_date` | Date of activation |
| `expire_date` | `start_date + plan.days` |

This snapshot approach means even if the admin changes plan limits later, existing subscribers keep their original terms.

#### Razorpay Integration

- **Razorpay Checkout** embedded on the payment page
- Supports: Credit/Debit Cards, UPI, Net Banking, Wallets
- **Signature verification** on callback for payment authenticity
- Error tracking: `razorpay_error_code` and `razorpay_error_description` stored on failure
- Webhook support for asynchronous payment status updates

#### Account Usage Page

- Shows real-time usage against plan limits
- Per-chatbot breakdown:
  - Messages used / total allocated
  - Documents uploaded / total allowed
  - Usage percentage with visual indicators
- Overall plan details: name, validity, limits

#### Order History

- Complete list of all past orders
- Columns: Order ID, Plan name, Amount, Status, Payment ID, Date
- Status badges: Completed (green), Pending (yellow), Failed (red)

---

### 3.10 Profile & Account Management

#### Profile Page

**Header Card:**
- Large gradient background card
- User avatar (circular, first letter of name)
- Full name and email
- Badges: User ID, Registration Status (Activated)

**Profile Information (Left Column):**
- Full Name with person icon
- Email Address with mail icon
- Member Since with calendar icon

**Current Plan Details (Right Column):**
- Plan name with premium icon
- Valid until date with calendar icon
- Feature limits table:
  - Chatbots Allowed
  - Queries per Bot
  - Documents per Bot
  - Document Size Limit
- "Select Plan" button if no active plan

---

### 3.11 Help & Support

#### Support Ticket System

**Submission Form:**
- Pre-filled (read-only): Name, Email (from user profile)
- User fills: Subject (required), Message (required, textarea)
- Submit button sends ticket

**On submission:**
1. `HelpSupportRequest` created with status `pending`
2. Email sent to user confirming receipt
3. Email sent to admin with ticket details
4. Activity logged

**Ticket Status Tracking:**
- Status options: Pending, In Progress, Resolved, Suspended
- User's past tickets displayed below the form
- Table view (desktop) / Card view (mobile)
- Color-coded status badges

**Contact Information (Always Visible):**

| Channel | Details |
|---------|---------|
| **Email** | sales@metricvibes.com |
| **Phone** | +91 75036 59606 (Mon-Fri, 10AM-7PM) |
| **Office** | Metric Vibes, AltF Coworking, Noida |

---

### 3.12 Administration Panel

QuerySafe includes a full Django admin panel for platform administrators.

#### Registered Models (15 Total)

| Model | Admin Capabilities |
|-------|-------------------|
| **User** | View/edit users, filter by status, search by email/name |
| **Chatbot** | View/edit chatbots, filter by status, search by name |
| **ChatbotDocument** | View uploaded documents per chatbot |
| **ChatbotURL** | View/manage URL training sources, filter by status |
| **Conversation** | View conversations, filter by chatbot |
| **Message** | View messages, filter by bot/user |
| **ChatbotFeedback** | View feedback ratings and comments |
| **Activity** | View activity log, filter by type |
| **HelpSupportRequest** | Manage support tickets, update status |
| **EmailOTP** | View OTP records, verify status |
| **QSPlan** | Create/edit subscription plans, set limits and pricing |
| **QSCheckout** | View checkout sessions |
| **QSBillingDetails** | View billing information |
| **QSOrder** | View/manage orders, filter by status |
| **QSPlanAllot** | View plan allocations, check expiry dates |

---

### 3.13 Email Notification System

QuerySafe sends contextual email notifications at key moments in the user journey.

| Email | Trigger | Template |
|-------|---------|----------|
| **Registration OTP** | User registers | `email/registration-otp.html` |
| **Forgot Password OTP** | User requests password reset | `email/forgot-password-otp.html` |
| **Password Changed** | Password successfully updated | `email/password-change-successfully.html` |
| **Welcome** | Account activated after OTP | `email/welcome-user.html` |
| **Chatbot Ready** | Training pipeline completes | `email/chatbot-ready-to-use.html` |
| **Plan Activated** | Subscription plan activated | `email/plan-activate.html` |
| **Contact Submission** | Contact form submitted | `email/contact-submission.html` |
| **Support Request (User)** | Support ticket created | `email/support-request-user.html` |
| **Support Request (Admin)** | Support ticket created | `email/support-request-admin.html` |

**Email Infrastructure:**
- SMTP: Hostinger (smtp.hostinger.com, port 465, SSL)
- From: no-reply@metricvibes.com
- Admin notifications: contactmedipanshu@gmail.com
- HTML templates with professional styling

---

## 4. Privacy & Security Promise

Privacy is not a feature of QuerySafe — it is the foundation. Every architectural decision, every data flow, and every user-facing element is designed with data protection as the primary concern.

### 4.1 Core Privacy Commitments

#### Zero LLM Training Guarantee

**Your data is NEVER used to train any language model.**

- Documents uploaded to QuerySafe are processed by Google Vertex AI (Gemini), which operates under Google Cloud's enterprise data processing terms
- Google Vertex AI explicitly guarantees that customer data is not used for model training or improvement
- Unlike consumer AI tools, Vertex AI provides a contractual commitment to data isolation
- Your documents, conversations, and chatbot interactions remain your intellectual property

#### AES-256 Encryption at Rest

- All stored data (documents, database, vector indexes) is encrypted using AES-256, the same standard used by banks and government agencies
- Encryption is handled at the Google Cloud Storage layer, ensuring data is protected even if physical storage media is compromised
- Encryption keys are managed by Google Cloud's Key Management Service (KMS)

#### TLS 1.3 Encryption in Transit

- All data transmitted between users, the QuerySafe console, and the chat widget is encrypted using TLS 1.3
- This includes: document uploads, chat messages, API calls, and admin operations
- HTTPS is enforced across all endpoints
- `Strict-Transport-Security` headers ensure browsers always use secure connections

#### Isolated Workspaces

- Each chatbot's data is stored in a completely isolated environment:
  - Documents: `{chatbot_id}_` prefixed files in dedicated directory
  - Vector Index: `{chatbot_id}-index.index` — separate FAISS index per chatbot
  - Metadata: `{chatbot_id}-chunks.json` — separate metadata per chatbot
  - Conversations: Database-level foreign key isolation per chatbot
- No data crosses chatbot boundaries
- No data crosses user account boundaries

#### Minimal Data Transmission

- Only the user's query and relevant context chunks (retrieved from FAISS) are sent to Vertex AI for inference
- Full documents are NEVER sent to the AI model — only small, relevant text snippets
- Bot instructions (custom system prompt) are sent but contain no user data
- No telemetry, analytics, or usage data is shared with third parties

#### Right to Delete

- Users can request complete data deletion at any time
- Deletion covers: uploaded documents, vector indexes, chunk metadata, conversations, messages, feedback, and all derived data
- Document deletion removes both database records AND physical files from storage
- Per-document and per-URL deletion available in the edit interface

---

### 4.2 Infrastructure Security (Google Cloud)

QuerySafe runs entirely on Google Cloud Platform, leveraging Google's world-class security infrastructure:

| Layer | Google Cloud Service | Security Benefit |
|-------|---------------------|-----------------|
| **Compute** | Cloud Run | Serverless, ephemeral containers. No persistent server state. Auto-scales to zero. |
| **Storage** | Cloud Storage (Mounted) | AES-256 encryption, redundant storage, access control via IAM |
| **AI** | Vertex AI (Gemini) | Enterprise data isolation, no training on customer data |
| **Networking** | Google Cloud Load Balancer | DDoS protection, SSL termination, global edge network |
| **Database** | Persistent Volume (SQLite3) | Encrypted at rest on attached storage |

**Key point:** There are **zero third-party AI providers** in the stack. All AI processing happens through Google Vertex AI, which means your data never leaves Google's secure infrastructure.

---

### 4.3 Compliance Framework

QuerySafe's compliance posture is built on Google Cloud's certified infrastructure combined with application-level best practices:

| Standard | Status | Details |
|----------|--------|---------|
| **ISO/IEC 27001** | Via Google Cloud | Google Cloud infrastructure is ISO 27001 certified. QuerySafe inherits infrastructure-level certification. |
| **SOC 2 Type II** | Via Google Cloud | Google Cloud has SOC 2 Type II attestation. QuerySafe benefits from audited infrastructure controls. |
| **GDPR Ready** | Application Level | Data minimization, right to delete, consent management, data processing transparency |
| **HIPAA Ready** | Application Level | Isolated data environments, encryption at rest/transit, audit logging, access controls |

**Shared Responsibility Model:** Google Cloud provides certified infrastructure (physical security, network security, hardware encryption). QuerySafe implements application-level security (access controls, data isolation, secure coding, session management).

---

### 4.4 Trust Signals Embedded in Product

QuerySafe doesn't just promise privacy — it reinforces it at every touchpoint in the user journey:

| Touchpoint | Trust Signal |
|------------|-------------|
| **Dashboard** | Full privacy trust banner with expandable details, 4 guarantee cards, compliance badges strip |
| **Create Chatbot** | Inline green trust strip above file upload: "Your data is safe: AES-256 encrypted · Never used for LLM training · Isolated workspace" |
| **Edit Chatbot** | Same inline trust strip above document management |
| **Chat Widget** | Green trust bar: "Private & secure — your data is encrypted and never used for AI training" |
| **Every Page (Footer)** | Trust indicators: "AES-256 Encrypted · Zero LLM Training · SOC 2 · ISO 27001 · Privacy Policy" |
| **Pricing Page** | "Zero-Training Guarantee" listed as a feature in every plan tier |
| **Privacy Policy** | Full policy at querysafe.ai/privacy |

---

## 5. Pricing & Plans

### 5.1 Plan Structure

QuerySafe uses a flexible, admin-configurable plan system. Plans are defined in the `QSPlan` model with the following parameters:

| Parameter | Description |
|-----------|-------------|
| `plan_name` | Display name of the plan |
| `no_of_bot` | Maximum number of chatbots the user can create |
| `no_of_query` | Maximum queries (messages) allowed per chatbot |
| `no_of_file` | Maximum documents/URLs per chatbot |
| `max_file_size` | Maximum file size in MB for individual uploads |
| `amount` | Price in INR (Indian Rupees) |
| `days` | Validity period (default: 30 days) |
| `currency` | Default: INR |
| `is_trial` | Whether this is a trial/introductory version |
| `status` | Visibility: Public, Limited, Private, Personal |

### 5.2 Plan Tiers

Plans are created and managed through the Django admin panel. The typical tier structure:

#### Free Trial

- **Price:** Free (INR 0)
- **Duration:** Limited days (configurable)
- **Purpose:** Let users experience QuerySafe before committing
- **Limits:** Restricted chatbots, queries, files, and file sizes
- **Features:** Core chatbot creation, document training, basic widget

#### Starter / Basic

- **Price:** Entry-level pricing in INR
- **Duration:** 30 days (configurable)
- **Limits:** Moderate chatbot count, query volume, file uploads
- **Features:** Everything in Trial + increased limits + Gemini 2.0 Flash

#### Professional

- **Price:** Mid-tier pricing in INR
- **Duration:** 30 days (configurable)
- **Limits:** Higher chatbot count, query volume, file sizes
- **Features:** Everything in Starter + remove branding + priority support

#### Enterprise / On-Premise

- **Price:** Custom (Contact Sales)
- **Features:**
  - Custom setup on client's own server
  - User-level tokenization with SSO
  - 100% privacy guarantee (data never leaves client infrastructure)
  - Full implementation customization
  - Dedicated success manager
  - Custom SLAs and support terms

### 5.3 Enterprise & On-Premise Option

For organizations with strict data sovereignty requirements, QuerySafe offers an on-premise deployment:

| Feature | Description |
|---------|-------------|
| **Deployment** | Full QuerySafe stack deployed on client's infrastructure |
| **SSO Integration** | User-level tokenization with client's identity provider |
| **Data Sovereignty** | 100% of data stays on client's servers — nothing in the cloud |
| **Customization** | UI branding, feature toggles, custom integrations |
| **Support** | Dedicated success manager + priority engineering support |

Contact: sales@metricvibes.com or +91 75036 59606

### 5.4 Discounts & Trials

| Mechanism | How It Works |
|-----------|-------------|
| **Free Trials** | Plans with `is_trial=True` and `amount=0.00` — zero-friction sign-up, no payment required |
| **Parent Plan Reference** | Trial plans reference their `parent_plan` — pricing page shows strikethrough of full price |
| **Activation Codes** | Plans with `require_act_code=True` can be unlocked with special codes (for partner/promo offers) |
| **Plan Visibility** | `status` field controls who sees the plan: Public (everyone), Limited (select users), Private (admin-only), Personal (individual allocation) |
| **Variable Validity** | Plans can have any duration (7-day trials, 30-day monthly, 365-day annual) via the `days` field |

### 5.5 Billing Flow

**Payment Gateway:** Razorpay (India's leading payment processor)

**Supported Payment Methods:**
- Credit Cards (Visa, MasterCard, American Express, RuPay)
- Debit Cards
- UPI (Google Pay, PhonePe, etc.)
- Net Banking (all major banks)
- Wallets (Paytm, Freecharge, etc.)

**Billing Data Collected:**
- Full name
- Email address
- Phone number (optional)
- Address, City, State, PIN code (optional)

**Security:**
- Razorpay PCI DSS Level 1 compliant
- Payment signature verification on every transaction
- Error codes and descriptions stored for debugging
- No credit card data stored by QuerySafe — handled entirely by Razorpay

---

## 6. Technical Architecture

### 6.1 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Language** | Python | 3.x |
| **Web Framework** | Django | 5.2 |
| **WSGI Server** | Gunicorn | 23.0.0 |
| **Database** | SQLite3 | (Django built-in) |
| **AI Model** | Google Gemini 2.0 Flash | via Vertex AI |
| **Vision Model** | Google Gemini 2.0 Flash | via Vertex AI |
| **Embeddings** | SentenceTransformer | 4.1.0 |
| **Vector Store** | FAISS (CPU) | 1.11.0 |
| **Text Splitting** | LangChain | 0.3.24 |
| **PDF Processing** | PyMuPDF | 1.25.5 |
| **Word Processing** | python-docx | 1.1.2 |
| **URL Scraping** | httpx + lxml | 0.28.1 / 5.4.0 |
| **Payment Gateway** | Razorpay | 1.4.1 |
| **Static Files** | WhiteNoise | 6.8.2 |
| **Deep Learning** | PyTorch | 2.7.0 |
| **Task Queue** | Celery + Redis | 5.5.2 / 5.2.1 |
| **CORS** | django-cors-headers | 4.7.0 |
| **Email** | Django SMTP (Hostinger) | Built-in |

### 6.2 Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     RAG Pipeline Flow                           │
│                                                                 │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │ PDF/DOCX │──▶│ Text Extract  │──▶│                        │  │
│  │ TXT/DOC  │   │ (PyMuPDF,    │   │                        │  │
│  └──────────┘   │  python-docx)│   │   LangChain Chunker    │  │
│                 └──────────────┘   │   (1500 chars,          │  │
│  ┌──────────┐   ┌──────────────┐   │    200 overlap)         │  │
│  │ Scanned  │──▶│ Gemini 2.0   │──▶│                        │  │
│  │ PDFs,    │   │ Flash Vision │   │          │              │  │
│  │ Images   │   │ (concurrent) │   │          ▼              │  │
│  └──────────┘   └──────────────┘   │   SentenceTransformer   │  │
│                                    │   Embeddings             │  │
│  ┌──────────┐   ┌──────────────┐   │          │              │  │
│  │ URLs,    │──▶│ httpx + lxml │──▶│          ▼              │  │
│  │ Sitemaps │   │ (polite      │   │   FAISS IndexFlatL2     │  │
│  └──────────┘   │  crawling)   │   │   (Vector Store)        │  │
│                 └──────────────┘   └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Chat Inference Flow

```
User Query (from widget)
        │
        ▼
┌───────────────┐
│ Generate       │
│ Query Embedding│ (SentenceTransformer)
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ FAISS Search   │ Find top-K most similar chunks
│ (L2 Distance)  │ from chatbot's vector index
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Build Prompt   │ System: bot_instructions
│                │ Context: retrieved chunks
│                │ Query: user's question
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Gemini 2.0     │ Generate response using
│ Flash (Vertex) │ knowledge context
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Store Message  │ Save to Conversation + Message models
│ Return Response│ Send JSON to widget
└───────────────┘
```

### 6.4 Widget Architecture

The chat widget is a self-contained JavaScript application served dynamically for each chatbot:

```
GET /widget/{chatbot_id}/querySafe.js
        │
        ▼
┌──────────────────────────────────┐
│  Dynamic JS Generation            │
│  - Chatbot config injected        │
│  - IIFE wrapper (no global scope) │
│  - HTML/CSS/JS all in one file    │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│  Widget on Customer's Site        │
│  ┌────────────────────────────┐  │
│  │  FAB Button (bottom-right) │  │
│  │       ↕ toggle             │  │
│  │  Chat Modal                │  │
│  │  ├─ Header (logo + name)   │  │
│  │  ├─ Starter Questions      │  │
│  │  ├─ Message Area           │  │
│  │  ├─ Input + Send           │  │
│  │  ├─ Feedback Modal         │  │
│  │  ├─ Trust Bar              │  │
│  │  └─ Branding               │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

**External Libraries (loaded via CDN within the widget):**
- `marked.js` — Markdown to HTML rendering
- `DOMPurify` — XSS sanitization

### 6.5 Data Models

QuerySafe uses 15 Django models organized into 4 domains:

#### User & Authentication Domain

```
User
├── user_id (PK, format: PC{6 chars})
├── name
├── email (unique)
├── password (bcrypt hashed)
├── is_active
├── registration_status (registered/activated)
├── activated_at
└── created_at

EmailOTP
├── email
├── otp (6 digits)
├── created_at
├── is_verified
└── [valid for 10 minutes]
```

#### Chatbot & Knowledge Domain

```
Chatbot
├── chatbot_id (PK, format: {6 chars})
├── user → User (FK)
├── name, description
├── status (training/trained/inactive/failed)
├── logo (ImageField)
├── bot_instructions (system prompt)
├── sample_questions (newline-separated)
├── last_trained_at
└── created_at

ChatbotDocument
├── chatbot → Chatbot (FK)
├── document (FileField)
└── uploaded_at

ChatbotURL
├── chatbot → Chatbot (FK)
├── url (max 2048 chars)
├── is_sitemap (bool)
├── status (pending/crawled/error)
├── page_count (for sitemaps)
├── error_message
└── created_at
```

#### Conversation & Feedback Domain

```
Conversation
├── conversation_id (PK, format: {10 chars})
├── chatbot → Chatbot (FK)
├── user_id (session identifier)
├── started_at
└── last_updated

Message
├── conversation → Conversation (FK)
├── is_bot (bool)
├── content (text)
└── timestamp

ChatbotFeedback
├── feedback_id (PK, format: FB{8 chars})
├── conversation → Conversation (FK)
├── no_of_star (1-5)
├── description (optional text)
└── created_at
```

#### Billing & Subscription Domain

```
QSPlan
├── plan_id (PK, format: {5 chars})
├── plan_name
├── is_trial, parent_plan (self FK)
├── require_act_code
├── no_of_bot, no_of_query, no_of_file, max_file_size
├── currency (INR), amount
├── status (public/limited/private/personal)
├── days (validity period)
└── created_at, updated_at

QSCheckout
├── checkout_id (PK, format: {10 chars})
├── user → User (FK)
├── plan → QSPlan (FK)
└── created_at

QSBillingDetails
├── billing_id (PK, format: {8 chars})
├── checkout → QSCheckout (FK)
├── full_name, email, phone
├── address, city, state, pin
└── created_at

QSOrder
├── order_id (PK, format: {up to 100 chars})
├── checkout → QSCheckout (FK)
├── user → User (FK)
├── plan → QSPlan (FK)
├── amount
├── status (pending/completed/failed)
├── razorpay_payment_id
├── razorpay_signature_id
├── razorpay_error_code
├── razorpay_error_description
└── created_at, updated_at

QSPlanAllot
├── plan_allot_id (PK, format: {8 chars})
├── user → User (FK)
├── parent_plan → QSPlan (FK)
├── order → QSOrder (FK, nullable)
├── plan_name (snapshot)
├── no_of_bot, no_of_query, no_of_files, file_size (snapshots)
├── start_date, expire_date
└── created_at, updated_at
```

#### Activity & Support Domain

```
Activity
├── user → User (FK)
├── type (primary/success/info/warning)
├── title, description
├── icon (Material icon name)
└── timestamp

HelpSupportRequest
├── user → User (FK)
├── subject, message
├── status (pending/in_progress/resolved/suspended)
└── created_at, updated_at
```

### 6.6 API Endpoints

#### Public Endpoints (No Auth Required)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/login/` | Login page |
| GET | `/register/` | Registration page |
| POST | `/login/` | Authenticate user |
| POST | `/register/` | Create account |
| POST | `/verify-otp/` | Verify email OTP |
| POST | `/resend-otp/` | Resend OTP (AJAX) |
| GET | `/widget/{chatbot_id}/querySafe.js` | Serve chatbot widget JS |
| GET | `/chatbot_view/{chatbot_id}/` | Public chatbot demo page |
| POST | `/chat/` | Send chat message (CORS) |
| POST | `/chat/feedback/` | Submit feedback (CORS) |

#### Authenticated Endpoints (Login Required)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/dashboard/` | Main dashboard |
| GET | `/chatbot/my_chatbots` | List user's chatbots |
| GET/POST | `/chatbot/create/` | Create new chatbot |
| GET/POST | `/chatbot/edit/{chatbot_id}/` | Edit chatbot |
| POST | `/chatbot/delete_document/{id}/` | Delete document (AJAX) |
| POST | `/chatbot/delete_url/{id}/` | Delete URL (AJAX) |
| POST | `/chatbot/retrain/{chatbot_id}/` | Retrain chatbot |
| POST | `/chatbot/preview_sitemap/` | Preview sitemap URLs (AJAX) |
| POST | `/chatbot/change_status/` | Toggle chatbot active/inactive (AJAX) |
| GET | `/chatbot/chatbot_status/` | Poll chatbot statuses (AJAX) |
| GET | `/conversations/` | Conversation history |
| GET | `/conversations/{chatbot_id}/` | Filtered conversations |
| GET | `/conversations/{chatbot_id}/{conv_id}/` | Specific conversation |
| GET | `/analytics/` | Analytics dashboard |
| GET | `/analytics/{chatbot_id}/` | Filtered analytics |
| GET | `/api/analytics/chart-data/` | Chart data (AJAX JSON) |
| GET | `/api/analytics/export/` | CSV export |
| GET | `/profile/` | User profile |
| GET/POST | `/help-support/` | Support tickets |
| GET | `/plan/subscriptions/` | View plans |
| GET | `/plan/usage/` | Account usage |
| POST | `/plan/checkout/` | Initiate checkout |
| POST | `/plan/order-payment` | Process payment |
| GET/POST | `/plan/order-status` | Payment status |
| GET | `/plan/orders-history/` | Order history |
| GET | `/logout/` | Logout |

### 6.7 Dependencies

#### Core Framework
| Package | Version | Purpose |
|---------|---------|---------|
| Django | 5.2 | Web framework |
| gunicorn | 23.0.0 | WSGI HTTP server |
| whitenoise | 6.8.2 | Static file serving |
| django-cors-headers | 4.7.0 | Cross-origin request handling |

#### AI & Machine Learning
| Package | Version | Purpose |
|---------|---------|---------|
| google-cloud-aiplatform | 1.88.0 | Vertex AI integration |
| google-genai | 1.10.0 | Google Generative AI client |
| faiss-cpu | 1.11.0 | Vector similarity search |
| sentence-transformers | 4.1.0 | Text embedding generation |
| langchain | 0.3.24 | Text splitting and chunking |
| torch | 2.7.0 | Deep learning backend |
| transformers | 4.51.3 | Hugging Face transformer models |

#### Document Processing
| Package | Version | Purpose |
|---------|---------|---------|
| PyMuPDF | 1.25.5 | PDF text extraction |
| python-docx | 1.1.2 | Word document processing |
| fpdf2 | 2.8.3 | PDF generation |
| pillow | 11.2.1 | Image processing |
| lxml | 5.4.0 | HTML/XML parsing |

#### Networking & HTTP
| Package | Version | Purpose |
|---------|---------|---------|
| httpx | 0.28.1 | Async HTTP client (URL scraping) |
| requests | 2.32.3 | HTTP client |

#### Payments
| Package | Version | Purpose |
|---------|---------|---------|
| razorpay | 1.4.1 | Payment gateway SDK |

#### Background Processing
| Package | Version | Purpose |
|---------|---------|---------|
| celery | 5.5.2 | Distributed task queue |
| redis | 5.2.1 | Message broker for Celery |

---

## 7. How QuerySafe Benefits Users

### For Business Owners

| Benefit | Description |
|---------|-------------|
| **24/7 AI Customer Support** | Your chatbot answers customer questions around the clock, reducing support ticket volume |
| **Zero Technical Expertise Needed** | Upload documents, configure in a web interface, embed with one line of code |
| **Data Stays Private** | Unlike ChatGPT or other tools, your business documents are never used to train AI models |
| **Cost Effective** | Replace or augment human support agents with AI that scales infinitely at fixed cost |
| **Quick Setup** | From sign-up to live chatbot in under 30 minutes |

### For Developers

| Benefit | Description |
|---------|-------------|
| **One-Line Integration** | Single `<script>` tag — works with any website, CMS, or web app |
| **No Server Management** | Fully managed SaaS — no infrastructure to maintain |
| **API Access** | Chat endpoint available for custom integrations |
| **Customizable** | Bot instructions, starter questions, custom branding |
| **Analytics API** | JSON endpoints for building custom dashboards |

### For Compliance Teams

| Benefit | Description |
|---------|-------------|
| **Data Sovereignty** | All data stays within Google Cloud (or on-premise for enterprise) |
| **Audit Trail** | Complete conversation logs, activity tracking, feedback records |
| **Compliance Badges** | ISO 27001, SOC 2 Type II, GDPR Ready, HIPAA Ready |
| **Right to Delete** | Granular data deletion (per-document, per-URL, per-chatbot) |
| **No Third-Party Data Sharing** | Zero external AI providers — all processing through Vertex AI |

### For End Users (Website Visitors)

| Benefit | Description |
|---------|-------------|
| **Instant Answers** | Get accurate responses from the business's own documentation |
| **Privacy Assured** | Trust bar visible: "Private & secure — your data is encrypted and never used for AI training" |
| **Rich Responses** | Markdown-formatted answers with lists, code blocks, links |
| **Feedback Option** | Rate responses and provide comments to improve the experience |
| **Mobile Friendly** | Responsive widget works on all devices |

---

## 8. Future Roadmap

QuerySafe's development roadmap focuses on three pillars: **expanding capabilities**, **deepening integrations**, and **strengthening enterprise readiness**.

### Near-Term (Next 3-6 Months)

| Feature | Description | Impact |
|---------|-------------|--------|
| **Multi-Language Support** | Chatbots that understand and respond in multiple languages | Global market expansion |
| **Real-Time Streaming Responses** | Token-by-token response streaming for faster perceived speed | Better user experience |
| **Custom Widget Domains** | Serve widget from customer's own domain (CNAME) | Enhanced brand trust |
| **PostgreSQL Migration** | Move from SQLite3 to PostgreSQL for production scale | Better concurrency and reliability |
| **Knowledge Base Versioning** | Track training data versions, rollback to previous versions | Safer content management |

### Mid-Term (6-12 Months)

| Feature | Description | Impact |
|---------|-------------|--------|
| **API Access** | RESTful API for programmatic chatbot management and chat | Developer ecosystem |
| **Slack Integration** | Deploy chatbots directly in Slack workspaces | Enterprise collaboration |
| **Microsoft Teams Integration** | Deploy chatbots in Teams channels | Enterprise collaboration |
| **Advanced Analytics** | Funnel analysis, user drop-off tracking, conversation flow visualization | Deeper insights |
| **A/B Testing** | Test different bot instructions and measure impact on satisfaction | Optimization |
| **Conversation Handoff** | Transfer from AI to human agent when bot confidence is low | Hybrid support |

### Long-Term (12+ Months)

| Feature | Description | Impact |
|---------|-------------|--------|
| **Multi-Model Support** | Choose between Gemini, Claude, GPT for each chatbot | Flexibility |
| **White-Label Solution** | Full platform rebranding for resellers and agencies | Partner channel |
| **Webhooks** | Real-time event notifications for external integrations | Automation |
| **Custom Actions** | Chatbots that can perform actions (book appointments, submit forms) | Beyond Q&A |
| **Voice Support** | Speech-to-text input and text-to-speech output in widget | Accessibility |
| **Mobile SDKs** | Native iOS and Android SDKs for in-app chatbots | Mobile apps |

---

## 9. Contact & Links

### Product Links

| Resource | URL |
|----------|-----|
| **QuerySafe Console** | [console.querysafe.in](https://console.querysafe.in) |
| **Marketing Website** | [querysafe.ai](https://querysafe.ai) |
| **Documentation** | [docs.querysafe.in](https://docs.querysafe.in) |
| **Privacy Policy** | [querysafe.ai/privacy](https://querysafe.ai/privacy) |

### Contact Information

| Channel | Details |
|---------|---------|
| **Sales Email** | sales@metricvibes.com |
| **Phone** | +91 75036 59606 (Mon-Fri, 10AM-7PM IST) |
| **Office** | Metric Vibes, AltF Coworking, Noida, India |

### Company

**Metric Vibes** — The company behind QuerySafe. Building AI-powered tools for businesses that take data privacy seriously.

---

## 10. Appendix

### A. Supported File Formats

| Format | Extension | Processing Method |
|--------|-----------|-------------------|
| PDF (text) | .pdf | PyMuPDF text extraction |
| PDF (scanned) | .pdf | Gemini 2.0 Flash Vision |
| Word Document | .docx | python-docx paragraph + table extraction |
| Legacy Word | .doc | LibreOffice/Win32COM conversion → PDF pipeline |
| Plain Text | .txt | Direct file read |
| JPEG Image | .jpg, .jpeg | Gemini 2.0 Flash Vision |
| PNG Image | .png | Gemini 2.0 Flash Vision |
| GIF Image | .gif | Gemini 2.0 Flash Vision |
| BMP Image | .bmp | Gemini 2.0 Flash Vision |

### B. ID Format Reference

| Entity | Format | Example | Length |
|--------|--------|---------|--------|
| User ID | `PC` + 6 alphanumeric | `PC4x8mN2` | 8 |
| Chatbot ID | 6 alphanumeric | `a3Kp9z` | 6 |
| Conversation ID | 10 alphanumeric | `xY7kL2mN9p` | 10 |
| Feedback ID | `FB` + 8 alphanumeric | `FB3kP9x2Lm` | 12 (max) |
| Checkout ID | 10 alphanumeric | `aB3kP9x2Lm` | 10 |
| Billing ID | 8 alphanumeric | `aB3kP9x2` | 8 (max) |
| Plan Allot ID | 8 alphanumeric | `x7kL2mN9` | 8 |

### C. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | `local` or `production` |
| `DEBUG` | `False` | Django debug mode |
| `SECRET_KEY` | — | Django secret key |
| `PROJECT_NAME` | `QuerySafe` | Application name |
| `PROJECT_ID` | — | Google Cloud project ID |
| `REGION` | — | Google Cloud region |
| `DATABASE_NAME` | `db.sqlite3` | Database filename |
| `GEMINI_CHAT_MODEL` | `gemini-2.0-flash-001` | Chat model name |
| `GEMINI_VISION_MODEL` | `gemini-2.0-flash-001` | Vision model name |
| `RAZORPAY_KEY_ID` | — | Razorpay API key |
| `RAZORPAY_KEY_SECRET` | — | Razorpay secret key |
| `RAZORPAY_WEBHOOK_SECRET` | — | Razorpay webhook secret |
| `EMAIL_HOST` | `smtp.hostinger.com` | SMTP host |
| `EMAIL_PORT` | `465` | SMTP port |
| `EMAIL_HOST_USER` | `no-reply@metricvibes.com` | SMTP username |
| `EMAIL_HOST_PASSWORD` | — | SMTP password |
| `ADMIN_EMAIL` | `contactmedipanshu@gmail.com` | Admin notification email |
| `WEBSITE_URL` | — | Base URL for widget script |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost,...` | Django allowed hosts |
| `CSRF_TRUSTED_ORIGINS` | `https://console.querysafe.in,...` | CSRF trusted origins |

### D. Security Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | Cloud Run SSL proxy |
| `SESSION_COOKIE_SECURE` | `True` | HTTPS-only session cookies |
| `CSRF_COOKIE_SECURE` | `True` | HTTPS-only CSRF cookies |
| `SECURE_SSL_REDIRECT` | `False` | Handled by Cloud Run |
| Password Hashing | bcrypt | Via `hashlib` + `os.urandom` salt |
| Rate Limiting | 10 msg/60s | Per-session chat rate limit |
| OTP Expiry | 10 minutes | Email verification OTP |
| OTP Resend Cooldown | 30 seconds | Prevents OTP abuse |

### E. Template Inventory (34 Templates)

**User-Facing Pages (19):**
dashboard.html, my_chatbots.html, create_chatbot.html, edit_chatbot.html, chatbot-widget.html, chatbot-view.html, conversations.html, analytics.html, subscriptions.html, profile.html, help-support.html, order_history.html, usage.html, payment_page.html, payment_checkout.html, payment_status.html, login.html, register.html, verify_otp.html

**Layout & Include (6):**
include/base.html, include/auth-base.html, include/header-nav.html, include/aside.html, include/footer.html, include/_trust_strip.html

**Email Templates (9):**
email/registration-otp.html, email/forgot-password-otp.html, email/password-change-successfully.html, email/welcome-user.html, email/chatbot-ready-to-use.html, email/plan-activate.html, email/contact-submission.html, email/support-request-user.html, email/support-request-admin.html

---

*This document is maintained by the QuerySafe engineering team at Metric Vibes. For questions or updates, contact the development team.*

*Last generated: February 2026*
