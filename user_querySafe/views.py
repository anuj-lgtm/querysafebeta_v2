from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import RegisterForm, OTPVerificationForm  # Remove LoginForm
from .models import Activity, User, Chatbot, ChatbotDocument, Conversation, Message, ChatbotFeedback, EmailOTP, QSPlanAllot, HelpSupportRequest
from django.http import JsonResponse, HttpResponse  # Import HttpResponse
import json
from django.views.decorators.csrf import csrf_exempt
import os
import faiss
from google import genai
from user_querySafe.chatbot.embedding_model import get_embedding_model
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate, ExtractHour
import csv
from django.core.mail import send_mail
import random
from django.template.loader import render_to_string
from .decorators import redirect_authenticated_user, login_required
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.urls import reverse
from django.db import models
import time  # Import the time module
import requests as http_requests  # renamed to avoid conflict with django request

# Initialize Gemini client (embedding model loaded lazily via singleton)
client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location=settings.REGION)

# OTP Genration 
def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

# Authentication system pages views
@redirect_authenticated_user
def register_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validation
        if not all([name, email, password, confirm_password]):
            messages.error(request, 'Please fill in all fields')
            return redirect('register')

        # Check if user exists
        try:
            existing_user = User.objects.get(email=email)
            request.session['pending_activation_user_id'] = existing_user.user_id

            if not existing_user.is_active:
                messages.info(request, 'Please complete your email verification.')
                return redirect('verify_otp')
            else:
                messages.error(request, 'Email already registered! Please login.')
                return redirect('login')
        except User.DoesNotExist:
            # Create inactive user and hash password
            user = User(
                name=name,
                email=email,
                is_active=False,
                registration_status='registered'
            )
            user.set_password(password)
            user.save()

            # Generate and send OTP
            otp = generate_otp()
            EmailOTP.objects.filter(email=email).delete()
            EmailOTP.objects.create(email=email, otp=otp)
            
            verification_url = request.build_absolute_uri(reverse('verify_otp'))
            send_otp_email(email, otp, name, verification_url)
            
            request.session['pending_activation_user_id'] = user.user_id
            messages.success(request, 'Please check your email for the OTP verification code.')
            return redirect('verify_otp')

    return render(request, 'user_querySafe/register.html', {
        'google_enabled': bool(settings.GOOGLE_CLIENT_ID),
    })

@redirect_authenticated_user
def verify_otp_view(request):
    if 'pending_activation_user_id' not in request.session:
        return redirect('register')

    try:
        user = User.objects.get(user_id=request.session['pending_activation_user_id'])
    except User.DoesNotExist:
        return redirect('register')

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']

            try:
                email_otp = EmailOTP.objects.get(email=user.email, is_verified=False)
                if email_otp.is_valid():
                    if email_otp.otp == entered_otp:
                        user.is_active = True
                        user.registration_status = 'activated'
                        user.activated_at = timezone.now()
                        user.save()
                        
                        # Mark OTP as verified
                        email_otp.is_verified = True
                        email_otp.save()
                        
                        # Set user session
                        request.session['user_id'] = user.user_id
                        
                        # Build dashboard URL for welcome email
                        dashboard_url = request.build_absolute_uri(reverse('dashboard'))
                        
                        # Send welcome email
                        send_welcome_email(user.email, user.name, dashboard_url)
                        
                        # Clear activation session
                        if 'pending_activation_user_id' in request.session:
                            del request.session['pending_activation_user_id']
                        
                        messages.success(request, 'Account verified successfully! Welcome to QuerySafe.')
                        return redirect('dashboard')
                    else:
                        messages.error(request, 'Invalid OTP. Please try again.')
                else:
                    messages.error(request, 'OTP has expired. Please request a new one.')
            except EmailOTP.DoesNotExist:
                messages.error(request, 'No valid OTP found. Please request a new one.')
    else:
        form = OTPVerificationForm()
    
    return render(request, 'user_querySafe/verify_otp.html', {'form': form, 'user': user})

