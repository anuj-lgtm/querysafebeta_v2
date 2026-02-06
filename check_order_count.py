import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'querySafe.settings')
import django
django.setup()
from user_querySafe.models import OrderHistory
print('OrderHistory count =', OrderHistory.objects.count())
for o in OrderHistory.objects.all()[:5]:
    print(o.razorpay_order_id, o.amount, o.status)
