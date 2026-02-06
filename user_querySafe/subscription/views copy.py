from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from user_querySafe.decorators import login_required
from user_querySafe.models import Activity, Chatbot, ChatbotDocument, Message, User, QSPlan, QSOrder, QSCheckout, QSBillingDetails, QSPlanAllot
import random, string
from django.utils import timezone
from types import SimpleNamespace
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import razorpay
import json

@login_required
def usage_view(request):
    user = User.objects.get(user_id=request.session['user_id'])
    
    # Get active plan: prefer QSPlanAllot, fall back to legacy UserPlanAlot
    active_plan = None
    active_plan_obj = None

    # Try QSPlanAllot first (new QS plans)
    qs_allot = QSPlanAllot.objects.filter(
        user=user,
        expire_date__gte=timezone.now().date()
    ).order_by('-created_at').first()

    active_plan_obj = qs_allot
    active_plan = SimpleNamespace(
        plan_name=qs_allot.plan_name,
        no_query=qs_allot.no_of_query,
        no_of_docs=qs_allot.no_of_files,
        doc_size_limit=qs_allot.file_size,
        no_of_bot=qs_allot.no_of_bot,
        expire_date=qs_allot.expire_date
    ) if qs_allot else None
    
    if not active_plan:
        messages.warning(request, "You don't have an active plan. Please select one.")
        return redirect('subscriptions')

    # Get user's chatbots with their usage statistics
    chatbots = Chatbot.objects.filter(user=user)
    
    chatbot_stats = []
    if active_plan:  # Only calculate stats if there's an active plan
        for chatbot in chatbots:
            # Get messages and documents count for this chatbot
            messages_count = Message.objects.filter(conversation__chatbot=chatbot, is_bot=True).count()
            documents_count = ChatbotDocument.objects.filter(chatbot=chatbot).count()
            
            # Calculate percentages
            messages_percentage = min(100, (messages_count / active_plan.no_query * 100) if active_plan.no_query > 0 else 0)
            documents_percentage = min(100, (documents_count / active_plan.no_of_docs * 100) if active_plan.no_of_docs > 0 else 0)
            
            chatbot_stats.append({
                'chatbot': chatbot,
                'messages_count': messages_count,
                'documents_count': documents_count,
                'messages_limit': active_plan.no_query,
                'documents_limit': active_plan.no_of_docs,
                'doc_size_limit': active_plan.doc_size_limit,
                'messages_percentage': messages_percentage,
                'documents_percentage': documents_percentage
            })

        # Calculate account level statistics
        total_chatbots = chatbots.count()
        chatbot_percentage = min(100, (total_chatbots / active_plan.no_of_bot * 100) if active_plan.no_of_bot > 0 else 0)
    else:
        total_chatbots = 0
        chatbot_percentage = 0

    context = {
        'user': user,
        'active_plan': active_plan,
        'total_chatbots': total_chatbots,
        'no_of_bots_limit': active_plan.no_of_bot if active_plan else 0,
        'chatbot_percentage': chatbot_percentage,
        'chatbot_stats': chatbot_stats,
        'recent_activities': Activity.objects.filter(user=user).order_by('-timestamp')[:10],
        'expire_date': active_plan.expire_date if active_plan else None
    }
    
    return render(request, 'user_querySafe/usage.html', context)


