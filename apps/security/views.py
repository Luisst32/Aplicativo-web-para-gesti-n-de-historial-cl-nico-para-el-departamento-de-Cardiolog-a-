from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .models import User


def login_view(request):
    """
    Autenticación institucional de usuarios.
    Permite el inicio de sesión con correo electrónico o nombre de usuario.
    """
    if request.user.is_authenticated:
        next_url = request.GET.get('next')
        if not next_url or next_url in ('/', '/dashboard/'):
            return redirect('clinical:list')
        return redirect(next_url)

    error_message = None

    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip() or request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not identifier or not password:
            error_message = 'Por favor completa tu correo y contraseña.'
        else:
            user_obj = None
            if '@' in identifier:
                user_obj = User.objects.filter(email__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(username__iexact=identifier).first()

            username_to_auth = user_obj.username if user_obj else identifier
            user = authenticate(request, username=username_to_auth, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)
                    next_url = request.GET.get('next')
                    if not next_url or next_url in ('/', '/dashboard/'):
                        return redirect('clinical:list')
                    return redirect(next_url)
                else:
                    error_message = 'Tu cuenta de usuario se encuentra inactiva.'
            else:
                error_message = 'Credenciales incorrectas. Verifica tu correo y contraseña.'

    context = {
        'error_message': error_message
    }
    return render(request, 'security/login.html', context)


def logout_view(request):
    """
    Cierra la sesión del usuario actual y lo redirige al formulario de inicio de sesión.
    """
    logout(request)
    return redirect('security:login')
