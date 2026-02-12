from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import RegisterForm, OTPVerificationForm  # Remove LoginForm
from .models import Activity, User, Chatbot, ChatbotDocument, Conversation, Message, ChatbotFeedback, EmailOTP, QSPlanAllot, HelpSupportRequest, BugReport, ScheduledEmail
from django.http import JsonResponse, HttpResponse  # Import HttpResponse
import json
from django.views.decorators.csrf import csrf_exempt
import os
import string
import faiss
from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
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
from django.core.mail import send_mail, EmailMessage
import random
from django.template.loader import render_to_string
from .decorators import redirect_authenticated_user, login_required
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.urls import reverse
from django.db import models
import time  # Import the time module
import logging
import requests as http_requests  # renamed to avoid conflict with django request

logger = logging.getLogger(__name__)

# Initialize Gemini client (embedding model loaded lazily via singleton)
client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location=settings.GEMINI_LOCATION)

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

                        # Schedule drip email sequence
                        try:
                            now = timezone.now()
                            drip_schedule = [
                                ('day1_getting_started', timedelta(days=1)),
                                ('day3_first_chatbot', timedelta(days=3)),
                                ('day7_tips', timedelta(days=7)),
                            ]
                            for email_type, delay in drip_schedule:
                                ScheduledEmail.objects.get_or_create(
                                    user=user,
                                    email_type=email_type,
                                    defaults={'scheduled_at': now + delay}
                                )
                        except Exception as drip_err:
                            print(f"Error scheduling drip emails: {drip_err}")

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


def google_callback(request):
    """Handle the callback from Google OAuth."""
    # Validate state to prevent CSRF
    state = request.GET.get('state')
    stored_state = request.session.pop('google_oauth_state', None)

    logger.info(f"Google OAuth callback: state={'present' if state else 'missing'}, stored_state={'present' if stored_state else 'missing'}")

    if not state or state != stored_state:
        logger.error(f"Google OAuth state mismatch: received={state}, stored={stored_state}")
        messages.error(request, 'Invalid authentication state. Please try again.')
        return redirect('login')

    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        logger.error(f"Google OAuth error: {error}")
        messages.error(request, 'Google sign-in was cancelled or failed.')
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
        }, timeout=15)

        if token_response.status_code != 200:
            logger.error(f"Google token exchange failed: {token_response.status_code} - {token_response.text}")
            messages.error(request, 'Failed to authenticate with Google. Please try again.')
            return redirect('login')

        tokens = token_response.json()
        access_token = tokens.get('access_token')

        if not access_token:
            logger.error(f"No access_token in Google response: {tokens}")
            messages.error(request, 'Failed to get access token from Google.')
            return redirect('login')

    except Exception as e:
        logger.error(f"Google token exchange exception: {e}")
        messages.error(request, 'Could not connect to Google. Please try again.')
        return redirect('login')

    # Fetch user info from Google
    try:
        userinfo_response = http_requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )

        if userinfo_response.status_code != 200:
            logger.error(f"Google userinfo failed: {userinfo_response.status_code} - {userinfo_response.text}")
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

    except Exception as e:
        logger.error(f"Google userinfo exception: {e}")
        messages.error(request, 'Error retrieving your Google profile.')
        return redirect('login')

    # Find or create user
    try:
        try:
            user = User.objects.get(email=email)
            logger.info(f"Google OAuth: existing user found for {email}")
            # Existing user — check if active
            if not user.is_active:
                # Auto-activate since Google has verified their email
                user.is_active = True
                user.registration_status = 'activated'
                user.activated_at = timezone.now()
                user.save()
        except User.DoesNotExist:
            # Create new user — auto-activated (Google verified email)
            logger.info(f"Google OAuth: creating new user for {email}")
            user = User(
                name=name or email.split('@')[0],
                email=email,
                is_active=True,
                registration_status='activated',
                activated_at=timezone.now(),
            )
            # Set an unusable password for Google-only users (field is non-nullable)
            from django.contrib.auth.hashers import make_password
            user.password = make_password(None)  # Stores a hash that can never be matched
            user.save()
            logger.info(f"Google OAuth: new user created with id {user.user_id}")
    except Exception as e:
        logger.error(f"Google OAuth user creation error: {e}")
        messages.error(request, 'Failed to create your account. Please try again.')
        return redirect('login')

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

    # Track login for engagement features
    request.session['previous_login'] = user.last_login.isoformat() if user.last_login else None
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

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

                    # Track login for engagement features
                    request.session['previous_login'] = user.last_login.isoformat() if user.last_login else None
                    user.last_login = timezone.now()
                    user.save(update_fields=['last_login'])

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
        # Guided tour (first-time users only)
        'show_tour': show_onboarding and not user.tour_completed,
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

