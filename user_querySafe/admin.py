from django.contrib import admin
from django.utils.html import format_html
from .models import User, Chatbot, ChatbotDocument, ChatbotURL, Conversation, Message, HelpSupportRequest, ChatbotFeedback, EmailOTP, Activity, QSPlan, QSCheckout, QSBillingDetails, QSOrder, QSPlanAllot

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'name', 'email', 'registration_status', 'is_active', 'created_at')
    list_filter = ('is_active', 'registration_status', 'created_at')
    search_fields = ('name', 'email', 'user_id')
    readonly_fields = ('user_id', 'created_at', 'activated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('user_id', 'name', 'email', 'password')
        }),
        ('Status Information', {
            'fields': ('is_active', 'registration_status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'activated_at')
        }),
    )

@admin.register(Chatbot)
class ChatbotAdmin(admin.ModelAdmin):
    list_display = ('chatbot_id', 'user', 'name', 'status_badge', 'dataset_name', 'last_trained_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('chatbot_id', 'name', 'description', 'dataset_name')
    readonly_fields = ('chatbot_id', 'created_at', 'last_trained_at')

    def status_badge(self, obj):
        colors = {
            'training': 'warning',
            'active': 'success',
            'inactive': 'danger',
            'failed': 'danger'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.status.title()
        )
    status_badge.short_description = 'Status'

@admin.register(ChatbotDocument)
class ChatbotDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'chatbot', 'document_name', 'uploaded_at')
    list_filter = ('uploaded_at', 'chatbot')
    search_fields = ('chatbot__name', 'document')
    readonly_fields = ('uploaded_at',)

    def document_name(self, obj):
        try:
            if hasattr(obj.document, 'name'):
                return obj.document.name.split('/')[-1]
            elif isinstance(obj.document, str):
                return obj.document.split('/')[-1]
            return str(obj.document)
        except Exception:
            return 'No document'
    document_name.short_description = 'Document'

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'chatbot', 'user_id', 'message_count', 'started_at', 'last_updated')
    list_filter = ('started_at', 'last_updated')
    search_fields = ('chatbot__name', 'user_id')
    readonly_fields = ('started_at', 'last_updated')

    def message_count(self, obj):
        try:
            # Using the related_name 'messages' from the Message model
            return obj.messages.count()
        except Exception:
            return 0
    message_count.short_description = 'Messages'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'short_content', 'is_bot', 'timestamp')
    list_filter = ('is_bot', 'timestamp', 'conversation__chatbot')
    search_fields = ('content', 'conversation__chatbot__name')
    readonly_fields = ('timestamp',)

    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'


@admin.register(HelpSupportRequest)
class HelpSupportRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'message_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__name', 'user__email', 'subject', 'message')

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


@admin.register(ChatbotFeedback)
class ChatbotFeedbackAdmin(admin.ModelAdmin):
    list_display = ('feedback_id', 'conversation', 'no_of_star', 'description_preview', 'created_at')
    list_filter = ('created_at', 'no_of_star')
    search_fields = ('feedback_id', 'conversation__conversation_id', 'description')
    readonly_fields = ('created_at',)

    def description_preview(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else (obj.description or '')
    description_preview.short_description = 'Description'


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('email', 'otp')
    readonly_fields = ('created_at',)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'title', 'icon', 'timestamp')
    list_filter = ('type', 'timestamp')
    search_fields = ('user__name', 'title', 'description')
    readonly_fields = ('timestamp',)

@admin.register(QSPlan)
class QSPlanAdmin(admin.ModelAdmin):
    list_display = ('plan_id', 'plan_name', 'amount', 'amount_usd', 'currency', 'is_trial', 'parent_plan', 'require_act_code', 'status', 'days', 'created_at')
    search_fields = ('plan_id', 'plan_name')
    list_filter = ('is_trial', 'require_act_code', 'status')


@admin.register(QSCheckout)
class QSCheckoutAdmin(admin.ModelAdmin):
    list_display = ('checkout_id', 'user', 'plan', 'created_at')
    search_fields = ('checkout_id', 'user__user_id')
    list_filter = ('created_at',)


@admin.register(QSBillingDetails)
class QSBillingDetailsAdmin(admin.ModelAdmin):
    list_display = ('billing_id', 'checkout', 'full_name', 'email', 'phone', 'created_at')
    search_fields = ('billing_id', 'full_name', 'email')
    list_filter = ('created_at',)


@admin.register(QSOrder)
class QSOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'checkout', 'user', 'plan', 'amount', 'status', 'created_at')
    search_fields = ('order_id', 'user__user_id', 'checkout__checkout_id')
    list_filter = ('status', 'created_at')


@admin.register(QSPlanAllot)
class QSPlanAllotAdmin(admin.ModelAdmin):
    list_display = ('plan_allot_id', 'user', 'parent_plan', 'plan_name', 'order', 'start_date', 'expire_date', 'created_at')
    search_fields = ('plan_allot_id', 'user__user_id', 'plan_name', 'order__order_id')
    list_filter = ('start_date', 'expire_date', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ChatbotURL)
class ChatbotURLAdmin(admin.ModelAdmin):
    list_display = ('id', 'chatbot', 'url_truncated', 'is_sitemap', 'status', 'page_count', 'created_at')
    list_filter = ('is_sitemap', 'status', 'created_at')
    search_fields = ('chatbot__chatbot_id', 'chatbot__name', 'url')
    readonly_fields = ('created_at',)

    def url_truncated(self, obj):
        return obj.url[:80] + ('...' if len(obj.url) > 80 else '')
    url_truncated.short_description = 'URL'