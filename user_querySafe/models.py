from django.db import models, IntegrityError
import random
import string
import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.text import get_valid_filename
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password as django_check_password
User = get_user_model()

# Create a custom storage that points to BASE_DIR/documents/files_uploaded
custom_storage = FileSystemStorage(location=os.path.join(settings.DATA_DIR, 'documents', 'files_uploaded'))

class User(models.Model):
    STATUS_CHOICES = (
        ('registered', 'Registered'),
        ('activated', 'Activated')
    )

    user_id = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    # store hashed passwords (use `set_password` / `check_password` helpers)
    password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    registration_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='registered'
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    tour_completed = models.BooleanField(default=False)
    # profile_image = models.ImageField(
    #     upload_to='user-profile/',
    #     blank=True,
    #     null=True,
    #     default='user-profile/default.png'
    # )

    def save(self, *args, **kwargs):
        if not self.user_id:
            # Retry on collision (unique constraint) instead of check-then-set
            for _ in range(10):
                random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                self.user_id = f"PC{random_string}"
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError('Could not generate a unique user_id after 10 attempts')
        super().save(*args, **kwargs)

    # Password helpers so we don't store plain text
    def set_password(self, raw_password):
        if raw_password is None:
            self.password = None
        else:
            self.password = make_password(raw_password)

    def check_password(self, raw_password):
        # If password field is empty, always fail
        if not self.password:
            return False

        return django_check_password(raw_password, self.password)

    def __str__(self):
        return self.name

class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_valid(self):
        # OTP valid for 10 minutes
        from django.utils import timezone
        return (timezone.now() - self.created_at).total_seconds() < 600

class Chatbot(models.Model):
    chatbot_id = models.CharField(max_length=6, unique=True, editable=False)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chatbots')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='training')
    logo = models.ImageField(
        upload_to='chatbot_logos/',
        null=True,
        blank=True,
        default='chatbot_logos/default.png'
    )
    dataset_name = models.CharField(max_length=255, blank=True, null=True)
    bot_instructions = models.TextField(blank=True, default='', help_text='Custom instructions for the chatbot (tone, personality, restrictions)')
    sample_questions = models.TextField(blank=True, default='', help_text='Newline-separated starter questions shown in chat widget')
    collect_email = models.BooleanField(default=False, help_text='Require visitor email before chatting')
    collect_email_message = models.TextField(blank=True, default='Please enter your email to get started.', help_text='Message shown when asking for email')
    last_trained_at = models.DateTimeField(null=True, blank=True, help_text='Last successful training timestamp')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.chatbot_id:
            for _ in range(10):
                self.chatbot_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError('Could not generate a unique chatbot_id after 10 attempts')
        super().save(*args, **kwargs)

    def logo_file_name(self):
        if self.logo:
            return f"{self.chatbot_id}_{self.logo.name}"
        return None

    @property
    def snippet_code(self):
        # Get the base URL from settings or environment variable
        from django.conf import settings
        base_url = getattr(settings, 'WEBSITE_URL')
        
        return f'''<script>
        (function(w,d,s,id){{
            var js, fjs = d.getElementsByTagName(s)[0];
            if (d.getElementById(id)){{return;}}
            js = d.createElement(s);
            js.id = id;
            js.src = "{base_url}/widget/{self.chatbot_id}/querySafe.js";
            js.async = true;
            fjs.parentNode.insertBefore(js, fjs);
        }}(window, document, 'script', 'querySafe-widget'));
        </script>'''

    @property
    def conversation_count(self):
        return self.conversations.count()

    def __str__(self):
        return self.name

