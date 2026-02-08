from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # dashboard_paths
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='dashboard'),

    # authentication related path
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),

    # Google OAuth 2.0
    path('auth/google/', views.google_login_redirect, name='google_login'),
    path('auth/google/callback/', views.google_callback, name='google_callback'),

    # conversations related paths
    path('conversations/', views.conversations_view, name='conversations'),
    path('conversations/<str:chatbot_id>/', views.conversations_view, name='conversations_by_chatbot'),
    path('conversations/<str:chatbot_id>/<str:conversation_id>/', views.conversations_view, name='conversation_detail'),

    # Chatbot related paths
    path('chatbot/', include('user_querySafe.chatbot.urls')),
    path('chatbot_view/<str:chatbot_id>/', views.chatbot_view, name='chatbot_view'),
    path('chat/', views.chat_message, name='chat_message'),
    path('chat/feedback/', views.chat_feedback, name='chat_feedback'),
    path('widget/<str:chatbot_id>/querySafe.js', views.serve_widget_js, name='widget_js'),

    # profile related paths
    path('profile/', views.profile_view, name='profile'),

    # subscriptions related path
    path('plan/', include('user_querySafe.subscription.urls'), name='plan'),

    # Help and support related paths
    path('help-support/', views.help_support, name='help_support'),

    # Analytics
    path('analytics/', views.analytics_view, name='analytics'),
    path('analytics/<str:chatbot_id>/', views.analytics_view, name='analytics_by_chatbot'),
    path('api/analytics/chart-data/', views.analytics_chart_data, name='analytics_chart_data'),
    path('api/analytics/export/', views.analytics_export_csv, name='analytics_export_csv'),

    # Public website API
    path('api/contact/', views.contact_form_api, name='contact_form_api'),
    path('api/bug-report/', views.bug_report_api, name='bug_report_api'),

    # Cron / Scheduled tasks (protected by CRON_SECRET header)
    path('cron/send-drip-emails/', views.cron_send_drip_emails, name='cron_send_drip_emails'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)