from django.urls import path
from . import views

urlpatterns = [
    path('my_chatbots', views.my_chatbots, name='my_chatbots'),
    path('create/', views.create_chatbot, name='create_chatbot'),
    path('edit/<str:chatbot_id>/', views.edit_chatbot, name='edit_chatbot'),
    path('delete_document/<int:document_id>/', views.delete_document, name='delete_document'),
    path('retrain/<str:chatbot_id>/', views.retrain_chatbot, name='retrain_chatbot'),
    path('preview_sitemap/', views.preview_sitemap, name='preview_sitemap'),
    path('delete_url/<int:url_id>/', views.delete_url, name='delete_url'),
    path('chatbot_status/', views.chatbot_status, name='chatbot_status'),
    path('chatbot/<int:pk>/', views.chatbot_detail_view, name='chatbot_detail'),
    path('change_status/', views.change_chatbot_status, name='change_chatbot_status'),
]