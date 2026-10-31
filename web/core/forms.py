"""Formularios de registro e inicio de sesión de OptiFlow Dining."""
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import AdminNotification


class RegisterForm(UserCreationForm):
    """Formulario de registro para nuevos meseros con validación estricta y aviso al administrador."""
    first_name = forms.CharField(label='Nombre', max_length=50, required=True)
    last_name = forms.CharField(label='Apellido', max_length=50, required=True)
    email = forms.EmailField(label='Correo electrónico', required=True)

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'username',
            'email',
            'password1',
            'password2',
        )
        labels = {
            'username': 'Nombre de usuario',
        }

    def __init__(self, *args, **kwargs):
        """Inicializa los campos con placeholders y estilos consistentes."""
        super().__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Daniel', 'class': 'form-input', 'autocomplete': 'given-name', 'enterkeyhint': 'next'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Gallego', 'class': 'form-input', 'autocomplete': 'family-name', 'enterkeyhint': 'next'})
        self.fields['username'].widget.attrs.update({'placeholder': 'dgallego', 'class': 'form-input', 'autocomplete': 'username', 'spellcheck': 'false', 'autocapitalize': 'none', 'autocorrect': 'off', 'enterkeyhint': 'next'})
        self.fields['email'].widget.attrs.update({'placeholder': 'daniel.gallego@optiflow.local', 'class': 'form-input', 'autocomplete': 'email', 'inputmode': 'email', 'spellcheck': 'false', 'autocapitalize': 'none', 'autocorrect': 'off', 'enterkeyhint': 'next'})
        self.fields['password1'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input', 'autocomplete': 'new-password', 'enterkeyhint': 'next'})
        self.fields['password2'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input', 'autocomplete': 'new-password', 'enterkeyhint': 'done'})

    def clean_first_name(self):
        """Valida que el nombre contenga únicamente letras coherentes y al menos 2 caracteres."""
        name = self.cleaned_data['first_name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('El nombre debe tener al menos 2 caracteres.')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\'-]+$', name):
            raise forms.ValidationError('El nombre solo puede contener letras y espacios válidos.')
        return name.title()

    def clean_last_name(self):
        """Valida que el apellido contenga únicamente letras coherentes y al menos 2 caracteres."""
        last = self.cleaned_data['last_name'].strip()
        if len(last) < 2:
            raise forms.ValidationError('El apellido debe tener al menos 2 caracteres.')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\'-]+$', last):
            raise forms.ValidationError('El apellido solo puede contener letras y espacios válidos.')
        return last.title()

    def clean_username(self):
        """Valida que el nombre de usuario sea alfanumérico y de longitud adecuada."""
        username = self.cleaned_data['username'].strip().lower()
        if len(username) < 3:
            raise forms.ValidationError('El nombre de usuario debe tener al menos 3 caracteres.')
        if not re.match(r'^[a-z0-9_.-]+$', username):
            raise forms.ValidationError('El usuario solo permite letras, números, puntos, guiones y guiones bajos.')
        return username

    def clean_email(self):
        """Valida que el correo no se encuentre registrado previamente."""
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado en el sistema.')
        return email

    def save(self, commit=True):
        """Asigna el correo validado al usuario y genera notificación para la administración."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            # Aviso automático a la administración del restaurante
            AdminNotification.objects.create(
                title=f'Nuevo mesero registrado: {user.get_full_name()} (@{user.username})',
                message=(
                    f'Se ha dado de alta una nueva cuenta operativa de mesero para {user.get_full_name()} '
                    f'con correo {user.email}. La cuenta está activa para el turno.'
                ),
            )
        return user


class LoginForm(AuthenticationForm):
    """Formulario de autenticación con widgets visuales consistentes."""
    username = forms.CharField(label='Usuario')
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        """Inicializa los campos de acceso con placeholders y clases visuales."""
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Ingresa tu usuario', 'class': 'form-input', 'autocomplete': 'username', 'spellcheck': 'false', 'autocapitalize': 'none', 'autocorrect': 'off', 'enterkeyhint': 'next'})
        self.fields['password'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input', 'autocomplete': 'current-password', 'enterkeyhint': 'done'})