@require_http_methods(["POST"])
@csrf_exempt
def resend_otp_view(request):
    if request.method == 'POST':
        try:
            if 'pending_activation_user_id' not in request.session:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid session. Please register again.'
                })

            user = User.objects.get(user_id=request.session['pending_activation_user_id'])
            
            # Add rate limiting using cache
            cache_key = f'resend_otp_{user.email}'
            if cache.get(cache_key):
                return JsonResponse({
                    'success': False,
                    'message': 'Please wait before requesting another OTP.'
                })
            
            # Set cache to prevent duplicate requests
            cache.set(cache_key, True, 30)  # 30 seconds cooldown
            
            # Generate new OTP
            otp = generate_otp()
            
            # Delete any existing OTP
            EmailOTP.objects.filter(email=user.email).delete()
            
            # Create new OTP
            EmailOTP.objects.create(email=user.email, otp=otp)
            
            # Send OTP email
            verification_url = request.build_absolute_uri(reverse('verify_otp'))
            if send_otp_email(user.email, otp, user.name, verification_url):
                return JsonResponse({
                    'success': True,
                    'message': 'OTP sent successfully!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Failed to send OTP. Please try again.'
                })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found. Please register again.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

# ── Google OAuth 2.0 ──────────────────────────────────────────────
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
GOOGLE_SCOPES = 'openid email profile'


@redirect_authenticated_user
def google_login_redirect(request):
    """Redirect user to Google OAuth consent screen."""
    client_id = settings.GOOGLE_CLIENT_ID
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    if not client_id or not redirect_uri:
        messages.error(request, 'Google Sign-In is not configured.')
        return redirect('login')

    import hashlib, secrets
    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': GOOGLE_SCOPES,
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account',
    }
    from urllib.parse import urlencode
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)


@redirect_authenticated_user
def google_callback(request):
    """Handle the callback from Google OAuth."""
    # Validate state to prevent CSRF
    state = request.GET.get('state')
    stored_state = request.session.pop('google_oauth_state', None)

    if not state or state != stored_state:
        messages.error(request, 'Invalid authentication state. Please try again.')
        return redirect('login')

    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        messages.error(request, f'Google sign-in was cancelled or failed.')
        return redirect('login')

    if not code:
        messages.error(request, 'No authorization code received from Google.')
        return redirect('login')

    # Exchange authorization code for tokens
    try:
        token_response = http_requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        }, timeout=10)

        if token_response.status_code != 200:
            messages.error(request, 'Failed to authenticate with Google. Please try again.')
            return redirect('login')

        tokens = token_response.json()
        access_token = tokens.get('access_token')

        if not access_token:
            messages.error(request, 'Failed to get access token from Google.')
            return redirect('login')

    except Exception:
        messages.error(request, 'Could not connect to Google. Please try again.')
        return redirect('login')

    # Fetch user info from Google
    try:
        userinfo_response = http_requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )

        if userinfo_response.status_code != 200:
            messages.error(request, 'Failed to fetch your Google profile.')
            return redirect('login')

        userinfo = userinfo_response.json()
        email = userinfo.get('email')
        name = userinfo.get('name', '')
        email_verified = userinfo.get('email_verified', False)

        if not email:
            messages.error(request, 'Could not retrieve email from Google.')
            return redirect('login')

        if not email_verified:
            messages.error(request, 'Your Google email is not verified.')
            return redirect('login')

    except Exception:
        messages.error(request, 'Error retrieving your Google profile.')
        return redirect('login')

    # Find or create user
    try:
        user = User.objects.get(email=email)
        # Existing user — check if active
        if not user.is_active:
            # Auto-activate since Google has verified their email
            user.is_active = True
            user.registration_status = 'activated'
            user.activated_at = timezone.now()
            user.save()
    except User.DoesNotExist:
        # Create new user — auto-activated (Google verified email)
        user = User(
            name=name or email.split('@')[0],
            email=email,
            is_active=True,
            registration_status='activated',
            activated_at=timezone.now(),
        )
        user.set_password(None)  # No password for Google users
        user.save()

    # Set session
    request.session['user_id'] = user.user_id
    request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days

    # Check for active plan
    active_plan = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()

    if active_plan:
        request.session['active_plan'] = active_plan.plan_name
    else:
        request.session['active_plan'] = "No active plan"

    messages.success(request, f'Welcome, {user.name}!')
    return redirect('dashboard')


