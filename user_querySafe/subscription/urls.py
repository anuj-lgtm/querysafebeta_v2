from django.urls import path
from . import views

urlpatterns = [
    # subscriptions related path
    path('subscriptions/', views.subscription_view, name='subscriptions'),
    path('usage/', views.usage_view, name='usage'),

    path('checkout/', views.checkout, name='qs_payment_checkout'),
    path('order-payment', views.order_payment, name='order_payment'),
    path('order-status', views.payment_status, name='payment_status'),

    path('orders-history/', views.order_history, name='order_history'),

    # Add-ons
    path('addons/', views.addons_view, name='addons'),
    path('addon-checkout/', views.addon_checkout, name='addon_checkout'),
]