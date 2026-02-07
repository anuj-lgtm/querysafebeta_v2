from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def project_name(request):
    return {"PROJECT_NAME": settings.PROJECT_NAME}


def engagement_data(request):
    """Inject user engagement metrics into all authenticated page renders."""
    context = {}
    user_id = request.session.get('user_id')
    if not user_id:
        return context

    from user_querySafe.models import User, Chatbot, Conversation, Message

    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return context

    now = timezone.now()

    # ── User greeting data ──────────────────────────────────────────
    context['engagement_first_name'] = user.name.split()[0] if user.name else 'there'

    # Returning user detection (set during login)
    previous_login_str = request.session.get('previous_login')
    context['is_first_visit'] = previous_login_str is None
    context['is_returning'] = previous_login_str is not None

    # ── Today's activity stats ──────────────────────────────────────
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    chatbots = Chatbot.objects.filter(user=user)

    context['conversations_today'] = Conversation.objects.filter(
        chatbot__in=chatbots,
        started_at__gte=today_start
    ).count()

    context['messages_today'] = Message.objects.filter(
        conversation__chatbot__in=chatbots,
        is_bot=True,
        timestamp__gte=today_start
    ).count()

    # ── Milestone detection ─────────────────────────────────────────
    total_conversations = Conversation.objects.filter(chatbot__in=chatbots).count()
    total_messages = Message.objects.filter(
        conversation__chatbot__in=chatbots, is_bot=True
    ).count()

    milestones = []
    for threshold in [10, 50, 100, 500, 1000]:
        if total_conversations >= threshold:
            milestones.append(f'{threshold}_conversations')
        if total_messages >= threshold:
            milestones.append(f'{threshold}_messages')

    # Only show milestones user hasn't seen yet (tracked in session)
    seen_milestones = set(request.session.get('seen_milestones', []))
    new_milestones = [m for m in milestones if m not in seen_milestones]
    if new_milestones:
        request.session['seen_milestones'] = list(seen_milestones | set(new_milestones))
    context['new_milestones'] = new_milestones

    context['total_conversations_all'] = total_conversations
    context['total_messages_all'] = total_messages

    return context