@redirect_authenticated_user
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me') == 'on'

        if not email or not password:
            messages.error(request, 'Please fill in all fields')
            return redirect('login')

        try:
            user = User.objects.get(email=email)
            # Verify password using hashed value; support legacy plain-text migration
            password_ok = False
            try:
                password_ok = user.check_password(password)
            except Exception:
                password_ok = False

            if not password_ok:
                # One-time migration for legacy plain-text passwords:
                # Only attempt if the stored value doesn't look like a Django hash
                # (Django hashes always contain '$' separators like "pbkdf2_sha256$...")
                if '$' not in user.password and user.password == password:
                    user.set_password(password)
                    user.save()
                    password_ok = True

            if password_ok:
                if user.is_active:
                    request.session['user_id'] = user.user_id

                    # Set session expiry based on remember_me
                    if remember_me:
                        # Set session expiry to 30 days
                        request.session.set_expiry(30 * 24 * 60 * 60)
                    else:
                        # Set session expiry to browser close
                        request.session.set_expiry(0)

                    # Check for active plan
                    active_plan = QSPlanAllot.objects.filter(
                        user=user,
                        expire_date__gte=timezone.now().date()
                    ).order_by('-created_at').first()
                    
                    if active_plan:
                        request.session['active_plan'] = active_plan.plan_name
                    else:
                        request.session['active_plan'] = "No active plan"

                    messages.success(request, f'Welcome back, {user.name}!')
                    return redirect('dashboard')
                else:
                    # If user exists but not active, send to OTP verification
                    request.session['pending_activation_user_id'] = user.user_id
                    messages.info(request, 'Please complete your email verification.')
                    return redirect('verify_otp')
            else:
                messages.error(request, 'Invalid password')
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email')

    # For GET requests, just render the login page
    return render(request, 'user_querySafe/login.html', {
        'google_enabled': bool(settings.GOOGLE_CLIENT_ID),
    })

def logout_view(request):
    if 'user_id' in request.session:
        del request.session['user_id']
        messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

def forget_password_view(request):
    # This view can be implemented later for password reset functionality
    messages.info(request, 'This feature is under development.')

# Portal pages views
@login_required
def dashboard_view(request):
    user = User.objects.get(user_id=request.session['user_id'])
    
    # Get user's chatbots
    chatbots = Chatbot.objects.filter(user=user)
    
    # Calculate metrics
    total_chatbots = chatbots.count()
    trained_chatbots = chatbots.filter(status='trained').count()
    
    # Get conversations data
    total_conversations = Conversation.objects.filter(chatbot__in=chatbots).count()
    last_24h = timezone.now() - timedelta(days=1)
    recent_conversations = Conversation.objects.filter(
        chatbot__in=chatbots,
        started_at__gte=last_24h  # Changed from created_at to started_at
    ).count()
    
    # Get documents data
    total_documents = ChatbotDocument.objects.filter(chatbot__in=chatbots).count()
    trained_documents = ChatbotDocument.objects.filter(
        chatbot__in=chatbots.filter(status='trained')
    ).count()
    
    # Get messages data
    # Get messages data
    total_messages = Message.objects.filter(conversation__chatbot__in=chatbots, is_bot=True).count()
    messages_last_24h = Message.objects.filter(
        conversation__chatbot__in=chatbots, 
        is_bot=True,
        timestamp__gte=last_24h
    ).count()
    
    # Get recent chatbots with their stats
    recent_chatbots = chatbots.annotate(
        total_messages=Count('conversations__messages', filter=models.Q(conversations__messages__is_bot=True))
    ).order_by('-id')[:5]  # Changed from created_at to id for ordering
    
    # ── Onboarding progress ──────────────────────────────────────────
    has_active_plan = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date(),
    ).exists()
    has_chatbot = total_chatbots > 0
    has_trained_bot = trained_chatbots > 0

    steps_complete = sum([has_active_plan, has_chatbot, has_trained_bot])
    # Show stepper until the user has at least one trained bot
    show_onboarding = not has_trained_bot

    context = {
        'user': user,
        'total_chatbots': total_chatbots,
        'trained_chatbots': trained_chatbots,
        'total_conversations': total_conversations,
        'recent_conversations': recent_conversations,
        'total_documents': total_documents,
        'trained_documents': trained_documents,
        'total_messages': total_messages,
        'messages_last_24h': messages_last_24h,
        'recent_chatbots': recent_chatbots,
        # Onboarding
        'show_onboarding': show_onboarding,
        'has_active_plan': has_active_plan,
        'has_chatbot': has_chatbot,
        'has_trained_bot': has_trained_bot,
        'steps_complete': steps_complete,
    }

    return render(request, 'user_querySafe/dashboard.html', context)

