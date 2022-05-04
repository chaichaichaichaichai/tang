from django.contrib.auth.models import User
from django import forms
from django.contrib.auth.forms import UserCreationForm

class SignUpForm(UserCreationForm):
    first_name=forms.CharField(max_length=100,required=True)
    last_name=forms.CharField(max_length=100,required=True)
    email=forms.EmailField(max_length=250,help_text='borospoc@gmail.com')
    # address=forms.CharField(max_length=200,required=True)
    # city=forms.CharField(max_length=100,required=True)
    # country=forms.CharField(max_length=100,required=True)
    # postcode=forms.CharField(max_length=100,required=True)
    # phone_number=forms.IntegerField(required=True)

    class Meta:
        model=User
        fields=('first_name','last_name','email','username','password1','password2')
    

    