class ChatbotDocument(models.Model):
    chatbot = models.ForeignKey('Chatbot', on_delete=models.CASCADE)
    # Use custom_storage so that files are saved in BASE_DIR/documents/files_uploaded
    document = models.FileField(upload_to='', storage=custom_storage)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.document.name) if hasattr(self.document, 'name') else "No document"

    def save(self, *args, **kwargs):
        # If new and file is uploaded, rename the file before saving
        if not self.pk and self.document:
            pdf_file = self.document
            chatbot_id = self.chatbot.chatbot_id
            original_filename = get_valid_filename(pdf_file.name)
            file_extension = os.path.splitext(original_filename)[1]

            # Truncate the original filename if it's too long
            max_filename_length = 200
            if len(original_filename) > max_filename_length:
                original_filename = original_filename[:max_filename_length - len(file_extension)]

            filename = f"{chatbot_id}_{original_filename}{file_extension}"
            # Save file using custom storage (this writes to BASE_DIR/documents/files_uploaded)
            saved_name = self.document.storage.save(filename, pdf_file)
            self.document.name = saved_name
            print(f"✅ File uploaded: {filename}")

        super().save(*args, **kwargs)

class Conversation(models.Model):
    conversation_id = models.CharField(max_length=10, unique=True, editable=False)
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='conversations')
    user_id = models.CharField(max_length=100)  # Session or user identifier
    visitor_email = models.EmailField(blank=True, null=True, help_text='Email collected from visitor via lead capture')
    started_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.conversation_id:
            for _ in range(10):
                self.conversation_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError('Could not generate a unique conversation_id after 10 attempts')
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-last_updated']

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    is_bot = models.BooleanField(default=False)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']


class Activity(models.Model):
    ACTIVITY_TYPES = (
        ('primary', 'Primary'),
        ('success', 'Success'), 
        ('info', 'Info'),
        ('warning', 'Warning')
    )

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='activities')
    type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='primary')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='info')  # Material icon name
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Activities'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.name} - {self.title}"

    @classmethod
    def log(cls, user, title, description='', activity_type='primary', icon='info'):
        return cls.objects.create(
            user=user,
            title=title,
            description=description,
            type=activity_type,
            icon=icon
        )

class HelpSupportRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('suspended', 'Suspended'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="help_requests")
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name} - {self.subject}"

class ChatbotFeedback(models.Model):
    feedback_id = models.CharField(max_length=12, primary_key=True, unique=True, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='feedbacks')
    no_of_star = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.feedback_id:
            for _ in range(10):
                self.feedback_id = 'FB' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError('Could not generate a unique feedback_id after 10 attempts')
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'chatbot_feedbacks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.feedback_id} - {self.conversation.conversation_id}"


class VisionAPIUsage(models.Model):
    """Tracks Gemini Vision API calls per chatbot for cost monitoring."""
    chatbot = models.ForeignKey('Chatbot', on_delete=models.CASCADE, related_name='vision_usage')
    call_count = models.PositiveIntegerField(default=1)
    call_type = models.CharField(max_length=20, choices=[
        ('training', 'Training Pipeline'),
        ('chat', 'Chat Response'),
    ], default='training')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vision_api_usage'

    def __str__(self):
        return f"{self.chatbot.chatbot_id} - {self.call_type} ({self.call_count})"


