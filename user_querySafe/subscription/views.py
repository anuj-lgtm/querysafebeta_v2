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
        from django.core.mail import EmailMessage as EM
        subject = "Plan Activated Successfully"
        context = {
            'name': name,
            'plan_name': plan.plan_name,
            'plan_limits': f"{getattr(plan, 'no_of_bot', 0)} Bot(s), {getattr(plan, 'no_of_query', 0)} Queries, {getattr(plan, 'no_of_file', 0)} Document(s)",
            'start_date': start_date.strftime('%B %d, %Y'),
            'expire_date': expire_date.strftime('%B %d, %Y'),
            'dashboard_url': dashboard_url,
            'project_name': settings.PROJECT_NAME
        }
        html_message = render_to_string("user_querySafe/email/plan-activate.html", context)

        # Use EmailMessage for CC support
        msg = EM(
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

    # Get active plan for "Current Plan" badge
    active_allot = None
    if user:
        active_allot = QSPlanAllot.objects.filter(
            user=user,
            expire_date__gte=timezone.now().date(),
        ).order_by('-created_at').first()

    context = {
        'qs_plans': qs_plans,
        'is_first_time_qs': is_first_time_qs,
        'active_allot': active_allot,
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

    # Prefill billing details from the user's most recent saved billing (if any)
    latest_billing = QSBillingDetails.objects.filter(checkout__user=user).order_by('-created_at').first()
    if latest_billing:
        billing_defaults = {
            'full_name': latest_billing.full_name or user.name,
            'email': latest_billing.email or user.email,
            'phone': latest_billing.phone or '',
            'address': latest_billing.address or '',
            'city': latest_billing.city or '',
            'state': latest_billing.state or '',
            'pin': latest_billing.pin or '',
        }
    else:
        billing_defaults = {
            'full_name': user.name,
            'email': user.email,
            'phone': '',
            'address': '',
            'city': '',
            'state': '',
            'pin': '',
        }

    context = {
        'plan': plan_context,
        'billing_defaults': billing_defaults,
        'checkout_id': checkout.checkout_id,
        'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }

    return render(request, 'user_querySafe/checkout.html', context)

@login_required
def order_payment(request):
    user = User.objects.get(user_id=request.session.get('user_id'))

    # Accept checkout_id via GET or POST
    checkout_id = request.GET.get('checkout_id') or request.POST.get('checkout_id')
    checkout = None
    if checkout_id:
        checkout = QSCheckout.objects.filter(checkout_id=checkout_id, user=user).select_related('plan').first()

    if not checkout:
        messages.warning(request, 'Invalid or missing checkout reference.')
        return redirect('subscriptions')

    plan = checkout.plan

    # If billing form submitted, save billing details and create Razorpay order + QSOrder
    razorpay_order_id = None
    amount_paise = int(getattr(plan, 'amount', 0) * 100)
    currency = getattr(plan, 'currency', 'INR')

    if request.method == 'POST':
        # Read billing details from form
        full_name = request.POST.get('full_name') or request.POST.get('billing_full_name') or ''
        email = request.POST.get('email') or ''
        phone = request.POST.get('phone') or ''
        address = request.POST.get('address') or ''
        city = request.POST.get('city') or ''
        state = request.POST.get('state') or ''
        pin = request.POST.get('pin') or ''

        # Generate billing_id
        def gen_billing_id(length=8):
            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

        billing_id = gen_billing_id()
        while QSBillingDetails.objects.filter(billing_id=billing_id).exists():
            billing_id = gen_billing_id()

        # Save billing details
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

        # If plan amount is zero (free plan), skip Razorpay and create order+allotment immediately
        try:
            if float(getattr(plan, 'amount', 0) or 0) == 0:
                # Create a local order id for free orders
                free_order_id = f"free_{checkout.checkout_id}_{int(timezone.now().timestamp())}"
                qs_order = QSOrder.objects.create(
                    order_id=free_order_id,
                    checkout=checkout,
                    user=user,
                    plan=plan,
                    amount=0.0,
                    status='completed'
                )

                # Create plan allotment immediately (avoid duplicates)
                try:
                    if not QSPlanAllot.objects.filter(order=qs_order).exists():
                        def gen_plan_allot_id(length=8):
                            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

                        plan_allot_id = gen_plan_allot_id()
                        while QSPlanAllot.objects.filter(plan_allot_id=plan_allot_id).exists():
                            plan_allot_id = gen_plan_allot_id()

                        plan_obj = qs_order.plan
                        start_date = timezone.now().date()
                        expire_date = start_date + timedelta(days=getattr(plan_obj, 'days', 0))

                        QSPlanAllot.objects.create(
                            plan_allot_id=plan_allot_id,
                            user=qs_order.user,
                            parent_plan=plan_obj,
                            order=qs_order,
                            plan_name=plan_obj.plan_name,
                            no_of_bot=getattr(plan_obj, 'no_of_bot', 0),
                            no_of_query=getattr(plan_obj, 'no_of_query', 0),
                            no_of_files=getattr(plan_obj, 'no_of_file', 0),
                            file_size=getattr(plan_obj, 'max_file_size', 0),
                            start_date=start_date,
                            expire_date=expire_date
                        )

                        # Send plan activation email
                        try:
                            dashboard_url = request.build_absolute_uri(reverse('dashboard'))
                            send_plan_activation_email(
                                user.email, user.name, plan_obj,
                                start_date, expire_date, dashboard_url
                            )
                        except Exception as email_err:
                            print(f"Plan activation email error (free): {email_err}")

                        # Update session so the user sees the new plan immediately
                        try:
                            if 'user_id' not in request.session:
                                request.session['user_id'] = qs_order.user.user_id
                        except Exception:
                            pass

                        if request.session.get('user_id') == qs_order.user.user_id:
                            request.session.pop('active_plan', None)
                            request.session.pop('active_plan_expire', None)
                            request.session.pop('active_plan_details', None)
                            request.session['active_plan'] = plan_obj.plan_name
                            request.session['active_plan_expire'] = str(expire_date)
                            request.session['active_plan_details'] = {
                                'no_of_bot': getattr(plan_obj, 'no_of_bot', 0),
                                'no_of_query': getattr(plan_obj, 'no_of_query', 0),
                                'no_of_files': getattr(plan_obj, 'no_of_file', 0),
                                'file_size': getattr(plan_obj, 'max_file_size', 0),
                            }
                            request.session.modified = True

                except Exception as ee:
                    print(f"Error creating plan allot for free order: {ee}")

                # Redirect to order-status page with the order id so the user sees the status page
                return redirect(f"{reverse('payment_status')}?order_id={qs_order.order_id}")

            # Otherwise, create Razorpay order now
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            # Build notes payload to help identify the order in Razorpay dashboard/webhooks
            notes = {
                'checkout_id': checkout.checkout_id,
                'plan_id': getattr(plan, 'plan_id', ''),
                'plan_name': getattr(plan, 'plan_name', ''),
                'customer_name': full_name,
                'customer_email': email,
                'customer_phone': phone,
            }
            order_data = {
                "amount": amount_paise,
                "currency": currency,
                "receipt": checkout.checkout_id,
                "payment_capture": 1,
                "notes": notes,
            }
            razorpay_order = razorpay_client.order.create(data=order_data)
            razorpay_order_id = razorpay_order.get('id')

            # Save QSOrder
            QSOrder.objects.create(
                order_id=razorpay_order_id,
                checkout=checkout,
                user=user,
                plan=plan,
                amount=plan.amount,
                status='pending'
            )
        except Exception as e:
            print(f"Error creating Razorpay order in order_payment: {e}")

    else:
        # GET: try to find existing QSOrder for this checkout
        qs_order = checkout.orders.order_by('-created_at').first()
        if qs_order:
            razorpay_order_id = qs_order.order_id
            try:
                amount_paise = int(qs_order.amount * 100)
            except Exception:
                amount_paise = int(getattr(plan, 'amount', 0) * 100)

    # Determine billing defaults to pass to payment page (use billing just created, or checkout-specific, or user)
    if 'billing' in locals() and billing:
        billing_defaults_page = {
            'full_name': billing.full_name or user.name,
            'email': billing.email or user.email,
            'phone': billing.phone or '',
            'address': billing.address or '',
            'city': billing.city or '',
            'state': billing.state or '',
            'pin': billing.pin or '',
        }
    else:
        latest_billing = QSBillingDetails.objects.filter(checkout=checkout).order_by('-created_at').first()
        if not latest_billing:
            latest_billing = QSBillingDetails.objects.filter(checkout__user=user).order_by('-created_at').first()

        if latest_billing:
            billing_defaults_page = {
                'full_name': latest_billing.full_name or user.name,
                'email': latest_billing.email or user.email,
                'phone': latest_billing.phone or '',
                'address': latest_billing.address or '',
                'city': latest_billing.city or '',
                'state': latest_billing.state or '',
                'pin': latest_billing.pin or '',
            }
        else:
            billing_defaults_page = {
                'full_name': user.name,
                'email': user.email,
                'phone': '',
                'address': '',
                'city': '',
                'state': '',
                'pin': '',
            }

    context = {
        'user': user,
        'checkout': checkout,
        'plan': {
            'plan_id': getattr(plan, 'plan_id', ''),
            'plan_name': getattr(plan, 'plan_name', ''),
            'amount': getattr(plan, 'amount', 0),
            'currency': currency,
            'days': getattr(plan, 'days', 0),
            'is_trial': getattr(plan, 'is_trial', False),
        },
        'billing_defaults': billing_defaults_page,
        'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'razorpay_order_id': razorpay_order_id,
        'amount_paise': amount_paise,
        'currency': currency,
        'project_name': getattr(settings, 'PROJECT_NAME', 'QuerySafe'),
    }

    return render(request, 'user_querySafe/payment_page.html', context)

@csrf_exempt
def payment_status(request):
    # Accept POST/GET from Razorpay Checkout callback, verify signature, update QSOrder, and display result.

    # --- Authentication guard ---
    # GET requests (viewing order status) require a logged-in user.
    # POST requests (Razorpay callback) are allowed through so the order can be
    # updated, but the rendered page will only show billing details if the
    # session user owns the order.
    session_user_id = request.session.get('user_id')
    if request.method == 'GET' and not session_user_id:
        messages.error(request, 'Please log in to view your order status.')
        return redirect('login')

    raw_body = request.body.decode('utf-8', errors='replace') if request.body else ''

    # Collect params from POST or GET
    params = {}
    if request.method == 'POST' and request.POST:
        params.update({k: v for k, v in request.POST.items()})
    elif request.method == 'GET' and request.GET:
        params.update({k: v for k, v in request.GET.items()})
    else:
        # Try parse urlencoded raw body
        try:
            from urllib.parse import parse_qs
            parsed = parse_qs(raw_body)
            for k, v in parsed.items():
                # take first value for simplicity
                params[k] = v[0] if isinstance(v, list) and v else v
        except Exception:
            pass

    # Prepare a pretty JSON for display
    try:
        post_json = json.dumps(params, indent=2)
    except Exception:
        post_json = str(params)

    # Extract key Razorpay fields if present
    razorpay_payment_id = params.get('razorpay_payment_id') or params.get('payment_id')
    razorpay_order_id = params.get('razorpay_order_id') or params.get('order_id')
    razorpay_signature = params.get('razorpay_signature') or params.get('signature')

    # If metadata exists inside error payload (failed payments), extract payment/order ids from it
    if not razorpay_payment_id or not razorpay_order_id:
        meta_raw = params.get('error[metadata]') or params.get('error_metadata') or None
        if meta_raw:
            try:
                # meta_raw may be a JSON string (urlencoded) or already dict-like string
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                if not razorpay_payment_id and isinstance(meta, dict) and meta.get('payment_id'):
                    razorpay_payment_id = meta.get('payment_id')
                if not razorpay_order_id and isinstance(meta, dict) and meta.get('order_id'):
                    razorpay_order_id = meta.get('order_id')
            except Exception:
                try:
                    # try decode urlencoded then parse
                    from urllib.parse import unquote_plus
                    decoded = unquote_plus(meta_raw)
                    meta = json.loads(decoded)
                    if not razorpay_payment_id and isinstance(meta, dict) and meta.get('payment_id'):
                        razorpay_payment_id = meta.get('payment_id')
                    if not razorpay_order_id and isinstance(meta, dict) and meta.get('order_id'):
                        razorpay_order_id = meta.get('order_id')
                except Exception:
                    pass

    result = {
        'verified': False,
        'updated': False,
        'message': '',
        'order': None,
        'params': params,
    }

    # Try to verify signature if we have the required fields
    if razorpay_order_id and razorpay_payment_id and razorpay_signature:
        try:
            client = razorpay.Client(auth=(getattr(settings, 'RAZORPAY_KEY_ID', ''), getattr(settings, 'RAZORPAY_KEY_SECRET', '')))
            utility = client.utility
            utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            result['verified'] = True
            result['message'] = 'Signature verification succeeded.'
        except Exception as e:
            result['verified'] = False
            result['message'] = f'Signature verification failed: {str(e)}'

    # Update QSOrder in DB if we can find it (by order_id)
    try:
        qs_order = None
        if razorpay_order_id:
            qs_order = QSOrder.objects.filter(order_id=razorpay_order_id).first()
        # If not found and error metadata contains order_id, try to extract
        if not qs_order and 'error[metadata]' in params:
            try:
                meta = json.loads(params.get('error[metadata]'))
                order_from_meta = meta.get('order_id')
                if order_from_meta:
                    qs_order = QSOrder.objects.filter(order_id=order_from_meta).first()
            except Exception:
                pass

        if qs_order:
            # Update fields based on verification and incoming params
            if razorpay_payment_id:
                qs_order.razorpay_payment_id = razorpay_payment_id
            if razorpay_signature:
                qs_order.razorpay_signature_id = razorpay_signature

            # If there is an error payload, save error fields
            if 'error[code]' in params:
                qs_order.razorpay_error_code = params.get('error[code]')
            if 'error[description]' in params:
                qs_order.razorpay_error_description = params.get('error[description]')

            # Determine if this is a free/local order (created by system) and should not be marked failed
            is_free_order = False
            try:
                is_free_order = (float(qs_order.amount or 0) == 0) or (str(qs_order.order_id).startswith('free_'))
            except Exception:
                is_free_order = False

            # Set status according to verification / presence of errors, but do NOT mark free orders as failed
            if is_free_order:
                qs_order.status = 'completed'
            else:
                if result.get('verified'):
                    qs_order.status = 'completed'
                else:
                    # If an explicit error present or verification failed, mark failed
                    if params.get('error[reason]') or params.get('error[code]') or not result.get('verified'):
                        qs_order.status = 'failed'

            qs_order.save()
            result['updated'] = True
            result['order'] = {
                'order_id': qs_order.order_id,
                'status': qs_order.status,
                'payment_id': qs_order.razorpay_payment_id,
            }
            # If payment completed, create a QSPlanAllot for the user if not already created
            try:
                if qs_order.status == 'completed':
                    # avoid duplicates
                    if not QSPlanAllot.objects.filter(order=qs_order).exists():
                        def gen_plan_allot_id(length=8):
                            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

                        plan_allot_id = gen_plan_allot_id()
                        while QSPlanAllot.objects.filter(plan_allot_id=plan_allot_id).exists():
                            plan_allot_id = gen_plan_allot_id()

                        plan = qs_order.plan
                        start_date = timezone.now().date()
                        expire_date = start_date + timedelta(days=getattr(plan, 'days', 0))

                        QSPlanAllot.objects.create(
                            plan_allot_id=plan_allot_id,
                            user=qs_order.user,
                            parent_plan=plan,
                            order=qs_order,
                            plan_name=plan.plan_name,
                            no_of_bot=getattr(plan, 'no_of_bot', 0),
                            no_of_query=getattr(plan, 'no_of_query', 0),
                            no_of_files=getattr(plan, 'no_of_file', 0),
                            file_size=getattr(plan, 'max_file_size', 0),
                            start_date=start_date,
                            expire_date=expire_date
                        )
                        result['plan_allot_created'] = True

                        # Send plan activation email
                        try:
                            dashboard_url = request.build_absolute_uri(reverse('dashboard'))
                            send_plan_activation_email(
                                qs_order.user.email, qs_order.user.name, plan,
                                start_date, expire_date, dashboard_url
                            )
                        except Exception as email_err:
                            print(f"Plan activation email error (paid): {email_err}")
            except Exception as e:
                result['message'] = result.get('message', '') + f' (Plan allot error: {e})'

            # If plan allotment was created, update session so user sees new plan immediately
            try:
                if result.get('plan_allot_created'):
                    # Fetch the newly created plan allotment
                    plan_allot = QSPlanAllot.objects.filter(order=qs_order).first()
                    if plan_allot:
                        # If no user is in session, set the purchaser as logged-in for this session
                        if 'user_id' not in request.session:
                            try:
                                request.session['user_id'] = qs_order.user.user_id
                            except Exception:
                                pass

                        # Only update plan-related session if session user matches order user (or we just set it)
                        if request.session.get('user_id') == qs_order.user.user_id:
                            # Clear old plan-related session variables
                            request.session.pop('active_plan', None)
                            request.session.pop('active_plan_expire', None)
                            request.session.pop('active_plan_details', None)

                            # Set new plan-related session variables
                            request.session['active_plan'] = plan_allot.plan_name
                            request.session['active_plan_expire'] = str(plan_allot.expire_date)
                            request.session['active_plan_details'] = {
                                'no_of_bot': plan_allot.no_of_bot,
                                'no_of_query': plan_allot.no_of_query,
                                'no_of_files': plan_allot.no_of_files,
                                'file_size': plan_allot.file_size,
                            }
                            # Mark session modified
                            request.session.modified = True
            except Exception as e:
                print(f"Error updating session with new plan: {e}")
    except Exception as e:
        # don't crash the view; show error in the page
        result['message'] = result.get('message', '') + f' (DB update error: {e})'
    # If no QSOrder could be matched, redirect to order history (user can inspect there)
    if not qs_order:
        try:
            return redirect('order_history')
        except Exception:
            # fallback to rendering page when redirect isn't possible
            context = {
                'method': request.method,
                'raw_body': raw_body,
                'post_json': post_json,
                'get_params': dict(request.GET),
                'result': result,
            }
            return render(request, 'user_querySafe/payment_status.html', context)

    # --- Ownership check ---
    # Only show full order details (billing info, etc.) if the logged-in user
    # owns this order. This prevents unauthorized users from viewing billing
    # details by guessing order IDs.
    is_owner = False
    if session_user_id and qs_order:
        is_owner = (qs_order.user.user_id == session_user_id)

    if not is_owner:
        # Not the owner: show only the order status, no billing details
        context = {
            'result': result,
            'order_obj': qs_order,
            'payment_info': {
                'status': qs_order.status,
                'amount': qs_order.amount,
            },
        }
        return render(request, 'user_querySafe/payment_status.html', context)

    # Build structured data to present on the order status page
    billing = None
    try:
        billing = QSBillingDetails.objects.filter(checkout=qs_order.checkout).order_by('-created_at').first()
    except Exception:
        billing = None

    plan_obj = qs_order.plan
    customer = qs_order.user
    payment_info = {
        'payment_id': qs_order.razorpay_payment_id,
        'signature': qs_order.razorpay_signature_id,
        'error_code': qs_order.razorpay_error_code,
        'error_description': qs_order.razorpay_error_description,
        'amount': qs_order.amount,
        'status': qs_order.status,
        'created_at': qs_order.created_at,
    }

    context = {
        'method': request.method,
        'result': result,
        'order_obj': qs_order,
        'plan_obj': plan_obj,
        'billing': billing,
        'customer': customer,
        'payment_info': payment_info,
    }
    return render(request, 'user_querySafe/payment_status.html', context)

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
