import json

from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string

from accounts.models import Account
from carts.models import CartItem
from store.models import Product
from .forms import OrderForm
import datetime
from .models import Order, Payment, OrderProduct
from django.db import transaction


def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])
    payment = Payment(
        user=request.user,
        payment_id=body['transactionID'],
        payment_method=body['payment_method'],
        amount_paid = order.order_total,
        status=body['status'],
    )
    payment.save()

    order.payment = payment
    order.is_ordered = True
    order.save()



    cart_items = CartItem.objects.filter(user=request.user).select_related("product").prefetch_related("variation")

    orderproducts_to_create = []
    variation_mappings = []  # will hold (orderproduct, variation) relations

    # Step 1: prepare OrderProduct objects
    product_ids_quantity = {}
    product_ids = []
    for item in cart_items:
        product_ids_quantity[item.product_id] = item.quantity
        product_ids.append(item.product_id)
        orderproducts_to_create.append(
            OrderProduct(
                order_id=order.id,
                payment=payment,
                user_id=request.user.id,
                product_id=item.product_id,
                quantity=item.quantity,
                product_price=item.product.price,
                ordered=True,
            )
        )

    with transaction.atomic():
        # Step 2: Bulk insert OrderProducts
        created_orderproducts = OrderProduct.objects.bulk_create(orderproducts_to_create)

        # Step 3: Build through-model rows for M2M relation (orderproduct_variation)
        through_model = OrderProduct.variation.through  # the join table

        for orderproduct, item in zip(created_orderproducts, cart_items):
            for variation in item.variation.all():
                variation_mappings.append(
                    through_model(
                        orderproduct_id=orderproduct.id,
                        variation_id=variation.id,
                    )
                )

        # Step 4: Bulk insert relations
        through_model.objects.bulk_create(
            variation_mappings,
            update_conflicts=True,  # update if conflict
            update_fields=["variation_id"],  # fields to update on conflict
            unique_fields=["orderproduct_id", "variation_id"],  # conflict key
        )

    # Reduce the quantity of the sold products
    products = Product.objects.filter(id__in=product_ids)
    for product in products:
        print(product_ids_quantity[product.id])
        product.stock = product.stock - int(product_ids_quantity[product.id])
    Product.objects.bulk_update(products, ["stock"])

    #clear cart
    CartItem.objects.filter(user=request.user).delete()

    #Send order received email to customer
    mail_subject = 'Thank you for your order .'
    message_html = render_to_string('orders/order_recieved_email.html', {
        'user': request.user,
        'order': order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message_html, to=[to_email])
    send_email.send()

    #send order number and transaction id back to sendData method via JsonResponse
    data = {
        'order_number': order.order_number,
        'transactionID': payment.payment_id,
    }

    return JsonResponse(data)

@login_required(login_url='/login/')
def place_order(request, total=0, quantity=0):
    current_user = request.user

    #if the cart count is less than pr equal to 0 the redirect back to shop
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += 1
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.email = form.cleaned_data['email']
            data.phone = form.cleaned_data['phone']
            data.address_line1 = form.cleaned_data['address_line1']
            data.address_line2 = form.cleaned_data['address_line2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']

            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            #Generate order number
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr,mt,dt)
            current_date = d.strftime('%Y%m%d')
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()
            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            context = {
                'order': order,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total,
            }
            return render(request, 'orders/payments.html', context)
        else:
            return redirect('checkout')
    else:
        return redirect('checkout')

def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')
    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        payment = Payment.objects.get(user=request.user, payment_id=transID)
        context = {
            'order': order,
            'ordered_products': ordered_products,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except(Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')