def _should_hide_branding(chatbot_user):
    """Check if chatbot owner's active plan includes branding removal (Secure Business or higher)."""
    try:
        active_allot = QSPlanAllot.objects.filter(
            user=chatbot_user,
            expire_date__gte=timezone.now().date()
        ).select_related('parent_plan').order_by('-created_at').first()
        if not active_allot:
            return False
        # Secure Business (GSE37) and its trial (GSE38) include branding removal
        return active_allot.parent_plan_id in ('GSE37', 'GSE38')
    except Exception:
        return False


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

    # Check if branding should be hidden based on owner's plan
    hide_branding = _should_hide_branding(chatbot.user)

    context = {
        'chatbot': chatbot,
        'chatbot_name': chatbot.name,
        'chatbot_logo': chatbot.logo.url if chatbot.logo else None,
        'chatbot_id': chatbot.chatbot_id,
        'sample_questions': sample_questions,
        'hide_branding': hide_branding,
        'collect_email': chatbot.collect_email,
        'collect_email_message': chatbot.collect_email_message or 'Please enter your email to get started.',
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

        # Check query limit BEFORE processing (base plan + add-on stacking)
        # Count total bot responses for this chatbot (across ALL visitors/conversations)
        total_bot_responses = Message.objects.filter(
            conversation__chatbot=chatbot,
            is_bot=True
        ).count()

        # Calculate effective limit: base plan + active extra_messages add-ons
        try:
            from user_querySafe.addon_utils import get_effective_limits
            effective = get_effective_limits(chatbot.user, active_plan)
            effective_query_limit = effective['no_of_query']
        except Exception:
            effective_query_limit = active_plan.no_of_query

        if total_bot_responses >= effective_query_limit:
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
            "You are a helpful AI assistant for a product/service. You answer questions ONLY using the provided knowledge context.",
            "Rules:",
            "- Answer ONLY from the provided knowledge context. Do NOT use any outside knowledge about the product or service.",
            "- If the knowledge context does not contain the answer, say: 'I don't have that information in my knowledge base. Please contact our team for details.'",
            "- NEVER guess, assume, or invent features, capabilities, or details not explicitly stated in the knowledge context.",
            "- If asked about a feature and the context doesn't mention it, say you don't have information about that specific feature.",
            "- Maintain conversation continuity and reference previous messages when relevant.",
            "- Be natural and conversational. Never say 'based on the context' or 'according to the documents'.",
            "- For general greetings or small talk, respond naturally without making claims about the product.",
            "- Respond in the same language the user writes in.",
            "",
            "Response formatting:",
            "- For simple questions (yes/no, single fact, greeting), reply in 1-2 short sentences.",
            "- For 'what is' or 'explain' questions, use a brief paragraph (3-5 sentences).",
            "- For 'how to', steps, or process questions, use a numbered list.",
            "- For listing features, benefits, or multiple items, use bullet points.",
            "- For comparison questions, use a short paragraph or side-by-side bullets.",
            "- When the user asks to elaborate or says 'tell me more', expand with a detailed paragraph and examples from the knowledge context.",
            "- Never use more than 150 words unless the user explicitly asks for detail.",
            "- Use markdown formatting (bold, bullets, numbered lists) for readability.",
        ]
        # Inject custom bot instructions if set
        if hasattr(chatbot, 'bot_instructions') and chatbot.bot_instructions.strip():
            system_parts.append(f"\nCustom instructions from the chatbot owner:\n{chatbot.bot_instructions.strip()}")

        # If web search is enabled, add instructions for using web data
        web_search_enabled = getattr(chatbot, 'enable_web_search', False)
        if web_search_enabled:
            system_parts.append("")
            system_parts.append("Web Search Grounding (ENABLED):")
            system_parts.append("- You have access to live Google Search results alongside the knowledge base.")
            system_parts.append("- ALWAYS prioritize the knowledge context over web results for product-specific questions.")
            system_parts.append("- Use web search results for comparisons, market data, competitor information, or questions outside the knowledge base.")
            system_parts.append("- Be transparent when using web data: e.g., 'According to recent web results...'")
            system_parts.append("- Never fabricate web search results. If web results are not available, say so.")
            system_parts.append("- Combine knowledge base and web data naturally when both are relevant.")

        system_instruction = "\n".join(system_parts)

        # User prompt
        prompt = (
            f"Previous conversation:\n{chat_context}\n\n"
            f"Knowledge context:\n{knowledge_context}\n\n"
            f"User question: {user_message}"
        )

        # Build Gemini config - conditionally add Google Search tool
        config_kwargs = {
            "system_instruction": system_instruction,
            "temperature": 0.3,
        }
        if web_search_enabled:
            config_kwargs["tools"] = [Tool(google_search=GoogleSearch())]

        gemini_config = GenerateContentConfig(**config_kwargs)

        # Get response from Gemini
        gemini_response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=gemini_config,
        )

        bot_response = gemini_response.text

        # Extract grounding metadata if web search was used
        web_sources = []
        if web_search_enabled:
            try:
                for candidate in (gemini_response.candidates or []):
                    grounding_meta = getattr(candidate, 'grounding_metadata', None)
                    if grounding_meta:
                        # Count search queries generated
                        search_queries = getattr(grounding_meta, 'web_search_queries', []) or []
                        if search_queries:
                            from user_querySafe.models import WebSearchUsage
                            WebSearchUsage.objects.create(
                                chatbot=chatbot,
                                query_count=len(search_queries),
                            )

                        # Extract source URLs from grounding chunks
                        grounding_chunks = getattr(grounding_meta, 'grounding_chunks', []) or []
                        for chunk in grounding_chunks:
                            web_ref = getattr(chunk, 'web', None)
                            if web_ref:
                                web_sources.append({
                                    'uri': getattr(web_ref, 'uri', ''),
                                    'title': getattr(web_ref, 'title', ''),
                                })
            except Exception as gs_err:
                print(f"Grounding metadata extraction error: {gs_err}")

        # Store bot response
        Message.objects.create(
            conversation=conversation,
            content=bot_response,
            is_bot=True
        )
        print(f"Stored bot response in conversation: {conversation.conversation_id}")

        # Update conversation last_updated
        conversation.save()

        response_data = {
            'answer': bot_response,
            'conversation_id': conversation.conversation_id,
            'matches': matches,
        }
        if web_sources:
            response_data['web_sources'] = web_sources

        response = JsonResponse(response_data)
        
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

    # Check if branding should be hidden based on owner's plan
    hide_branding = _should_hide_branding(chatbot.user)

    context = {
        'chatbot': chatbot,
        'chatbot_name': chatbot.name,
        'chatbot_logo': logo_url,
        'base_url': base_url,
        'collect_email': chatbot.collect_email,
        'collect_email_message': chatbot.collect_email_message or 'Please enter your email to get started.',
        'hide_branding': hide_branding,
    }
    
    response = render(request, 'user_querySafe/widget.js', context, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
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

        # No CC on OTP emails — they contain sensitive verification codes
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

        # Use EmailMessage for CC support
        msg = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            cc=[settings.CC_EMAIL] if getattr(settings, 'CC_EMAIL', '') else [],
        )
        msg.content_subtype = 'html'
        msg.send(fail_silently=False)
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
    writer.writerow(['Conversation ID', 'Chatbot', 'User Session', 'Visitor Email', 'Started At',
                     'Total Messages', 'Bot Messages', 'User Messages'])

    for conv in conv_qs.select_related('chatbot').prefetch_related('messages'):
        msgs = conv.messages.all()
        writer.writerow([
            conv.conversation_id,
            conv.chatbot.name,
            conv.user_id,
            conv.visitor_email or '',
            conv.started_at.isoformat(),
            msgs.count(),
            msgs.filter(is_bot=True).count(),
            msgs.filter(is_bot=False).count(),
        ])

    return response


