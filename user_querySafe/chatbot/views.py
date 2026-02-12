import os
import json
import logging
from django.contrib import messages

logger = logging.getLogger(__name__)
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from user_querySafe.decorators import login_required
from user_querySafe.forms import ChatbotCreateForm, ChatbotEditForm
from user_querySafe.models import Activity, Chatbot, ChatbotDocument, ChatbotTemplate, ChatbotEmailReport, Conversation, GoalPlan, User, QSPlanAllot
from .pipeline_processor import run_pipeline_background, PDF_DIR


@login_required
def my_chatbots(request):
    user = User.objects.get(user_id=request.session['user_id'])
    chatbots = Chatbot.objects.filter(user=user).prefetch_related('conversations')
 
    # Get active plan and usage data
    active_plan = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()
    
    current_chatbots = chatbots.count()
    
    # Show widget guidance for newer users who have trained bots
    trained_count = chatbots.filter(status='trained').count()
    show_widget_guidance = current_chatbots <= 2 and trained_count > 0

    # Check if user has any conversations (to show contextual "Next Step" banner)
    has_any_conversations = Conversation.objects.filter(chatbot__in=chatbots).exists()

    context = {
        'chatbots': chatbots,
        'active_plan': active_plan,
        'chatbots_used': current_chatbots,
        'chatbots_total': active_plan.no_of_bot if active_plan else 0,
        'chatbots_remaining': (active_plan.no_of_bot - current_chatbots) if active_plan else 0,
        'show_toaster': False,
        'show_widget_guidance': show_widget_guidance,
        'has_any_conversations': has_any_conversations,
    }
    return render(request, 'user_querySafe/my_chatbots.html', context)

