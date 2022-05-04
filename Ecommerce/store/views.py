from distutils.log import error
import email
import imp
from itertools import product
from unicodedata import name
import django
from django.shortcuts import  render, get_object_or_404,redirect
from matplotlib.style import context
from store.models import Category,Product,Cart,CartItem,Order,OrderItem
from store.forms import SignUpForm
from django.contrib.auth.models import Group,User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login,authenticate,logout
from django.core.paginator import Paginator,EmptyPage,InvalidPage
from django.contrib.auth.decorators import login_required
from django.conf import settings
import stripe



def index(request,category_slug=None):
    products=None
    category_page=None
    if category_slug!=None:
        category_page=get_object_or_404(Category,slug=category_slug)
        products=Product.objects.all().filter(category=category_page,available=True)
    else :
        products=Product.objects.all().filter(available=True)
    
    #12 / 3 = 4
    paginator=Paginator(products,3)
    try:
        page=int(request.GET.get('page','1'))
    except:
        page=1

    try:
        productperPage=paginator.page(page)
    except (EmptyPage,InvalidPage):
        productperPage=paginator.page(paginator.num_pages)
    
    return render(request,'index.html',{'products':productperPage,'category':category_page})

def productPage(request,category_slug,product_slug):
    try:
        product=Product.objects.get(category__slug=category_slug,slug=product_slug)
    except Exception as e :
        raise e
    return render(request,'product.html',{'product':product})

def _cart_id(request):
    cart=request.session.session_key
    if not cart:
        cart=request.session.create()
    return cart
@login_required(login_url='signIn')
def addCart(request,product_id):
    #ดึงสินค้าที่ซื้อมาใช้
    product=Product.objects.get(id=product_id)
    #สร้างตะกร้าสินค้า
    try:
        cart=Cart.objects.get(cart_id=_cart_id(request))
    except Cart.DoesNotExist:
        cart=Cart.objects.create(cart_id=_cart_id(request))
        cart.save()
    
    try:
        #ซ์ื้อสินค้าซ้ำ
        cart_item=CartItem.objects.get(product=product,cart=cart)
        if cart_item.quantity<cart_item.product.stock:
            #เปลี่ยนจำนวนสินค้า
            cart_item.quantity+=1
            #บันทึก&อัปเดต
            cart_item.save()
    except CartItem.DoesNotExist:
        #ซื้อครั้งแรก
        cart_item=CartItem.objects.create(
            product=product,
            cart=cart,
            quantity=1
        )
        cart_item.save()
    
    return redirect('cartdetail')

def cartdetail(request):
    total=0
    counter=0
    cart_items=None
    try:
        cart=Cart.objects.get(cart_id=_cart_id(request)) #ดึงตะกร้า
        cart_items=CartItem.objects.filter(cart=cart,active=True) #ดึงข้อมูลสินค้าในตะกร้า
        for item in cart_items:
            total+=(item.product.price*item.quantity)
            counter+=item.quantity
    except Exception as e :
        pass

    stripe.api_key=settings.SECRET_KEY
    stripe_total=int(total*100)
    description="Payment "
    data_key=settings.PUBLIC_KEY

    if request.method=="POST":
        try :
            token=request.POST['stripeToken']
            email=request.POST['stripeEmail']
            name=request.POST['stripeBillingName']
            address=request.POST['stripeBillingAddressLine1']
            city=request.POST['stripeBillingAddressCity']
            postcode=request.POST['stripeShippingAddressZip']
            customer=stripe.Customer.create(
                email=email,
                source=token
            )
            charge=stripe.Charge.create(
                amount=stripe_total,
                currency='thb',
                description=description,
                customer=customer.id
            )
            #บันทึกข้อมูลใบสั่งซื้อ
            order=Order.objects.create(
                name=name,
                address=address,
                city=city,
                postcode=postcode,
                total=total,
                email=email,
                token=token
            )
            order.save()

            #บันทึกรายการสั่งซื้อ
            for item in cart_items :
                order_item=OrderItem.objects.create(
                    product=item.product.name,
                    quantity=item.quantity,
                    price=item.product.price,
                    order=order
                )
                order_item.save()
                #ลดจำนวน Stock
                product=Product.objects.get(id=item.product.id)
                product.stock=int(item.product.stock-order_item.quantity)
                product.save()
                item.delete()
            return redirect('thankyou')

        except stripe.error.CardError as e :
            return False , e

    return render(request,'cartdetail.html',
    dict(cart_items=cart_items,total=total,counter=counter,
    data_key=data_key,
    stripe_total=stripe_total,
    description=description
    ))

def removeCart(request,product_id):
    cart=Cart.objects.get(cart_id=_cart_id(request))
    product=get_object_or_404(Product,id=product_id)
    cartItem=CartItem.objects.get(product=product,cart=cart)
    cartItem.delete()
    return redirect('cartdetail')

