import os
import json
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from user_querySafe.decorators import login_required
from user_querySafe.forms import ChatbotCreateForm, ChatbotEditForm
from user_querySafe.models import Activity, Chatbot, ChatbotDocument, User, QSPlanAllot
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

    context = {
        'chatbots': chatbots,
        'active_plan': active_plan,
        'chatbots_used': current_chatbots,
        'chatbots_total': active_plan.no_of_bot if active_plan else 0,
        'chatbots_remaining': (active_plan.no_of_bot - current_chatbots) if active_plan else 0,
        'show_toaster': False,
        'show_widget_guidance': show_widget_guidance,
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

    # Check if user reached chatbot limit
    current_chatbots = Chatbot.objects.filter(user=user).count()
    if current_chatbots >= active_plan.no_of_bot:
        messages.warning(
            request,
            f"You have reached your limit of {active_plan.no_of_bot} chatbots under the {active_plan.plan_name} plan. "
            f"Please contact us via Help & Support to upgrade."
        )
        return redirect('my_chatbots')

    if request.method == 'POST':
        form = ChatbotCreateForm(request.POST, request.FILES)
        if form.is_valid():
            chatbot = form.save(commit=False)
            chatbot.user = user
            chatbot.save()

            # Process document uploads
            uploaded_docs = request.FILES.getlist('pdf_files')
            allowed_docs = active_plan.no_of_files
            allowed_size_bytes = active_plan.file_size * 1024 * 1024

            if len(uploaded_docs) > allowed_docs:
                messages.error(request, f"You can upload a maximum of {allowed_docs} file(s) as per your subscription.")
                return redirect('create_chatbot')

            ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.bmp'}

            successful_uploads = 0
            for doc in uploaded_docs:
                # Validate file extension
                import os as _os
                ext = _os.path.splitext(doc.name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    messages.error(request, f"File '{doc.name}' has an unsupported type. Allowed: PDF, DOC, DOCX, TXT, JPG, PNG, GIF, BMP.")
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

            if successful_uploads > 0 or url_count > 0:
                # Trigger pipeline ONCE now that all documents/URLs are saved
                run_pipeline_background(chatbot.chatbot_id)
                messages.info(request, f"Chatbot '{chatbot.name}' created successfully! Training typically takes 1-3 minutes. You'll see the status change to 'Trained' once it's ready.")
                return redirect('my_chatbots')
            else:
                messages.error(request, "No documents or URLs were provided.")
                chatbot.delete()
                return redirect('create_chatbot')
    else:
        form = ChatbotCreateForm()

    context = {
        'form': form,
        'active_plan': active_plan,
    }
    return render(request, 'user_querySafe/create_chatbot.html', context)

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
            form.save()

            # Handle new file uploads
            uploaded_docs = request.FILES.getlist('pdf_files')
            current_doc_count = existing_docs.count()
            try:
                url_count = existing_urls.count() if existing_urls else 0
            except Exception:
                url_count = 0
            total_sources = current_doc_count + url_count
            allowed_docs = active_plan.no_of_files
            allowed_size_bytes = active_plan.file_size * 1024 * 1024
            ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.bmp'}

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

            Activity.log(user, f'Edited chatbot {chatbot.name}',
                         activity_type='info', icon='edit')
            messages.success(request, f"Chatbot '{chatbot.name}' updated successfully!")
            return redirect('edit_chatbot', chatbot_id=chatbot_id)
    else:
        form = ChatbotEditForm(instance=chatbot)

    context = {
        'form': form,
        'chatbot': chatbot,
        'existing_docs': existing_docs,
        'existing_urls': existing_urls,
        'active_plan': active_plan,
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

    chatbot.status = 'training'
    chatbot.save()

    run_pipeline_background(chatbot.chatbot_id)

    Activity.log(user, f'Retrained chatbot {chatbot.name}',
                 activity_type='info', icon='refresh')
    messages.info(request, f"Retraining '{chatbot.name}' started. This may take 1-3 minutes.")
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
