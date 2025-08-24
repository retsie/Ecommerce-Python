from django.contrib import admin
from orders.models import Order, Payment, OrderProduct

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    extra = 0
    verbose_name_plural = 'Order Products'
    verbose_name = 'Order Product'
    ordering = ['order']
    readonly_fields = ('payment', 'user', 'product', 'quantity', 'product_price', 'ordered')


class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'full_name', 'phone', 'email', 'city', 'order_total', 'tax', 'status', 'ip', 'is_ordered', 'created_at']
    list_filter = ['status', 'is_ordered']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email']
    list_per_page = 20
    inlines = [OrderProductInline]

admin.site.register(Order, OrderAdmin)
admin.site.register(Payment)
admin.site.register(OrderProduct)