def send_plan_activation_email(email, name, plan, start_date, expire_date, dashboard_url):
    try:
        subject = "Plan Activated Successfully"
        context = {
            'name': name,
            # You can dynamically pass these values from the plan
            'plan_name': plan.plan_name,
            'plan_limits': f"{plan.no_of_bot} Bot(s), {plan.no_query_per_bot} Queries per Bot, {plan.no_of_docs_per_bot} Document(s)",
            'start_date': start_date.strftime('%B %d, %Y'),
            'expire_date': expire_date.strftime('%B %d, %Y'),
            'dashboard_url': dashboard_url,
            'project_name': settings.PROJECT_NAME
        }
        html_message = render_to_string("user_querySafe/email/plan-activate.html", context)
        plain_message = (
            f"Hello {name},\n\n"
            f"Your plan '{plan.plan_name}' has been activated successfully.\n"
            f"Plan Limits: {plan.no_of_bot} Bot(s), {plan.no_query_per_bot} Queries per Bot, {plan.no_of_docs_per_bot} Document(s)\n"
            f"Start Date: {start_date.strftime('%B %d, %Y')}\n"
            f"Valid Till: {expire_date.strftime('%B %d, %Y')}\n\n"
            f"Go to your dashboard: {dashboard_url}\n\n"
            "Thank you for subscribing to QuerySafe."
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
        print(f"Error sending plan activation email: {str(e)}")
        return False


@login_required
def subscription_view(request):
    user = None
    try:
        user = User.objects.get(user_id=request.session.get('user_id'))
    except Exception:
        user = None

    is_first_time_qs = True
    if user:
        user_orders = QSOrder.objects.filter(user=user)
        if user_orders.filter(status__in=['completed', 'pending']).exists():
            is_first_time_qs = False
        else:
            # If there are no orders or only failed orders, keep as first-time
            is_first_time_qs = True

    # Show trial plans to first-time users; otherwise show non-trial plans
    qs_plans = QSPlan.objects.filter(is_trial=is_first_time_qs, status='public').order_by('amount')

    context = {
        'qs_plans': qs_plans,
        'is_first_time_qs': is_first_time_qs,
    }
    return render(request, 'user_querySafe/subscriptions.html', context)



@login_required
def checkout(request):
    if request.method != 'POST':
        messages.warning(request, 'Invalid access to checkout.')
        return redirect('subscriptions')

    user = None
    try:
        user = User.objects.get(user_id=request.session.get('user_id'))
    except Exception:
        messages.error(request, 'Please login to continue.')
        return redirect('login')

    plan_id = request.POST.get('plan_id')
    plan_obj = QSPlan.objects.filter(plan_id=plan_id, status='public').first()
    
    if not plan_obj:
        messages.error(request, 'Selected plan not found.')
        return redirect('subscriptions')

    # Generate unique checkout_id
    def gen_id(length=10):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    checkout_id = gen_id()
    while QSCheckout.objects.filter(checkout_id=checkout_id).exists():
        checkout_id = gen_id()

    # Create QSCheckout record immediately
    checkout = QSCheckout.objects.create(
        checkout_id=checkout_id,
        user=user,
        plan=plan_obj
    )

    # Build plan context from DB object
    plan_context = {
        'plan_id': plan_obj.plan_id,
        'plan_name': plan_obj.plan_name,
        'amount': plan_obj.amount,
        'currency': plan_obj.currency,
        'days': plan_obj.days,
        'is_trial': plan_obj.is_trial,
        'parent_plan': plan_obj.parent_plan,
        'no_of_bot': plan_obj.no_of_bot,
        'no_of_query': plan_obj.no_of_query,
        'no_of_file': plan_obj.no_of_file,
        'max_file_size': plan_obj.max_file_size,
    }

    # Prefill billing details from logged-in user
    billing_defaults = {
        'full_name': user.name,
        'email': user.email,
    }

    context = {
        'plan': plan_context,
        'billing_defaults': billing_defaults,
        'checkout_id': checkout.checkout_id,
        'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }

    return render(request, 'user_querySafe/checkout.html', context)


@login_required
def qs_initiate_payment(request):
    if request.method != 'POST':
        messages.warning(request, 'Invalid access to payment.')
        return redirect('subscriptions')

    user = None
    try:
        user = User.objects.get(user_id=request.session.get('user_id'))
    except Exception:
        messages.error(request, 'Please login to continue.')
        return redirect('login')

    checkout_id = request.POST.get('checkout_id')
    checkout = QSCheckout.objects.filter(checkout_id=checkout_id, user=user).first()
    
    if not checkout:
        messages.error(request, 'Checkout session not found.')
        return redirect('subscriptions')

    plan = checkout.plan

    # Generate unique billing_id
    def gen_id(length=10):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    billing_id = gen_id()
    while QSBillingDetails.objects.filter(billing_id=billing_id).exists():
        billing_id = gen_id()

    # Read billing fields from POST
    full_name = request.POST.get('full_name', user.name if user else '')
    email = request.POST.get('email', user.email if user else '')
    phone = request.POST.get('phone', '')
    address = request.POST.get('address', '')
    city = request.POST.get('city', '')
    state = request.POST.get('state', '')
    pin = request.POST.get('pin', '')

    # Create billing details linked to existing checkout
    billing = QSBillingDetails.objects.create(
        billing_id=billing_id,
        checkout=checkout,
        full_name=full_name,
        email=email,
        phone=phone,
        address=address,
        city=city,
        state=state,
        pin=pin
    )

    messages.success(request, f'Billing details saved. Proceeding to payment...')
    # Redirect to payment page with checkout_id (QSOrder will be created after Razorpay order)
    return redirect('qs_payment_page', checkout_id=checkout_id)


@login_required
def qs_payment_page(request, checkout_id):
    user = None
    try:
        user = User.objects.get(user_id=request.session.get('user_id'))
    except Exception:
        messages.error(request, 'Please login to continue.')
        return redirect('login')

    checkout = QSCheckout.objects.filter(checkout_id=checkout_id, user=user).first()
    if not checkout:
        messages.error(request, 'Checkout session not found.')
        return redirect('subscriptions')

    plan = checkout.plan
    billing = checkout.billing_details.first()

    context = {
        'checkout_id': checkout_id,
        'plan': plan,
        'checkout': checkout,
        'billing': billing,
        'amount': plan.amount,
        'user': user,
        'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }

    return render(request, 'user_querySafe/qs_payment.html', context)


@login_required
def create_qs_order_api(request):
    """API endpoint to create a Razorpay order for QS plans.
    Called via AJAX/fetch from qs_payment.html.
    Creates QSOrder with razorpay_order_id as the order_id (single source of truth).
    Returns JSON: {'razorpay_order_id': '...', 'amount': ...}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

    try:
        import razorpay
        import json
        data = json.loads(request.body)
        checkout_id = data.get('checkout_id')
        amount = data.get('amount')

        if not checkout_id or not amount:
            return JsonResponse({'status': 'error', 'message': 'Missing checkout_id or amount'}, status=400)

        # Get checkout and plan
        user = User.objects.get(user_id=request.session.get('user_id'))
        checkout = QSCheckout.objects.filter(checkout_id=checkout_id, user=user).first()
        
        if not checkout:
            return JsonResponse({'status': 'error', 'message': 'Checkout not found'}, status=400)

        plan = checkout.plan

        # Create Razorpay order FIRST
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        amount_paise = int(float(amount) * 100)

        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': checkout_id,
            'payment_capture': 1,
            'notes': {
                'checkout_id': checkout_id,
                'user_id': user.user_id,
                'user_name': user.name,
                'user_email': user.email,
                'plan_id': plan.plan_id,
                'plan_name': plan.plan_name,
            }
        }

        razorpay_order = client.order.create(data=order_data)
        razorpay_order_id = razorpay_order.get('id')

        # NOW create QSOrder with razorpay_order_id as the order_id
        # This is the single source of truth for order ID
        qs_order = QSOrder.objects.create(
            order_id=razorpay_order_id,  # Use Razorpay's order ID as our order ID
            checkout=checkout,
            user=user,
            plan=plan,
            amount=float(amount),
            status='pending'
        )

        # Log activity
        Activity.log(user, 'Razorpay Order Created', f'Order {razorpay_order_id} created for plan {plan.plan_name}', 'primary', 'info')

        return JsonResponse({
            'razorpay_order_id': razorpay_order_id,
            'amount': amount_paise,
            'plan_name': plan.plan_name,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'}, status=500)


@csrf_exempt
def verify_qs_payment(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

    import razorpay
    
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')
    # allow both formats
    error_code = request.POST.get('error[code]') or request.POST.get('error_code')
    error_description = request.POST.get('error[description]') or request.POST.get('error_description')
    # fallback: checkout id (from our hidden form) if order id missing
    checkout_id = request.POST.get('checkout_id') or request.POST.get('checkout')

    print(f"[Razorpay Callback] order_id={razorpay_order_id}, payment_id={razorpay_payment_id}, error={error_code}, checkout={checkout_id}")

    # Resolve QSOrder: prefer razorpay_order_id, fallback to checkout_id
    qs_order = None
    if razorpay_order_id:
        qs_order = QSOrder.objects.filter(order_id=razorpay_order_id).first()
    if not qs_order and checkout_id:
        qs_order = QSOrder.objects.filter(checkout__checkout_id=checkout_id).first()
        if qs_order:
            # populate razorpay_order_id for later redirects
            razorpay_order_id = qs_order.order_id

    # If still not found, show generic status page (no order)
    if not qs_order:
        print(f"[verify_qs_payment] QSOrder not found for order_id={razorpay_order_id} checkout={checkout_id}")
        # Redirect to unified payment status page without order id
        return redirect('qs_payment_status_noid')

    # ============ CASE 1: PAYMENT FAILED ============
    if error_code or not razorpay_payment_id or not razorpay_signature:
        print(f"[Payment Failed] order_id={razorpay_order_id} (resolved via checkout: {checkout_id})")

        qs_order.status = 'failed'
        qs_order.razorpay_error_code = error_code or 'PAYMENT_FAILED'
        qs_order.razorpay_error_description = error_description or 'Payment could not be processed'
        qs_order.save()

        Activity.log(qs_order.user, 'Payment Failed', f'Order {qs_order.order_id}: {error_description or error_code}', 'danger', 'warning')

        # Redirect to unified payment status page with order id
        return redirect('qs_payment_status', order_id=razorpay_order_id)

    # ============ CASE 2: PAYMENT SUCCESS ============
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })

        print(f"[Payment Success] order_id={razorpay_order_id}, signature verified")

        # Update order to completed
        qs_order.razorpay_payment_id = razorpay_payment_id
        qs_order.razorpay_signature_id = razorpay_signature
        qs_order.status = 'completed'
        qs_order.save()

        # Activate plan
        user = qs_order.user
        plan = qs_order.plan
        start_date = timezone.now().date()
        expire_date = start_date + timedelta(days=plan.days)

        # Generate unique plan_allot_id
        def gen_id(length=8):
            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

        plan_allot_id = gen_id()
        while QSPlanAllot.objects.filter(plan_allot_id=plan_allot_id).exists():
            plan_allot_id = gen_id()

        # Create plan allocation
        QSPlanAllot.objects.create(
            plan_allot_id=plan_allot_id,
            user=user,
            parent_plan=plan,
            order=qs_order,
            plan_name=plan.plan_name,
            no_of_bot=plan.no_of_bot,
            no_of_query=plan.no_of_query,
            no_of_files=plan.no_of_file,
            file_size=plan.max_file_size,
            start_date=start_date,
            expire_date=expire_date
        )

        # Redirect to unified payment status page with order id (successful)
        return redirect('qs_payment_status', order_id=qs_order.order_id)

    except razorpay.BadRequestsError as e:
        # Signature verification failed = payment failed
        print(f"[Payment Failed - Signature] order_id={razorpay_order_id}, error={str(e)}")

        qs_order.status = 'failed'
        qs_order.razorpay_error_code = 'SIGNATURE_MISMATCH'
        qs_order.razorpay_error_description = 'Payment verification failed'
        qs_order.save()

        Activity.log(qs_order.user, 'Payment Failed', f'Order {qs_order.order_id}: Signature verification failed', 'danger', 'warning')

        return redirect('qs_payment_status', order_id=qs_order.order_id)

    except Exception as e:
        # Any other error
        print(f"[Payment Failed - Exception] order_id={razorpay_order_id}, error={str(e)}")

        qs_order.status = 'failed'
        qs_order.razorpay_error_code = 'ERROR'
        qs_order.razorpay_error_description = str(e)[:200]
        qs_order.save()

        Activity.log(qs_order.user, 'Payment Failed', f'Order {qs_order.order_id}: {str(e)[:100]}', 'danger', 'error')

        return redirect('qs_payment_status', order_id=qs_order.order_id)


@login_required
def qs_payment_success(request, order_id):
    """Display payment success page after successful payment."""
    user = User.objects.get(user_id=request.session.get('user_id'))
    
    # Get the order
    order = QSOrder.objects.filter(order_id=order_id, user=user).first()
    
    if not order:
        messages.error(request, 'Order not found.')
        return redirect('subscriptions')
    
    if order.status != 'completed':
        messages.warning(request, 'This order was not completed successfully.')
        return redirect('subscriptions')
    
    # Get the activated plan allot
    plan_allot = QSPlanAllot.objects.filter(order=order).first()
    
    context = {
        'order': order,
        'plan_allot': plan_allot,
        'user': user,
    }
    
    return render(request, 'user_querySafe/qs_payment_success.html', context)


@login_required
def qs_payment_failed(request, order_id=None):
    """Display payment failure page after failed payment."""
    user = User.objects.get(user_id=request.session.get('user_id'))
    
    order = None
    error_message = 'Payment could not be processed.'
    error_code = None
    
    if order_id:
        order = QSOrder.objects.filter(order_id=order_id, user=user).first()
        
        if order:
            error_code = order.razorpay_error_code or 'UNKNOWN_ERROR'
            error_message = order.razorpay_error_description or 'Payment processing failed. Please try again.'
    
    context = {
        'order': order,
        'error_message': error_message,
        'error_code': error_code,
        'user': user,
    }
    
    return render(request, 'user_querySafe/qs_payment_failed.html', context)


@login_required
def qs_payment_status(request, order_id=None):
    """Unified payment status page. Shows success or failure details for a QS order.
    If no order_id is provided, shows a generic status/info page.
    """
    user = User.objects.get(user_id=request.session.get('user_id'))

    order = None
    status = 'unknown'
    message = 'Payment status not available.'
    error_code = None

    if order_id:
        order = QSOrder.objects.filter(order_id=order_id, user=user).first()
        if order:
            status = order.status
            if order.status == 'completed':
                message = 'Payment completed successfully.'
            elif order.status == 'failed':
                message = order.razorpay_error_description or 'Payment failed.'
                error_code = order.razorpay_error_code
            else:
                message = 'Payment is pending. Please wait a moment and refresh.'

    context = {
        'user': user,
        'order': order,
        'status': status,
        'message': message,
        'error_code': error_code,
    }

    return render(request, 'user_querySafe/qs_payment_status.html', context)


@login_required
def order_history(request):
    user = User.objects.get(user_id=request.session['user_id'])

    # Get Type 2 orders (QSPlan / QSOrder)
    type2_orders = QSOrder.objects.filter(user=user).select_related('plan').order_by('-created_at')
    
    # Build combined order list
    all_orders = []
    

    # Process Type 2 orders (QS orders)
    for o in type2_orders:
        expiry = None
        try:
            # Get linked plan allotment if available
            plan_allot = o.plan_allots.first()
            if plan_allot:
                expiry = plan_allot.expire_date
        except Exception:
            pass
        
        all_orders.append({
            'order_id': o.order_id,
            'amount': o.amount,
            'status': o.status,
            'plan_name': o.plan.plan_name if o.plan else 'N/A',
            'created_at': o.created_at,
            'expiry': expiry,
            'error_code': o.razorpay_error_code,
            'error_desc': o.razorpay_error_description,
        })
    
    # Sort combined list by created_at (newest first)
    all_orders.sort(key=lambda x: x['created_at'], reverse=True)
    
    context = {
        'orders': all_orders,
        'user': user,
    }
    
    return render(request, 'user_querySafe/order_history.html', context)

    context = {
        'user': user,
        'orders': all_orders,
    }
    return render(request, 'user_querySafe/order_history.html', context)