@login_required
def conversations_view(request, chatbot_id=None, conversation_id=None):
    user = User.objects.get(user_id=request.session['user_id'])
    chatbots = Chatbot.objects.filter(user=user)
    
    selected_bot = None
    conversations = []
    selected_conversation = None
    messages = []
    
    if chatbot_id:
        selected_bot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)
        conversations = Conversation.objects.filter(chatbot=selected_bot).order_by('-last_updated')
        
        # Add last message to each conversation
        for conv in conversations:
            last_msg = Message.objects.filter(conversation=conv).last()
            conv.last_message = last_msg.content if last_msg else ""
            conv.unread_count = Message.objects.filter(
                conversation=conv, 
                is_bot=True, 
                timestamp__gt=conv.last_updated
            ).count()
        
        if conversation_id:
            selected_conversation = get_object_or_404(Conversation, conversation_id=conversation_id, chatbot=selected_bot)
            messages = Message.objects.filter(conversation=selected_conversation).order_by('timestamp')
        elif conversations.exists():
            selected_conversation = conversations.first()
            messages = Message.objects.filter(conversation=selected_conversation).order_by('timestamp')
    
    context = {
        'chatbots': chatbots,
        'selected_bot': selected_bot,
        'conversations': conversations,
        'selected_conversation': selected_conversation,
        'messages': messages,
    }
    
    return render(request, 'user_querySafe/conversations.html', context)

def chatbot_view(request, chatbot_id):
    # Get the chatbot or return 404
    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id)
    
    # Only allow access if chatbot is trained
    if chatbot.status != 'trained':
        messages.error(request, 'This chatbot is not ready yet.')
        return redirect('my_chatbots')
    
    # Parse sample questions (newline-separated)
    sample_questions = []
    if hasattr(chatbot, 'sample_questions') and chatbot.sample_questions.strip():
        sample_questions = [q.strip() for q in chatbot.sample_questions.strip().split('\n') if q.strip()][:4]

    context = {
        'chatbot': chatbot,
        'chatbot_name': chatbot.name,
        'chatbot_logo': chatbot.logo.url if chatbot.logo else None,
        'chatbot_id': chatbot.chatbot_id,
        'sample_questions': sample_questions,
    }

    return render(request, 'user_querySafe/chatbot-view.html', context)

