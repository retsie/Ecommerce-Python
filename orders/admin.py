from django.contrib import admin
from orders.models import Order, Payment, OrderProduct

admin.site.register(Order)
admin.site.register(Payment)
admin.site.register(OrderProduct)