@login_required
def create_chatbot(request):
    user = User.objects.get(user_id=request.session['user_id'])

    # Get the current active plan
    active_plan = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()

    if not active_plan:
        messages.error(request, "You do not have an active subscription to create chatbots.")
        return redirect('my_chatbots')

    # Check if user reached chatbot limit (base plan + add-on stacking)
    current_chatbots = Chatbot.objects.filter(user=user).count()
    try:
        from user_querySafe.addon_utils import get_effective_limits
        effective = get_effective_limits(user, active_plan)
        effective_bot_limit = effective['no_of_bot']
    except Exception:
        effective_bot_limit = active_plan.no_of_bot

    if current_chatbots >= effective_bot_limit:
        messages.warning(
            request,
            f"You have reached your limit of {effective_bot_limit} chatbots. "
            f"Purchase an extra chatbot slot add-on or upgrade your plan."
        )
        return redirect('my_chatbots')

    if request.method == 'POST':
        form = ChatbotCreateForm(request.POST, request.FILES)
        if form.is_valid():
            chatbot = form.save(commit=False)
            chatbot.user = user

            # Apply template if selected
            template_id = request.POST.get('template_id', '').strip()
            if template_id:
                try:
                    template = ChatbotTemplate.objects.get(template_id=template_id, is_active=True)
                    chatbot.template = template
                    if not chatbot.bot_instructions.strip():
                        chatbot.bot_instructions = template.bot_instructions
                    if not chatbot.sample_questions.strip():
                        chatbot.sample_questions = template.sample_questions
                    if not chatbot.description.strip():
                        chatbot.description = template.description
                except ChatbotTemplate.DoesNotExist:
                    pass

            chatbot.save()

            # Handle goal text for Goal Planner template
            goal_text = request.POST.get('goal_text', '').strip()
            enable_goal_emails = 'enable_goal_emails' in request.POST
            if goal_text and chatbot.template and chatbot.template.template_id == 'TMPL01':
                from django.core.files.base import ContentFile
                content = f"USER GOALS:\n\n{goal_text}"
                doc_file = ContentFile(content.encode('utf-8'), name=f"{chatbot.name}-goals.txt")
                ChatbotDocument.objects.create(chatbot=chatbot, document=doc_file)

            # Process document uploads (base plan + add-on stacking)
            uploaded_docs = request.FILES.getlist('pdf_files')
            try:
                from user_querySafe.addon_utils import get_effective_limits
                effective = get_effective_limits(user, active_plan, chatbot=chatbot)
                allowed_docs = effective['no_of_files']
            except Exception:
                allowed_docs = active_plan.no_of_files
            allowed_size_bytes = active_plan.file_size * 1024 * 1024

            if len(uploaded_docs) > allowed_docs:
                messages.error(request, f"You can upload a maximum of {allowed_docs} file(s). Purchase extra documents add-on for more.")
                return redirect('create_chatbot')

            ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.jpg', '.jpeg', '.png', '.gif', '.bmp'}

            successful_uploads = 0
            for doc in uploaded_docs:
                # Validate file extension
                import os as _os
                ext = _os.path.splitext(doc.name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    messages.error(request, f"File '{doc.name}' has an unsupported type. Allowed: PDF, DOC, DOCX, TXT, XLSX, XLS, JPG, PNG, GIF, BMP.")
                    continue

                if doc.size > allowed_size_bytes:
                    messages.error(request, f"File '{doc.name}' exceeds the size limit of {active_plan.file_size} MB.")
                    continue

                ChatbotDocument.objects.create(chatbot=chatbot, document=doc)
                successful_uploads += 1

            # Process URL inputs
            url_text = request.POST.get('website_urls', '').strip()
            sitemap_url = request.POST.get('sitemap_url', '').strip()
            url_count = 0

            try:
                from user_querySafe.models import ChatbotURL
                if url_text:
                    urls = [u.strip() for u in url_text.splitlines() if u.strip()]
                    for url in urls:
                        if successful_uploads + url_count >= allowed_docs:
                            messages.warning(request, "Source limit reached.")
                            break
                        ChatbotURL.objects.create(chatbot=chatbot, url=url, is_sitemap=False)
                        url_count += 1

                if sitemap_url:
                    ChatbotURL.objects.create(chatbot=chatbot, url=sitemap_url, is_sitemap=True)
                    url_count += 1
            except Exception:
                pass  # ChatbotURL model not yet available

            # For Goal Planner with text-only (no files/URLs), we still need to run the pipeline
            has_goal_text_only = (goal_text and chatbot.template
                                  and chatbot.template.template_id == 'TMPL01'
                                  and successful_uploads == 0 and url_count == 0)

            if successful_uploads > 0 or url_count > 0 or has_goal_text_only:
                # Train in background thread so the page redirects immediately
                from .pipeline_processor import run_pipeline_background

                has_docs = ChatbotDocument.objects.filter(chatbot=chatbot).exists() or url_count > 0
                is_goal_planner = (chatbot.template and chatbot.template.is_flagship
                                   and chatbot.template.template_id == 'TMPL01')

                # Build post-pipeline callback for Goal Planner
                post_callback = None
                if is_goal_planner:
                    _goal_text = goal_text or None
                    _chatbot = chatbot
                    _user = user
                    _enable = enable_goal_emails
                    def _goal_callback():
                        try:
                            _generate_goal_plan(_chatbot, _user, goal_text=_goal_text)
                            GoalPlan.objects.filter(chatbot=_chatbot).update(enable_emails=_enable)
                        except Exception:
                            logger.exception("Goal plan generation failed for %s", _chatbot.chatbot_id)
                    post_callback = _goal_callback

                if has_docs:
                    run_pipeline_background(chatbot.chatbot_id, post_callback=post_callback)
                elif is_goal_planner and post_callback:
                    # Text-only goal planner with no docs - just generate the plan
                    import threading
                    def _bg_goal():
                        post_callback()
                        Chatbot.objects.filter(chatbot_id=chatbot.chatbot_id).update(status='trained')
                    threading.Thread(target=_bg_goal, daemon=False).start()

                messages.success(request, f"Chatbot '{chatbot.name}' created! Training is in progress - this usually takes a few minutes.")
                return redirect('my_chatbots')
            else:
                messages.error(request, "No documents or URLs were provided.")
                chatbot.delete()
                return redirect('create_chatbot')
    else:
        form = ChatbotCreateForm()

    templates = ChatbotTemplate.objects.filter(is_active=True).order_by('sort_order', 'name')
    context = {
        'form': form,
        'active_plan': active_plan,
        'templates': templates,
    }
    return render(request, 'user_querySafe/create_chatbot.html', context)


def _generate_goal_plan(chatbot, user, goal_text=None):
    """Generate a 30-day goal plan. Uses goal_text if provided, else document chunks."""
    from django.conf import settings
    from google import genai

    if goal_text:
        # Direct text input from user - use as-is
        document_text = goal_text
    else:
        # Read from trained document chunks
        meta_path = os.path.join(settings.META_DIR, f"{chatbot.chatbot_id}-chunks.json")
        if not os.path.exists(meta_path):
            raise FileNotFoundError("No training data found for this chatbot")

        with open(meta_path, 'r', encoding='utf-8') as f:
            chunk_data = json.load(f)

        # Extract text content from chunks (limit to avoid exceeding context)
        document_text = "\n".join([
            entry.get('content', str(entry)) if isinstance(entry, dict) else str(entry)
            for entry in chunk_data[:50]
        ])[:15000]  # Cap at ~15k chars

    prompt = f"""You are a goal planning expert. Based on the user's goals below, create a detailed 30-day action plan.

USER'S GOALS:
{document_text}

INSTRUCTIONS:
- First assess if the goals are realistic for a 30-day timeframe. If not, adjust the scope and clearly explain what can be achieved in 30 days versus what requires a longer commitment.
- Provide a plan_summary with your honest assessment, any adjusted expectations, and the overall plan description (2-4 sentences).
- Create exactly 30 days of planning.
- Each day should have a clear title, 2-3 specific actionable tasks, and a focus area.
- Tasks should be concrete and achievable in the allocated day.
- Build progressively - earlier days focus on foundation and habits, later days on execution and consistency.
- Include weekly review days (days 7, 14, 21, 28) for reflection and adjustment.
- Be motivational but realistic - do not promise unrealistic outcomes.

OUTPUT FORMAT (strict JSON, no markdown):
{{"plan_summary": "Honest assessment and plan overview", "days": [{{"day": 1, "title": "Day title", "focus": "Focus area", "tasks": ["Task 1", "Task 2", "Task 3"], "motivation": "Short motivational message"}}]}}

Return ONLY valid JSON, no markdown code fences."""

    client = genai.Client(
        vertexai=True,
        project=settings.PROJECT_ID,
        location=settings.GEMINI_LOCATION
    )
    response = client.models.generate_content(
        model=settings.GEMINI_CHAT_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"temperature": 0.4},
    )

    plan_text = response.text.strip()
    # Remove markdown code fences if present
    if plan_text.startswith('```'):
        plan_text = plan_text.split('\n', 1)[1]
    if plan_text.endswith('```'):
        plan_text = plan_text.rsplit('```', 1)[0]
    plan_text = plan_text.strip()

    plan_data = json.loads(plan_text)

    GoalPlan.objects.update_or_create(
        chatbot=chatbot,
        defaults={
            'recipient_email': user.email,
            'plan_data': plan_data,
            'total_days': len(plan_data.get('days', [])),
            'current_day': 0,
            'status': 'active',
        }
    )


