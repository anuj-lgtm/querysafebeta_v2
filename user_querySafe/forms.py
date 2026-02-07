from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import Chatbot

class RegisterForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'name',
            'placeholder': 'Full Name'
        }),
        label='Name'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'id': 'email',
            'placeholder': 'Email'
        }),
        label='Email'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password',
            'placeholder': 'Password'
        }),
        label='Password'
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'confirm_password',
            'placeholder': 'Confirm Password'
        }),
        label='Confirm Password'
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError({
                    'confirm_password': 'Passwords do not match'
                })

        return cleaned_data
    
class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )

class ChatbotCreateForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'Metric Vibes AI Support...',
            'id': 'id_name'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'We are the best Data Analytics company...',
            'rows': '4',
            'id': 'id_description'
        })
    )
    logo = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        required=False,
        label="Upload Logo"
    )

    bot_instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'e.g. Be polite and professional. Answer only about our services. Keep answers concise.',
            'rows': '3',
            'id': 'id_bot_instructions'
        }),
        required=False,
        label="Bot Instructions"
    )
    sample_questions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'What services do you offer?\nHow can I contact support?\nWhat are your pricing plans?',
            'rows': '3',
            'id': 'id_sample_questions'
        }),
        required=False,
        label="Starter Questions"
    )

    collect_email = forms.BooleanField(
        required=False,
        label="Collect Visitor Email",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_collect_email'
        })
    )
    collect_email_message = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'Please enter your email to get started.',
            'id': 'id_collect_email_message'
        }),
        required=False,
        label="Email Prompt Message"
    )

    class Meta:
        model = Chatbot
        fields = ['name', 'description', 'logo', 'bot_instructions', 'sample_questions', 'collect_email', 'collect_email_message']

class ChatbotEditForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'Chatbot Name...',
            'id': 'id_name'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'Describe your chatbot...',
            'rows': '4',
            'id': 'id_description'
        }),
        required=False
    )
    logo = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        required=False,
        label="Upload Logo"
    )
    bot_instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'e.g. Be polite and professional. Answer only about our services.',
            'rows': '3',
            'id': 'id_bot_instructions'
        }),
        required=False,
        label="Bot Instructions"
    )
    sample_questions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'What services do you offer?\nHow can I contact support?',
            'rows': '3',
            'id': 'id_sample_questions'
        }),
        required=False,
        label="Starter Questions"
    )

    collect_email = forms.BooleanField(
        required=False,
        label="Collect Visitor Email",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_collect_email'
        })
    )
    collect_email_message = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control border px-3',
            'placeholder': 'Please enter your email to get started.',
            'id': 'id_collect_email_message'
        }),
        required=False,
        label="Email Prompt Message"
    )

    class Meta:
        model = Chatbot
        fields = ['name', 'description', 'logo', 'bot_instructions', 'sample_questions', 'collect_email', 'collect_email_message']

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6, widget=forms.TextInput(attrs={
        'class': 'form-control text-center',
        'placeholder': 'Enter OTP'
    }))