@csrf_exempt
def chat_message(request):
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        return response

    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('query', '').strip()
        chatbot_id = data.get('chatbot_id')
        conversation_id = data.get('conversation_id')

        # Input validation
        if not user_message or not chatbot_id:
            return JsonResponse({'error': 'Missing required fields: query and chatbot_id'}, status=400)
        if len(user_message) > 5000:
            return JsonResponse({'error': 'Message is too long. Maximum 5000 characters.'}, status=400)

        # Ensure we have a session
        if not request.session.session_key:
            request.session.create()
        session_id = request.session.session_key

        # Get chatbot
        chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id)

        # Check if chatbot is trained
        if chatbot.status != 'trained':
            return JsonResponse({
                'error': 'This chatbot is still in training or not ready. Please try again later.',
                'status': chatbot.status
            }, status=400)

        # Get user's active plan
        user = chatbot.user
        active_plan = QSPlanAllot.objects.filter(
            user=user,
            expire_date__gte=timezone.now().date()
        ).order_by('-created_at').first()

        if not active_plan:
            return JsonResponse({
                'error': 'No active plan found. Please subscribe to a plan to continue using the chatbot.'
            })

        # Check query limit BEFORE processing
        # Count total bot responses for this chatbot (across ALL visitors/conversations)
        total_bot_responses = Message.objects.filter(
            conversation__chatbot=chatbot,
            is_bot=True
        ).count()
        
        if total_bot_responses >= active_plan.no_of_query:
            return JsonResponse({
                'error': 'This chatbot has reached its query limit. Please contact the chatbot owner to upgrade their plan.',
                'limit_reached': True
            }, status=429)

        # Get or create conversation
        try:
            if conversation_id:
                conversation = Conversation.objects.get(conversation_id=conversation_id)
            else:
                conversation = Conversation.objects.create(
                    chatbot=chatbot,
                    user_id=session_id
                )
            print(f"Created new conversation: {conversation.conversation_id}")
        except Conversation.DoesNotExist:
            conversation = Conversation.objects.create(
                chatbot=chatbot,
                user_id=session_id
            )
            print(f"Created new conversation: {conversation.conversation_id}")

        # Save visitor email if provided (lead capture)
        visitor_email = data.get('visitor_email', '').strip()
        if visitor_email and not conversation.visitor_email:
            conversation.visitor_email = visitor_email
            conversation.save()

        # Rate limiting: reject excessive requests instead of blocking the worker
        cache_key = f'chat_message_count_{conversation.user_id}'
        message_count = cache.get(cache_key, 0)

        if message_count >= 10:
            response = JsonResponse({
                'error': 'Too many messages. Please wait a moment before sending another.',
                'retry_after': 60
            }, status=429)
            response['Access-Control-Allow-Origin'] = '*'
            response['Retry-After'] = '60'
            return response

        cache.set(cache_key, message_count + 1, 60)  # Reset count every 60 seconds

        # Store user message
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            is_bot=False
        )
        print(f"Stored user message in conversation: {conversation.conversation_id}")

        # Get chat history (last 5 messages)
        chat_history = Message.objects.filter(conversation=conversation).order_by('-timestamp')[:5]
        chat_context = "\n".join([
            f"{'Bot' if msg.is_bot else 'User'}: {msg.content}"
            for msg in reversed(chat_history)
        ])
        
        # Get vector search results
        index_path = os.path.join(settings.INDEX_DIR, f"{chatbot_id}-index.index")
        meta_path = os.path.join(settings.META_DIR, f"{chatbot_id}-chunks.json")

        if not os.path.exists(index_path) or not os.path.exists(meta_path):
            return JsonResponse({'error': 'Chatbot data not found'}, status=404)

        index = faiss.read_index(index_path)
        with open(meta_path, 'r', encoding='utf-8') as f:
            chunk_data = json.load(f)

        query_vector = get_embedding_model().encode([user_message]).astype('float32')
        k = 8
        distances, indices = index.search(query_vector, k)

        # Backward-compatible: handle both old ["str"] and new [{"content","source"}]
        matches = []
        for i, idx in enumerate(indices[0]):
            if idx < len(chunk_data):
                dist = float(distances[0][i])
                if dist > 1.5:
                    continue  # skip irrelevant chunks
                entry = chunk_data[idx]
                if isinstance(entry, dict):
                    matches.append({'content': entry['content'], 'source': entry.get('source', ''), 'distance': dist})
                else:
                    matches.append({'content': entry, 'source': '', 'distance': dist})

        knowledge_context = "\n\n".join([m['content'] for m in matches])

        # Build system instruction (behavioral rules separated from content)
        system_parts = [
            "You are a helpful AI assistant that answers questions based on the provided knowledge context.",
            "Rules:",
            "- Primarily answer from the provided knowledge context.",
            "- For comparison or general questions, you may use broader knowledge but clearly note when doing so.",
            "- If the knowledge context does not contain enough information, politely say you don't have that specific information.",
            "- Keep answers concise and to the point. If the user wants more detail, they will ask.",
            "- Maintain conversation continuity and reference previous messages when relevant.",
            "- Be natural and conversational. Never say 'based on the context' or 'according to the documents'.",
            "- Respond in the same language the user writes in.",
        ]
        # Inject custom bot instructions if set
        if hasattr(chatbot, 'bot_instructions') and chatbot.bot_instructions.strip():
            system_parts.append(f"\nCustom instructions from the chatbot owner:\n{chatbot.bot_instructions.strip()}")
        system_instruction = "\n".join(system_parts)

        # User prompt — left-aligned, no Python indentation
        prompt = (
            f"Previous conversation:\n{chat_context}\n\n"
            f"Knowledge context:\n{knowledge_context}\n\n"
            f"User question: {user_message}"
        )

        # Get response from Gemini
        gemini_response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config={"system_instruction": system_instruction},
        )

        bot_response = gemini_response.text
        
        # Store bot response
        Message.objects.create(
            conversation=conversation,
            content=bot_response,
            is_bot=True
        )
        print(f"Stored bot response in conversation: {conversation.conversation_id}")

        # Update conversation last_updated
        conversation.save()
        
        response = JsonResponse({
            'answer': bot_response,
            'conversation_id': conversation.conversation_id,
            'matches': matches
        })
        
        # Add CORS headers to the response
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
        
    except json.JSONDecodeError:
        response = JsonResponse({'error': 'Invalid request body'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('chat_message error')
        response = JsonResponse({'error': 'An internal error occurred. Please try again.'}, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response


@csrf_exempt
def chat_feedback(request):
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'
        return response

    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        rating = data.get('rating') or data.get('no_of_star') or 0
        description = data.get('description', '')

        if not conversation_id:
            return JsonResponse({'error': 'conversation_id is required'}, status=400)

        conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

        # coerce rating to int and cap
        try:
            rating_val = int(rating)
        except Exception:
            rating_val = 0
        if rating_val < 0: rating_val = 0
        if rating_val > 5: rating_val = 5

        fb = ChatbotFeedback.objects.create(
            conversation=conversation,
            no_of_star=rating_val,
            description=description or ''
        )

        response = JsonResponse({'success': True, 'feedback_id': fb.feedback_id})
        response['Access-Control-Allow-Origin'] = '*'
        return response

    except json.JSONDecodeError:
        response = JsonResponse({'error': 'Invalid request body'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('chat_feedback error')
        response = JsonResponse({'error': 'An internal error occurred. Please try again.'}, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response

@xframe_options_exempt
@csrf_exempt
def serve_widget_js(request, chatbot_id):
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id)
    
    # Get absolute URLs
    base_url = request.build_absolute_uri('/').rstrip('/')
    logo_url = request.build_absolute_uri(chatbot.logo.url) if chatbot.logo else None
    
    context = {
        'chatbot': chatbot,
        'chatbot_name': chatbot.name,
        'chatbot_logo': logo_url,
        'base_url': base_url,
        'collect_email': chatbot.collect_email,
        'collect_email_message': chatbot.collect_email_message or 'Please enter your email to get started.',
    }
    
    response = render(request, 'user_querySafe/widget.js', context, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

def get_widget_code(chatbot_id, base_url):
    return f"""<!-- querySafe Chatbot Widget -->
    <script>
    (function(w,d,s,id){{
        var js, fjs = d.getElementsByTagName(s)[0];
        if (d.getElementById(id)){{return;}}
        js = d.createElement(s);
        js.id = id;
        js.src = "{base_url}/widget/{chatbot_id}/querySafe.js";
        js.async = true;
        fjs.parentNode.insertBefore(js, fjs);
    }}(window, document, 'script', 'querySafe-widget'));
    </script>"""

def get_widget_snippet(request, chatbot_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET method allowed'}, status=405)
    
    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id)
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    snippet = get_widget_code(chatbot_id, base_url)
    return JsonResponse({'snippet': snippet})

@login_required
def profile_view(request):
    user = User.objects.get(user_id=request.session['user_id'])
    
    # Get active plan
    # Prefer QSPlanAllot (QuerySafe plans). Fall back to legacy UserPlanAlot if none.
    qs_active = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()

    if qs_active:
        # Build a dict matching template keys used in profile.html
        active_plan = {
            'plan_name': qs_active.plan_name,
            'expire_date': qs_active.expire_date,
            'no_of_bot': qs_active.no_of_bot,
            'no_query': qs_active.no_of_query,
            'no_of_docs': qs_active.no_of_files,
            'doc_size_limit': qs_active.file_size,
        }
    else:
        active_plan = None
    
    # Get statistics
    stats = {
        'total_chatbots': Chatbot.objects.filter(user=user).count(),
        'total_conversations': Conversation.objects.filter(chatbot__user=user).count(),
        'total_messages': Message.objects.filter(conversation__chatbot__user=user).count(),
        'total_documents': ChatbotDocument.objects.filter(chatbot__user=user).count(),
    }
    
    # Get recent activities (last 10)
    recent_activities = Activity.objects.filter(user=user).order_by('-timestamp')[:10]
    
    context = {
        'user': user,
        'active_plan': active_plan,
        **stats,
        'recent_activities': recent_activities
    }
    
    return render(request, 'user_querySafe/profile.html', context)


# Public shared pages views 
def index_view(request):
    return render(request, 'user_querySafe/index.html')

@login_required
def help_support(request):
    user = User.objects.get(user_id=request.session['user_id'])
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        try:
            HelpSupportRequest.objects.create(
                user=user,
                subject=subject,
                message=message,
                status='pending'
            )
            messages.success(request, 'Your support request has been submitted successfully.')
            return redirect('help_support')
        except Exception as e:
            messages.error(request, f'Error creating support ticket: {str(e)}')
    
    # Get user's support tickets
    support_tickets = HelpSupportRequest.objects.filter(user=user).order_by('-created_at')
    
    # Define status colors and badge styling
    status_colors = {
        'pending': 'warning',
        'in_progress': 'info',
        'resolved': 'success',
        'suspended': 'danger'
    }
    
    # Add ticket_id, badge_color, and short_message to each ticket
    for ticket in support_tickets:
        ticket.ticket_id = f"HS{ticket.id:06d}"
        ticket.badge_color = status_colors.get(ticket.status, 'secondary')
        ticket.short_message = (ticket.message[:120] + '...') if ticket.message and len(ticket.message) > 120 else (ticket.message or '')
    
    context = {
        'user': user,
        'support_tickets': support_tickets
    }
    
    return render(request, 'user_querySafe/help-support.html', context)


# Email views  

def send_otp_email(email, otp, name, verification_url):
    try:
        subject = 'Verify Your Account'
        
        # Render the HTML template with personalized details
        html_message = render_to_string('user_querySafe/email/registration-otp.html', {
            'otp': otp,
            'name': name,
            'verification_url': verification_url,
            'project_name': settings.PROJECT_NAME
        })
        
        # Create plain-text fallback message with a clickable URL
        plain_message = (
            f"Hello {name},\n\n"
            f"Your OTP is: {otp}\n\n"
            f"Click the following link to verify your account:\n"
            f"{verification_url}\n\n"
            "The OTP is valid for 10 minutes."
        )
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def send_welcome_email(email, name, dashboard_url):
    try:
        subject = "Welcome to QuerySafe"
        html_message = render_to_string("user_querySafe/email/welcome-user.html", {
            'name': name,
            'dashboard_url': dashboard_url,
            'project_name': settings.PROJECT_NAME
        })
        plain_message = (
            f"Hello {name},\n\n"
            f"Welcome to QuerySafe!\n"
            f"Access your dashboard here: {dashboard_url}\n\n"
            "Thank you for joining us."
        )
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        return False


# =====================================================================
# ANALYTICS VIEWS
# =====================================================================

@login_required
def analytics_view(request, chatbot_id=None):
    """Analytics dashboard with summary metrics."""
    user = User.objects.get(user_id=request.session['user_id'])
    chatbots = Chatbot.objects.filter(user=user)

    selected_bot = None
    if chatbot_id:
        selected_bot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)

    # Date range
    range_param = request.GET.get('range', '30')
    range_days = {'7': 7, '30': 30, '90': 90, 'all': None}.get(range_param, 30)

    # Build base querysets
    conv_qs = Conversation.objects.filter(chatbot__user=user)
    msg_qs = Message.objects.filter(conversation__chatbot__user=user)
    feedback_qs = ChatbotFeedback.objects.filter(conversation__chatbot__user=user)

    if selected_bot:
        conv_qs = conv_qs.filter(chatbot=selected_bot)
        msg_qs = msg_qs.filter(conversation__chatbot=selected_bot)
        feedback_qs = feedback_qs.filter(conversation__chatbot=selected_bot)

    if range_days:
        cutoff = timezone.now() - timedelta(days=range_days)
        conv_qs = conv_qs.filter(started_at__gte=cutoff)
        msg_qs = msg_qs.filter(timestamp__gte=cutoff)
        feedback_qs = feedback_qs.filter(created_at__gte=cutoff)

    # Summary metrics
    total_conversations = conv_qs.count()
    total_messages = msg_qs.count()
    bot_messages = msg_qs.filter(is_bot=True).count()
    user_messages = msg_qs.filter(is_bot=False).count()

    avg_messages_per_conv = 0
    if total_conversations > 0:
        avg_messages_per_conv = round(total_messages / total_conversations, 1)

    avg_satisfaction = feedback_qs.aggregate(avg=Avg('no_of_star'))['avg'] or 0
    avg_satisfaction = round(avg_satisfaction, 1)
    feedback_count = feedback_qs.count()

    # Response rate: conversations that have at least one bot reply
    convs_with_reply = conv_qs.filter(messages__is_bot=True).distinct().count()
    response_rate = round((convs_with_reply / total_conversations * 100), 1) if total_conversations > 0 else 0

    # Leads collected (conversations with visitor_email)
    leads_qs = conv_qs.filter(visitor_email__isnull=False).exclude(visitor_email='')
    leads_collected = leads_qs.count()
    recent_leads = list(
        leads_qs.order_by('-started_at')
        .values_list('visitor_email', flat=True)[:10]
    )

    context = {
        'chatbots': chatbots,
        'selected_bot': selected_bot,
        'range': range_param,
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'bot_messages': bot_messages,
        'user_messages': user_messages,
        'avg_messages_per_conv': avg_messages_per_conv,
        'avg_satisfaction': avg_satisfaction,
        'feedback_count': feedback_count,
        'response_rate': response_rate,
        'leads_collected': leads_collected,
        'recent_leads': recent_leads,
    }
    return render(request, 'user_querySafe/analytics.html', context)


@login_required
def analytics_chart_data(request):
    """AJAX endpoint returning JSON data for Chart.js charts."""
    user = User.objects.get(user_id=request.session['user_id'])
    chatbot_id = request.GET.get('chatbot_id')
    chart_type = request.GET.get('chart', 'conversations_over_time')
    range_param = request.GET.get('range', '30')
    range_days = {'7': 7, '30': 30, '90': 90, 'all': None}.get(range_param, 30)

    # Build base querysets
    conv_qs = Conversation.objects.filter(chatbot__user=user)
    msg_qs = Message.objects.filter(conversation__chatbot__user=user)

    if chatbot_id:
        conv_qs = conv_qs.filter(chatbot__chatbot_id=chatbot_id)
        msg_qs = msg_qs.filter(conversation__chatbot__chatbot_id=chatbot_id)

    cutoff = None
    if range_days:
        cutoff = timezone.now() - timedelta(days=range_days)
        conv_qs = conv_qs.filter(started_at__gte=cutoff)
        msg_qs = msg_qs.filter(timestamp__gte=cutoff)

    if chart_type == 'conversations_over_time':
        data = (conv_qs
                .annotate(date=TruncDate('started_at'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date'))
        return JsonResponse({
            'labels': [d['date'].isoformat() for d in data],
            'values': [d['count'] for d in data],
        })

    elif chart_type == 'messages_per_day':
        data = (msg_qs
                .annotate(date=TruncDate('timestamp'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date'))
        return JsonResponse({
            'labels': [d['date'].isoformat() for d in data],
            'values': [d['count'] for d in data],
        })

    elif chart_type == 'peak_hours':
        data = (msg_qs
                .annotate(hour=ExtractHour('timestamp'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour'))
        labels = [f"{d['hour']:02d}:00" for d in data]
        values = [d['count'] for d in data]
        return JsonResponse({'labels': labels, 'values': values})

    elif chart_type == 'top_questions':
        top_qs = (msg_qs
                  .filter(is_bot=False)
                  .values('content')
                  .annotate(count=Count('id'))
                  .order_by('-count')[:20])
        return JsonResponse({
            'questions': [{'text': q['content'][:100], 'count': q['count']} for q in top_qs],
        })

    elif chart_type == 'satisfaction_distribution':
        feedback_qs = ChatbotFeedback.objects.filter(conversation__chatbot__user=user)
        if chatbot_id:
            feedback_qs = feedback_qs.filter(conversation__chatbot__chatbot_id=chatbot_id)
        if cutoff:
            feedback_qs = feedback_qs.filter(created_at__gte=cutoff)
        data = (feedback_qs
                .values('no_of_star')
                .annotate(count=Count('id'))
                .order_by('no_of_star'))
        dist = {i: 0 for i in range(1, 6)}
        for d in data:
            if d['no_of_star'] in dist:
                dist[d['no_of_star']] = d['count']
        return JsonResponse({
            'labels': ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
            'values': list(dist.values()),
        })

    return JsonResponse({'error': 'Unknown chart type'}, status=400)


@login_required
def analytics_export_csv(request):
    """Export analytics data as CSV."""
    user = User.objects.get(user_id=request.session['user_id'])
    chatbot_id = request.GET.get('chatbot_id')
    range_param = request.GET.get('range', '30')
    range_days = {'7': 7, '30': 30, '90': 90, 'all': None}.get(range_param, 30)

    conv_qs = Conversation.objects.filter(chatbot__user=user)
    if chatbot_id:
        conv_qs = conv_qs.filter(chatbot__chatbot_id=chatbot_id)
    if range_days:
        cutoff = timezone.now() - timedelta(days=range_days)
        conv_qs = conv_qs.filter(started_at__gte=cutoff)

    response = HttpResponse(content_type='text/csv')
    fname = f"analytics_{chatbot_id or 'all'}_{range_param}d.csv"
    response['Content-Disposition'] = f'attachment; filename="{fname}"'

    writer = csv.writer(response)
    writer.writerow(['Conversation ID', 'Chatbot', 'User Session', 'Started At',
                     'Total Messages', 'Bot Messages', 'User Messages'])

    for conv in conv_qs.select_related('chatbot').prefetch_related('messages'):
        msgs = conv.messages.all()
        writer.writerow([
            conv.conversation_id,
            conv.chatbot.name,
            conv.user_id,
            conv.started_at.isoformat(),
            msgs.count(),
            msgs.filter(is_bot=True).count(),
            msgs.filter(is_bot=False).count(),
        ])

    return response

