from django import forms

class EmailForm(forms.Form):
    email = forms.EmailField(label='Email', required=True)
    num1 = forms.IntegerField(label='Number 1', required=True)
    num2 = forms.IntegerField(label='Number 2', required=True)