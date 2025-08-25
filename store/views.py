from itertools import product

from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect

from carts.models import Cart, CartItem
from carts.views import _cart_id
from category.models import Category
from orders.models import OrderProduct
from .forms import ReviewForm
from .models import Product, ReviewRating, ProductGallery
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.contrib import messages, auth


# Create your views here.
def store(request, category_slug=None):
    categories = None
    products = None
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True)
    else:
        products = Product.objects.filter(is_available=True).order_by('id')

    paginator = Paginator(products, 3)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    product_count = products.count()


    context = {
        'products': paged_products,
        'product_count': product_count,
    }

    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):

    try:
        product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=product).exists()

    except Exception as e:
        raise e

    if request.user.is_authenticated:
        try:
            orderproducts = OrderProduct.objects.filter(user=request.user, product_id=product.id).exists()
        except orderproducts.DoesNotExist:
            orderproducts = None
    else:
        orderproducts = None

    reviews = ReviewRating.objects.filter(product_id=product.id, status=True)

    # Get the product gallery
    product_gallery = ProductGallery.objects.filter(product_id=product.id, is_active=True)
    context = {'product': product, 'in_cart': in_cart, 'orderproducts': orderproducts, 'reviews': reviews, 'product_gallery': product_gallery,}
    return render(request, 'store/product_detail.html', context)

def search(request):
    context = {}
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.order_by('-created_at').filter(Q(description__icontains=keyword) | Q(product_name__icontains=keyword))
            products_count = products.count()
            context = {'products': products, 'product_count': products_count}
    return render(request, 'store/store.html', context)



def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Review updated successfully')

        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank you for your review')
        return redirect(url)


