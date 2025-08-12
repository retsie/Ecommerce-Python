from django.contrib import admin
from carts.models import Cart, CartItem
from store.models import Product

# Register your models here.
admin.site.register(Cart)
admin.site.register(CartItem)