# ─────────────────────────────────────────────
# Contact Form API (for static public website)
# ─────────────────────────────────────────────
@csrf_exempt
def contact_form_api(request):
    """Handle contact form submissions from the static public website (querysafe.ai)."""
    # CORS headers for cross-origin requests from querysafe.ai
    origin = request.META.get('HTTP_ORIGIN', '')
    is_allowed = origin in ('https://querysafe.ai', 'https://www.querysafe.ai') or \
        origin.startswith('http://localhost') or origin.startswith('http://127.0.0.1')

    def cors_response(response):
        if is_allowed:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = HttpResponse(status=200)
        return cors_response(response)

    if request.method != 'POST':
        return cors_response(JsonResponse({'error': 'Method not allowed'}, status=405))

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return cors_response(JsonResponse({'error': 'Invalid JSON'}, status=400))

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    message_text = data.get('message', '').strip()

    # Validation
    if not name or not email or not message_text:
        return cors_response(JsonResponse({'error': 'Name, email, and message are required.'}, status=400))

    # Send email notification
    try:
        from django.core.mail import send_mail
        subject = f'[QuerySafe Contact] New message from {name}'
        body = (
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Phone: {phone or 'Not provided'}\n\n"
            f"Message:\n{message_text}\n"
        )
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )
    except Exception as e:
        return cors_response(JsonResponse({'error': 'Failed to send message. Please try again later.'}, status=500))

    return cors_response(JsonResponse({'success': True, 'message': 'Thank you! Your message has been sent successfully.'}))


