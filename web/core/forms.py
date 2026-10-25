"""Formularios de registro e inicio de sesión de OptiFlow Dining."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    """Formulario de registro para nuevos meseros con validación de correo único."""
    first_name = forms.CharField(label='Nombre', max_length=50)
    last_name = forms.CharField(label='Apellido', max_length=50)
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
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Daniel', 'class': 'form-input'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Gallego', 'class': 'form-input'})
        self.fields['username'].widget.attrs.update({'placeholder': 'dgallego', 'class': 'form-input'})
        self.fields['email'].widget.attrs.update({'placeholder': 'hello@reallygreatsite.com', 'class': 'form-input'})
        self.fields['password1'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input'})
        self.fields['password2'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input'})

    def clean_email(self):
        """Valida que el correo no se encuentre registrado previamente."""
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado.')
        return email

    def save(self, commit=True):
        """Asigna el correo validado al usuario antes de persistir."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Formulario de autenticación con widgets visuales consistentes."""
    username = forms.CharField(label='Usuario')
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        """Inicializa los campos de acceso con placeholders y clases visuales."""
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'admin o tu usuario', 'class': 'form-input'})
        self.fields['password'].widget.attrs.update({'placeholder': '••••••••••••', 'class': 'form-input'})