@login_required
def change_chatbot_status(request):
    """
    AJAX view to change the status of a chatbot.
    Expects JSON with keys "chatbot_id" and "new_status".
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            chatbot_id = data.get('chatbot_id')
            new_status = data.get('new_status')

            # Validate status against allowed values
            ALLOWED_STATUS_TRANSITIONS = {'trained', 'inactive'}
            if new_status not in ALLOWED_STATUS_TRANSITIONS:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid status value. Allowed: {", ".join(ALLOWED_STATUS_TRANSITIONS)}'
                }, status=400)

            # Add user verification
            user = User.objects.get(user_id=request.session['user_id'])
            chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)

            # Update status
            chatbot.status = new_status
            chatbot.save()
            
            # Log the activity
            Activity.objects.create(
                user=user,
                title='Chatbot Status Change',
                description=f'Changed chatbot {chatbot.name} status to {new_status}',
                type='info'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Chatbot status changed to {new_status}'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=400)
            
    return JsonResponse({
        'error': 'Invalid request method'
    }, status=405)

def chatbot_status(request):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    user = User.objects.get(user_id=request.session['user_id'])
    chatbots = Chatbot.objects.filter(user=user)
    data = [{'chatbot_id': bot.chatbot_id, 'status': bot.status} for bot in chatbots]
    return JsonResponse(data, safe=False)

@login_required
def chatbot_documents_api(request, chatbot_id):
    """AJAX endpoint to return the list of documents for a chatbot."""
    user = User.objects.get(user_id=request.session['user_id'])
    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)
    documents = ChatbotDocument.objects.filter(chatbot=chatbot).order_by('-uploaded_at')
    docs_data = []
    for doc in documents:
        file_ext = os.path.splitext(doc.document.name)[1].lower() if doc.document else ''
        file_size = doc.document.size if doc.document and hasattr(doc.document, 'size') else 0
        docs_data.append({
            'name': doc.original_filename if hasattr(doc, 'original_filename') and doc.original_filename else os.path.basename(doc.document.name),
            'type': file_ext.replace('.', '').upper() or 'FILE',
            'size_kb': round(file_size / 1024, 1) if file_size else 0,
            'uploaded_at': doc.uploaded_at.strftime('%b %d, %Y') if doc.uploaded_at else '',
        })
    return JsonResponse({'documents': docs_data, 'total': len(docs_data)})


def chatbot_detail_view(request, pk):
    if 'user_id' not in request.session:
        return redirect('login')

    user = User.objects.get(user_id=request.session['user_id'])
    chatbot = get_object_or_404(Chatbot, id=pk, user=user)

    context = {
        'chatbot': chatbot,
    }
    return render(request, 'user_querySafe/chatbot_detail.html', context)


# ── Edit / Retrain ──────────────────────────────────────────────────

@login_required
def edit_chatbot(request, chatbot_id):
    user = User.objects.get(user_id=request.session['user_id'])
    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)

    active_plan = QSPlanAllot.objects.filter(
        user=user, expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()

    if not active_plan:
        messages.error(request, "You need an active subscription to edit chatbots.")
        return redirect('my_chatbots')

    existing_docs = ChatbotDocument.objects.filter(chatbot=chatbot).order_by('uploaded_at')

    # Import here to avoid circular imports at module level
    try:
        from user_querySafe.models import ChatbotURL
        existing_urls = ChatbotURL.objects.filter(chatbot=chatbot).order_by('created_at')
    except Exception:
        existing_urls = []

    if request.method == 'POST':
        form = ChatbotEditForm(request.POST, request.FILES, instance=chatbot)
        if form.is_valid():
            saved_chatbot = form.save(commit=False)

            # Validate web search toggle: only allow if user has active addon
            if saved_chatbot.enable_web_search:
                try:
                    from user_querySafe.models import QSAddonPurchase
                    has_addon = QSAddonPurchase.objects.filter(
                        user=user,
                        addon__addon_type='web_search',
                        chatbot=chatbot,
                        expire_date__gte=timezone.now().date(),
                        status='active',
                        quantity_remaining__gt=0,
                    ).exists()
                    if not has_addon:
                        saved_chatbot.enable_web_search = False
                except Exception:
                    saved_chatbot.enable_web_search = False
            saved_chatbot.save()
            form.save_m2m()

            # Handle new file uploads (base plan + add-on stacking)
            uploaded_docs = request.FILES.getlist('pdf_files')
            current_doc_count = existing_docs.count()
            try:
                url_count = existing_urls.count() if existing_urls else 0
            except Exception:
                url_count = 0
            total_sources = current_doc_count + url_count
            try:
                from user_querySafe.addon_utils import get_effective_limits
                effective = get_effective_limits(user, active_plan, chatbot=chatbot)
                allowed_docs = effective['no_of_files']
            except Exception:
                allowed_docs = active_plan.no_of_files
            allowed_size_bytes = active_plan.file_size * 1024 * 1024
            ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.jpg', '.jpeg', '.png', '.gif', '.bmp'}

            successful_uploads = 0
            for doc in uploaded_docs:
                if total_sources + successful_uploads >= allowed_docs:
                    messages.warning(request, f"Document limit reached ({allowed_docs}).")
                    break
                ext = os.path.splitext(doc.name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    messages.error(request, f"'{doc.name}' has an unsupported type.")
                    continue
                if doc.size > allowed_size_bytes:
                    messages.error(request, f"'{doc.name}' exceeds size limit of {active_plan.file_size}MB.")
                    continue
                ChatbotDocument.objects.create(chatbot=chatbot, document=doc)
                successful_uploads += 1

            # Handle new URLs
            url_text = request.POST.get('website_urls', '').strip()
            sitemap_url = request.POST.get('sitemap_url', '').strip()
            new_url_count = 0

            try:
                from user_querySafe.models import ChatbotURL
                if url_text:
                    urls = [u.strip() for u in url_text.splitlines() if u.strip()]
                    for url in urls:
                        if total_sources + successful_uploads + new_url_count >= allowed_docs:
                            messages.warning(request, "Source limit reached.")
                            break
                        ChatbotURL.objects.get_or_create(
                            chatbot=chatbot, url=url,
                            defaults={'is_sitemap': False}
                        )
                        new_url_count += 1

                if sitemap_url:
                    ChatbotURL.objects.get_or_create(
                        chatbot=chatbot, url=sitemap_url,
                        defaults={'is_sitemap': True}
                    )
                    new_url_count += 1
            except Exception:
                pass  # ChatbotURL model not yet available

            # Handle email report subscription
            enable_reports = request.POST.get('enable_email_reports') == 'on'
            report_frequency = request.POST.get('report_frequency', 'weekly')
            report_email = request.POST.get('report_email', user.email).strip()

            if enable_reports:
                ChatbotEmailReport.objects.update_or_create(
                    chatbot=chatbot,
                    defaults={
                        'recipient_email': report_email or user.email,
                        'frequency': report_frequency,
                        'status': 'active',
                        'expiry_notice_sent': False,
                    }
                )
            else:
                ChatbotEmailReport.objects.filter(chatbot=chatbot).delete()

            # Handle goal plan settings if applicable
            try:
                goal_plan = GoalPlan.objects.get(chatbot=chatbot)
                goal_email = request.POST.get('goal_email', '').strip()
                goal_time = request.POST.get('goal_preferred_time', '')
                goal_plan.enable_emails = 'enable_goal_emails' in request.POST
                if goal_email:
                    goal_plan.recipient_email = goal_email
                if goal_time:
                    from datetime import time as dt_time
                    hour, minute = goal_time.split(':')
                    goal_plan.preferred_time = dt_time(int(hour), int(minute))
                goal_plan.save()
            except GoalPlan.DoesNotExist:
                pass

            Activity.log(user, f'Edited chatbot {chatbot.name}',
                         activity_type='info', icon='edit')
            messages.success(request, f"Chatbot '{chatbot.name}' updated successfully!")
            return redirect('edit_chatbot', chatbot_id=chatbot_id)
    else:
        form = ChatbotEditForm(instance=chatbot)

    # Fetch email report and goal plan for context
    try:
        email_report = ChatbotEmailReport.objects.get(chatbot=chatbot)
    except ChatbotEmailReport.DoesNotExist:
        email_report = None

    try:
        goal_plan = GoalPlan.objects.get(chatbot=chatbot)
    except GoalPlan.DoesNotExist:
        goal_plan = None

    # Check if user has an active web search add-on for this chatbot
    has_web_search_addon = False
    try:
        from user_querySafe.models import QSAddonPurchase
        has_web_search_addon = QSAddonPurchase.objects.filter(
            user=user,
            addon__addon_type='web_search',
            chatbot=chatbot,
            expire_date__gte=timezone.now().date(),
            status='active',
            quantity_remaining__gt=0,
        ).exists()
    except Exception:
        pass

    context = {
        'form': form,
        'chatbot': chatbot,
        'existing_docs': existing_docs,
        'existing_urls': existing_urls,
        'active_plan': active_plan,
        'email_report': email_report,
        'goal_plan': goal_plan,
        'user': user,
        'has_web_search_addon': has_web_search_addon,
    }
    return render(request, 'user_querySafe/edit_chatbot.html', context)


@login_required
@require_POST
def delete_document(request, document_id):
    user = User.objects.get(user_id=request.session['user_id'])
    doc = get_object_or_404(ChatbotDocument, id=document_id, chatbot__user=user)
    chatbot = doc.chatbot

    # Delete the physical file from disk
    file_path = os.path.join(PDF_DIR, doc.document.name)
    if os.path.exists(file_path):
        os.remove(file_path)

    doc.delete()

    remaining = ChatbotDocument.objects.filter(chatbot=chatbot).count()
    return JsonResponse({
        'success': True,
        'remaining_docs': remaining,
        'message': 'Document removed successfully.'
    })


@login_required
@require_POST
def retrain_chatbot(request, chatbot_id):
    user = User.objects.get(user_id=request.session['user_id'])
    chatbot = get_object_or_404(Chatbot, chatbot_id=chatbot_id, user=user)

    remaining_docs = ChatbotDocument.objects.filter(chatbot=chatbot).count()

    # Also check for URL sources
    try:
        from user_querySafe.models import ChatbotURL
        remaining_urls = ChatbotURL.objects.filter(chatbot=chatbot).count()
    except Exception:
        remaining_urls = 0

    if remaining_docs == 0 and remaining_urls == 0:
        messages.error(request, "Cannot retrain: no documents or URLs remain. Please add sources first.")
        return redirect('edit_chatbot', chatbot_id=chatbot_id)

    # Enforce retrain limit: base 4/month + add-on credits
    try:
        from user_querySafe.addon_utils import get_effective_limits, consume_addon_credit, BASE_RETRAINS_PER_MONTH

        # Count retrains this month using Activity log
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        retrains_this_month = Activity.objects.filter(
            user=user,
            title__startswith='Retrained chatbot',
            timestamp__gte=month_start,
        ).count()

        # Get active plan
        retrain_plan = QSPlanAllot.objects.filter(
            user=user,
            expire_date__gte=timezone.now().date()
        ).order_by('-created_at').first()

        if retrain_plan:
            effective = get_effective_limits(user, retrain_plan)
            effective_retrain_limit = effective['retrains']
        else:
            effective_retrain_limit = BASE_RETRAINS_PER_MONTH

        if retrains_this_month >= effective_retrain_limit:
            messages.error(
                request,
                f"You have used all {effective_retrain_limit} retrains this month. "
                f"Purchase extra retrains from the Add-ons page to continue."
            )
            return redirect('edit_chatbot', chatbot_id=chatbot_id)

        # If over base limit, consume an add-on credit
        if retrains_this_month >= BASE_RETRAINS_PER_MONTH:
            consume_addon_credit(user, 'extra_retrains')
    except Exception as retrain_err:
        print(f"Retrain limit check error (non-blocking): {retrain_err}")

    chatbot.status = 'training'
    chatbot.save()

    # Train in background thread so the page redirects immediately
    from .pipeline_processor import run_pipeline_background
    run_pipeline_background(chatbot.chatbot_id)
    messages.success(request, f"'{chatbot.name}' is being retrained! This usually takes a few minutes.")

    Activity.log(user, f'Retrained chatbot {chatbot.name}',
                 activity_type='info', icon='refresh')
    return redirect('my_chatbots')


@login_required
def preview_sitemap(request):
    """AJAX: Parse a sitemap URL and return discovered page URLs."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        sitemap_url = data.get('url', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not sitemap_url:
        return JsonResponse({'error': 'URL required'}, status=400)

    try:
        from user_querySafe.chatbot.url_scraper import parse_sitemap
        urls, error = parse_sitemap(sitemap_url)
        if error:
            return JsonResponse({'error': error}, status=400)
        return JsonResponse({'urls': urls[:100], 'total': len(urls)})
    except ImportError:
        return JsonResponse({'error': 'URL scraping module not available'}, status=500)


@login_required
@require_POST
def delete_url(request, url_id):
    user = User.objects.get(user_id=request.session['user_id'])
    try:
        from user_querySafe.models import ChatbotURL
        url_obj = get_object_or_404(ChatbotURL, id=url_id, chatbot__user=user)
        url_obj.delete()
        return JsonResponse({'success': True})
    except ImportError:
        return JsonResponse({'error': 'ChatbotURL model not available'}, status=500)