# -----------------------------------------
# Bug Report API (for static public website)
# -----------------------------------------
@csrf_exempt
def bug_report_api(request):
    """Handle bug report submissions from the static public website (querysafe.ai)."""
    origin = request.META.get('HTTP_ORIGIN', '')
    is_allowed = origin in ('https://querysafe.ai', 'https://www.querysafe.ai') or \
        origin.startswith('http://localhost') or origin.startswith('http://127.0.0.1')

    def cors_response(response):
        if is_allowed:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = HttpResponse(status=200)
        return cors_response(response)

    if request.method != 'POST':
        return cors_response(JsonResponse({'error': 'Method not allowed'}, status=405))

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return cors_response(JsonResponse({'error': 'Invalid JSON'}, status=400))

    email = data.get('email', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    steps_to_reproduce = data.get('steps_to_reproduce', '').strip()
    severity = data.get('severity', 'low').strip().lower()

    # Validation
    if not email or not title or not description:
        return cors_response(JsonResponse({'error': 'Email, title, and description are required.'}, status=400))

    if severity not in ('low', 'medium', 'high', 'critical'):
        return cors_response(JsonResponse({'error': 'Invalid severity level.'}, status=400))

    # Rate limiting: 1 submission per email per 24 hours
    one_day_ago = timezone.now() - timedelta(hours=24)
    if BugReport.objects.filter(email=email, created_at__gte=one_day_ago).exists():
        return cors_response(JsonResponse({
            'error': 'You have already submitted a bug report in the last 24 hours. Please try again later.'
        }, status=429))

    # Generate coupon code
    coupon_code = 'QS-BUG-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Create the bug report
    try:
        report = BugReport(
            email=email,
            title=title,
            description=description,
            steps_to_reproduce=steps_to_reproduce,
            severity=severity,
            coupon_code=coupon_code,
        )
        report.save()
    except Exception as e:
        logger.error(f'Bug report creation failed: {e}')
        return cors_response(JsonResponse({'error': 'Failed to submit report. Please try again.'}, status=500))

    # Send admin email notification
    try:
        send_mail(
            f'[QuerySafe Bug Report] {severity.upper()}: {title}',
            f"Report ID: {report.report_id}\n"
            f"Email: {email}\n"
            f"Severity: {severity}\n"
            f"Title: {title}\n\n"
            f"Description:\n{description}\n\n"
            f"Steps to Reproduce:\n{steps_to_reproduce or 'Not provided'}\n\n"
            f"Coupon Code: {coupon_code}\n",
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=True,
        )
    except Exception:
        pass  # Don't fail the request if email fails

    return cors_response(JsonResponse({
        'success': True,
        'coupon_code': coupon_code,
        'report_id': report.report_id,
        'message': 'Bug report submitted successfully!'
    }))


# =====================================================================
# CRON / SCHEDULED TASK ENDPOINTS
# =====================================================================

@csrf_exempt
def cron_send_drip_emails(request):
    """
    HTTP trigger for Cloud Scheduler to send pending drip emails.
    Protected by a shared secret in the X-Cron-Secret header.
    """
    # Verify cron secret to prevent unauthorized access
    cron_secret = getattr(settings, 'CRON_SECRET', '')
    request_secret = request.headers.get('X-Cron-Secret', '')

    if not cron_secret or request_secret != cron_secret:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from django.core.management import call_command
    from io import StringIO

    output = StringIO()
    call_command('send_drip_emails', stdout=output)
    result = output.getvalue()

    return JsonResponse({'success': True, 'output': result})


@csrf_exempt
def cron_send_chatbot_reports(request):
    """HTTP trigger for Cloud Scheduler to send chatbot email reports."""
    cron_secret = getattr(settings, 'CRON_SECRET', '')
    request_secret = request.headers.get('X-Cron-Secret', '')
    if not cron_secret or request_secret != cron_secret:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from django.core.management import call_command
    from io import StringIO
    output = StringIO()
    call_command('send_chatbot_reports', stdout=output)
    return JsonResponse({'success': True, 'output': output.getvalue()})


@csrf_exempt
def cron_send_goal_plan_emails(request):
    """HTTP trigger for Cloud Scheduler to send daily goal plan emails."""
    cron_secret = getattr(settings, 'CRON_SECRET', '')
    request_secret = request.headers.get('X-Cron-Secret', '')
    if not cron_secret or request_secret != cron_secret:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from django.core.management import call_command
    from io import StringIO
    output = StringIO()
    call_command('send_goal_plan_emails', stdout=output)
    return JsonResponse({'success': True, 'output': output.getvalue()})


# -----------------------------------------
# Tour Complete API
# -----------------------------------------
@login_required
def tour_complete_api(request):
    """Mark the guided tour as completed for the logged-in user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    user = User.objects.get(user_id=request.session['user_id'])
    user.tour_completed = True
    user.save(update_fields=['tour_completed'])
    return JsonResponse({'success': True})