class QSPlan(models.Model):
    plan_id = models.CharField(max_length=5, primary_key=True, unique=True)
    plan_name = models.CharField(max_length=255)
    is_trial = models.BooleanField(default=False)
    parent_plan = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_plans', help_text='Optional: select a parent plan when this is a trial derived from another plan')
    require_act_code = models.BooleanField(default=False)
    no_of_bot = models.PositiveIntegerField(default=0)
    no_of_query = models.PositiveIntegerField(default=0)
    no_of_file = models.PositiveIntegerField(default=0)
    max_file_size = models.PositiveIntegerField(help_text='Max file size in MB', default=0)
    currency = models.CharField(max_length=10, default='INR')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text='Price in INR')
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text='Price in USD')
    STATUS_CHOICES = (
        ('public', 'Public'),
        ('limited', 'Limited'),
        ('private', 'Private'),
        ('personal', 'Personal'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='public')
    days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'qs_plans'

    def __str__(self):
        return f"{self.plan_id} - {self.plan_name}"


class QSCheckout(models.Model):
    checkout_id = models.CharField(max_length=10, primary_key=True, unique=True)
    user = models.ForeignKey(User, to_field='user_id', on_delete=models.CASCADE, related_name='qs_checkouts')
    plan = models.ForeignKey(QSPlan, to_field='plan_id', on_delete=models.CASCADE, related_name='qs_checkouts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'qs_checkout'

    def __str__(self):
        return f"{self.checkout_id} - {self.user.user_id} - {self.plan.plan_id}"


class QSBillingDetails(models.Model):
    billing_id = models.CharField(max_length=10, primary_key=True, unique=True)
    checkout = models.ForeignKey(QSCheckout, on_delete=models.CASCADE, related_name='billing_details')
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'qs_billing_details'

    def __str__(self):
        return f"{self.billing_id} - {self.full_name}"


class QSOrder(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    order_id = models.CharField(max_length=100, primary_key=True, unique=True)
    checkout = models.ForeignKey(QSCheckout, on_delete=models.CASCADE, related_name='orders')
    user = models.ForeignKey(User, to_field='user_id', on_delete=models.CASCADE, related_name='qs_orders')
    plan = models.ForeignKey(QSPlan, to_field='plan_id', on_delete=models.CASCADE, related_name='qs_orders')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_error_code = models.CharField(max_length=100, blank=True, null=True, help_text='Error code from Razorpay if payment failed')
    razorpay_error_description = models.TextField(blank=True, null=True, help_text='Error description from Razorpay if payment failed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'qs_orders'

    def __str__(self):
        return f"{self.order_id} - {self.user.user_id} - {self.status}"


class QSPlanAllot(models.Model):
    plan_allot_id = models.CharField(max_length=8, primary_key=True, unique=True)
    user = models.ForeignKey(User, to_field='user_id', on_delete=models.CASCADE, related_name='qs_plan_allots')
    parent_plan = models.ForeignKey(QSPlan, to_field='plan_id', on_delete=models.CASCADE, related_name='allots')
    order = models.ForeignKey(QSOrder, to_field='order_id', on_delete=models.CASCADE, null=True, blank=True, related_name='plan_allots', help_text='Order that activated this plan (Razorpay order_id)')
    plan_name = models.CharField(max_length=255)
    no_of_bot = models.PositiveIntegerField(default=0)
    no_of_query = models.PositiveIntegerField(default=0)
    no_of_files = models.PositiveIntegerField(default=0)
    file_size = models.PositiveIntegerField(default=0, help_text='File size limit in MB')
    start_date = models.DateField()
    expire_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'qs_plan_allot'

    def __str__(self):
        return f"{self.plan_allot_id} - {self.user.user_id} - {self.plan_name}"


class ChatbotURL(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('crawled', 'Crawled'),
        ('error', 'Error'),
    )
    chatbot = models.ForeignKey('Chatbot', on_delete=models.CASCADE, related_name='urls')
    url = models.URLField(max_length=2048)
    is_sitemap = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    page_count = models.PositiveIntegerField(default=0, help_text='Number of pages discovered (for sitemaps)')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('chatbot', 'url')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.chatbot.chatbot_id} - {self.url[:80]}"


class BugReport(models.Model):
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    STATUS_CHOICES = (
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('fixed', 'Fixed'),
    )

    report_id = models.CharField(max_length=10, primary_key=True, unique=True)
    email = models.EmailField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    steps_to_reproduce = models.TextField(blank=True, default='')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    coupon_code = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bug_reports'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.report_id:
            for _ in range(10):
                self.report_id = 'BR' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError('Could not generate a unique report_id after 10 attempts')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.report_id} - {self.title[:50]}"


class ScheduledEmail(models.Model):
    """Tracks drip/scheduled emails for user engagement sequences."""
    EMAIL_TYPES = (
        ('day1_getting_started', 'Day 1 - Getting Started'),
        ('day3_first_chatbot', 'Day 3 - Create First Chatbot'),
        ('day7_tips', 'Day 7 - Tips & Best Practices'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    )

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='scheduled_emails')
    email_type = models.CharField(max_length=30, choices=EMAIL_TYPES)
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scheduled_emails'
        ordering = ['scheduled_at']
        unique_together = ('user', 'email_type')  # One of each type per user

    def __str__(self):
        return f"{self.user.email} - {self.email_type} ({self.status})"