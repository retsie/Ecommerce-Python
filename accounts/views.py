from itertools import product

from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from accounts.forms import RegisterForm, UserForm, UserProfileForm
from carts.models import Cart, CartItem
from orders.models import Order, OrderProduct
from .models import Account, UserProfile
from carts.views import _cart_id

#verification email
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
import requests

# from django.core.mail import send_mail, EmailMessage
# from django.utils.encoding import force_bytes
# from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
# from django.contrib.auth.tokens import default_token_generator



def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            username = email.split('@')[0]
            user = Account.objects.create_user(first_name=first_name,last_name=last_name,email=email, username=username, password=password)
            user.phone_number = phone_number
            user.save()

            #user activation
            current_site = get_current_site(request)
            mail_subject = 'Activate your account.'
            message_html = render_to_string('accounts/account_verfication_email.html', {
                'user': user,
                'domain': current_site,
                'uid' : urlsafe_base64_encode(force_bytes(user.pk)),
                'token' : default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message_html, to=[to_email])
            send_email.send()

            # messages.success(request, 'Thank you for registering. We have sent you a confirmation link.')
            return redirect('/accounts/login/?command=verification&email=' + email)
    else:
        form = RegisterForm()

    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)

def login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = auth.authenticate(email=email, password=password)
        if user is not None:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                is_cart_item_exist = CartItem.objects.filter(cart=cart ).exists()
                if is_cart_item_exist:
                    cart_items = CartItem.objects.filter(cart=cart)

                    #Getting the product variation by cart id
                    product_variation = []
                    id_cart = []
                    for item in cart_items:
                        product_variation.append(list(item.variation.all()))
                        id_cart.append(item.id)

                    #Get the cart items from the
                    cart_items = CartItem.objects.filter(user=user)
                    existing_variation = []
                    id = []
                    for item in cart_items:
                        existing_variation.append(list(item.variation.all()))
                        id.append(item.id)

                    item_to_update = []
                    ids = []
                    for pr in product_variation:
                        # print(pr)
                        if pr in existing_variation:
                            index_cart = product_variation.index(pr)
                            item_cart_id = id_cart[index_cart]
                            ids.append(item_cart_id)

                            index = existing_variation.index(pr)
                            item_id = id[index]
                            ids.append(item_id)
                            item_to_update.append({'to_update': item_id, 'to_delete': item_cart_id})

                    cart_items = CartItem.objects.filter(id__in=ids)
                    cart_items_map = {p.id: p for p in cart_items}

                    updated_cart_items = {}
                    for item in item_to_update:
                        cart_item_to_update = cart_items_map.get(item['to_update'])
                        cart_item_to_delete = cart_items_map.get(item['to_delete'])

                        cart_item_to_update.user = user
                        cart_item_to_update.quantity = cart_item_to_update.quantity + cart_item_to_delete.quantity

                        cart_item_to_delete.is_active = False

                        updated_cart_items[item['to_update']] = cart_item_to_update
                        updated_cart_items[item['to_delete']] = cart_item_to_delete

                    CartItem.objects.bulk_update(updated_cart_items.values(), ["user", "quantity", "is_active"])

                    cart_items = CartItem.objects.filter(cart=cart, is_active=True)
                    cart_items_map_cart = {p.id: p for p in cart_items}
                    for item in cart_items:
                        cart_item = cart_items_map_cart.get(item.id)
                        if cart_item:
                            cart_item.user = user
                    CartItem.objects.bulk_update(cart_items_map_cart.values(), ["user"])


            except:
                pass

            auth.login(request, user)
            messages.success(request, 'You are logged in')
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    next_page = params['next']
                    return redirect(next_page)
            except:
                return redirect('dashboard')

        else:
            messages.error(request, 'Email or password is incorrect')
            return redirect('login')
    return render(request, 'accounts/login.html')


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'You have been logged out')
    return redirect('login')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Account has been activated')
        return redirect('login')
    else:
        messages.error(request, 'Activation link is invalid')
        return redirect('register')


@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.order_by('-created_at').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()

    userprofile = UserProfile.objects.get(user_id=request.user.id)
    context = {
        'orders_count': orders_count,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/dashboard.html', context)


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)

            # user Reset Password
            current_site = get_current_site(request)
            mail_subject = 'Reset your password.'
            message_html = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message_html, to=[to_email])
            send_email.send()
            messages.success(request, 'Password reset email sent')
            return redirect('login')

        else:
            messages.error(request, 'Account does not exist')
            return redirect('forgot_password')

    return render(request, 'accounts/forgot_password.html')


def resetpassword_validate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your password')
        return redirect('reset_password')
    else:
        messages.error(request, 'This password reset link is invalid')

def reset_password(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirmation = request.POST['confirm_password']
        if password == confirmation:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'Your password has been reset')
            return redirect('login')

        else:
            messages.error(request, 'Passwords do not match')
            return redirect('reset_password')
    else:
        return render(request, 'accounts/reset_password.html')

@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.order_by('-created_at').filter(user=request.user, is_ordered=True)
    context = {
        'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)

@login_required(login_url='login')
def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your account has been updated!')
            return redirect('edit_profile')

    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        confirm_password = request.POST['confirm_password']
        new_password = request.POST['new_password']

        user = Account.objects.get(username__exact=request.user.username)


        if new_password == confirm_password:
            success = user.check_password(current_password)
            if success:
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Your password has been updated!')
                return redirect('change_password')
            else:
                messages.error(request, 'Your password is incorrect')
                return redirect('change_password')
        else:
            messages.error(request, 'Passwords do not match')
            return redirect('change_password')


    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def order_details(request, order_id):
    order_details = OrderProduct.objects.filter(order__order_number=order_id)
    order = Order.objects.get(order_number=order_id)
    subtotal = 0
    for i in order_details:
        subtotal += i.product_price * i.quantity

    context = {
        'order': order,
        'order_details': order_details,
        'subtotal': subtotal,
    }
    return render(request, 'accounts/order_details.html', context)