def signUpView(request):
    if request.method=='POST':
        form=SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username=form.cleaned_data.get('username')
            signUpUser=User.objects.get(username=username)
            customer_group=Group.objects.get(name='Customer')
            customer_group.user_set.add(signUpUser)
    else:
        form=SignUpForm()
    return render(request,"signup.html",{'form':form})
    


def signInView(request):
    if request.method=='POST':
        form=AuthenticationForm(data=request.POST)
        if form.is_valid():
            username=request.POST['username']
            password=request.POST['password']
            user=authenticate(username=username,password=password)
            if user is not None:
                login(request,user)
                return redirect('Home')
            else:
                return redirect('signUp')

            
    else:
        form=AuthenticationForm()
    return render(request,"signin.html",{'form':form})


def signOutView(request):
    logout(request)
    return redirect('signIn')


def search(request):
    products=Product.objects.filter(name__contains=request.GET['title'])
    return render(request,'index.html',{'products':products})


def orderHistory(request):
    if request.user.is_authenticated:
        email=str(request.user.email)
        orders=Order.objects.filter(email=email)
    return render(request,'orders.html',{'orders':orders})

def viewOrder(request,order_id):
    if request.user.is_authenticated:
        email=str(request.user.email)
        order=Order.objects.get(email=email,id=order_id)
        orderitem=OrderItem.objects.filter(order=order)
    return render(request,'viewOrder.html',{'order': order, 'order_items': orderitem})

def thankyou(request):
    return render(request,'thankyou.html')

def Checkout(request):
    total=0

    try:
        cart=Cart.objects.get(cart_id=_cart_id(request)) #ดึงตะกร้า
        cart_items=CartItem.objects.filter(cart=cart,active=True) #ดึงข้อมูลสินค้าในตะกร้า
        for item in cart_items:
            total+=(item.product.price*item.quantity)
    except Exception as e :
        pass
    context={"total_price":float(total), "mobile":"0973437869"}
    return render(request,'checkout.html',context)

def home(request):
    message='id:%s, username:%s firstname:%s, lastname:%s'%(request.user.pk,request.user.username,request.user.first_name,request.user.last_name)
    now = datetime.datetime.now()
    html = '<html><body><p>It is now %s,</p><p>%s</p></body></html>' %(now,message)
    return HttpResponse(html)

from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView
import json 

data =[]

def add_to_cart(request):
    global data
    pk = request.POST.get("pk", "")
    title = request.POST.get("title", "")
    myitem={
        "pk": pk,
        "tile": title,
        "quantity": 1
        }
    data += [myitem,]
    dictionary = {"data": data}
    json_object = json.dumps(dictionary, indent = 4)
    print(json_object)
    response = redirect('home')
    response.set_cookie('cart', json_object)
    return response

def home(request):
    return render(request, 'home.html')

def profile(request): 
    instance = get_object_or_404(Profile, user=request.user)
    form = ProfileForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect('home')
    else:
        context = {
            'form':form,
            'user':request.user,
            'mobile': "0826639106",
            'amount': 3.14159
            }
        return render(request, 'profile.html', context) 

from django.http import HttpResponse
from PIL import Image
import libscrc
import qrcode

def calculate_crc(code):
    crc = libscrc.ccitt_false(str.encode(code))
    crc = str(hex(crc))
    crc = crc[2:].upper()
    return crc.rjust(4, '0')

def gen_code(mobile="", nid="", amount=1.23):
    code="00020101021153037645802TH29370016A000000677010111"
    if mobile:
        tag,value = 1,"0066"+mobile[1:]
        seller='{:02d}{:02d}{}'.format(tag,len(value), value)
    elif nid:
        tag,value = 2,nid
        seller='{:02d}{:02d}{}'.format(tag,len(value), value)
    else:
        raise Exception("Error: gen_code() does not get seller mandatory details")
    code+=seller
    tag,value = 54, '{:.2f}'.format(amount)
    code+='{:02d}{:02d}{}'.format(tag,len(value), value)
    code+='6304'
    code+=calculate_crc(code)
    return code

def get_qr(request,mobile="",nid="",amount=""):
    message="mobile: %s, nid: %s, amount: %s"%(mobile,nid,amount)
    print( message )
    code=gen_code(mobile=mobile, amount=float(amount))#scb
    print(code)
    img = qrcode.make(code,box_size=4)
    response = HttpResponse(content_type='image/png')
    img.save(response, "PNG")
    return response

def checkout(request):
    context={
        "mobile":"0826639206", #seller's mobile
        "amount": 2.81619
    }
    return render(request, 'checkout.html', context)