/**
 * LOGIN.JS
 * Lógica de cliente para la interfaz de inicio de sesión:
 * alternar visibilidad de contraseña, validación previa de campos,
 * y recuperación institucional de contraseñas olvidadas.
 */

document.addEventListener('DOMContentLoaded', function () {
  var btnEye = document.getElementById('btnEye');
  var inputPass = document.getElementById('password');
  var iconEye = document.getElementById('iconEye');
  var iconEyeSlash = document.getElementById('iconEyeSlash');

  var loginForm = document.getElementById('loginForm');
  var alertBox = document.getElementById('alertBox');
  var btnEntrar = document.getElementById('btnEntrar');

  var btnForgot = document.getElementById('btnForgot');
  var btnBackToLogin = document.getElementById('btnBackToLogin');
  var loginSection = document.getElementById('loginSection');
  var forgotSection = document.getElementById('forgotSection');
  var forgotForm = document.getElementById('forgotForm');
  var forgotEmail = document.getElementById('forgotEmail');
  var forgotAlertBox = document.getElementById('forgotAlertBox');
  var btnEnviarForgot = document.getElementById('btnEnviarForgot');
  var debugResetContainer = document.getElementById('debugResetLinkContainer');
  var debugResetAnchor = document.getElementById('debugResetLinkAnchor');

  // 1. Alternar visualización de contraseña
  if (btnEye && inputPass) {
    btnEye.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var isPassword = inputPass.type === 'password';
      inputPass.type = isPassword ? 'text' : 'password';
      if (iconEye) iconEye.style.display = isPassword ? 'none' : 'block';
      if (iconEyeSlash) iconEyeSlash.style.display = isPassword ? 'block' : 'none';
      btnEye.setAttribute('aria-label', isPassword ? 'Ocultar contraseña' : 'Ver contraseña');
      btnEye.setAttribute('title', isPassword ? 'Ocultar contraseña' : 'Ver contraseña');
      inputPass.focus();
    });
  }

  // 2. Navegación fluida: Cambiar a panel de recuperación
  function mostrarRecuperacion() {
    if (loginSection) loginSection.style.display = 'none';
    if (forgotSection) {
      forgotSection.style.display = 'block';
      var emailInput = document.getElementById('email');
      if (emailInput && emailInput.value.trim() && forgotEmail && !forgotEmail.value) {
        forgotEmail.value = emailInput.value.trim();
      }
      if (forgotEmail) forgotEmail.focus();
    }
  }

  function mostrarLogin() {
    if (forgotSection) forgotSection.style.display = 'none';
    if (loginSection) {
      loginSection.style.display = 'block';
      var emailInput = document.getElementById('email');
      if (emailInput) emailInput.focus();
    }
  }

  if (btnForgot) {
    btnForgot.addEventListener('click', function (e) {
      e.preventDefault();
      mostrarRecuperacion();
    });
  }

  if (btnBackToLogin) {
    btnBackToLogin.addEventListener('click', function (e) {
      e.preventDefault();
      mostrarLogin();
    });
  }

  // Apertura automática si la URL contiene ?action=forgot
  var urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('action') === 'forgot') {
    mostrarRecuperacion();
  }

  // 3. Envío de solicitud de recuperación de contraseña
  if (forgotForm) {
    forgotForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var identifierVal = forgotEmail ? forgotEmail.value.trim() : '';

      if (!identifierVal) {
        mostrarAlertaForgot('Por favor ingresa tu correo institucional o nombre de usuario.', 'error');
        if (forgotEmail) forgotEmail.focus();
        return;
      }

      if (btnEnviarForgot) {
        btnEnviarForgot.disabled = true;
        btnEnviarForgot.textContent = 'Enviando enlace de recuperación...';
      }
      if (forgotAlertBox) forgotAlertBox.style.display = 'none';
      if (debugResetContainer) debugResetContainer.style.display = 'none';

      fetch('/security/password-reset/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ email: identifierVal })
      })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok || result.data.status === 'error') {
          mostrarAlertaForgot(result.data.message || 'Error al procesar la solicitud.', 'error');
          if (btnEnviarForgot) {
            btnEnviarForgot.disabled = false;
            btnEnviarForgot.textContent = 'Enviar enlace de recuperación';
          }
          return;
        }

        // Éxito: mensaje claro de confirmación
        mostrarAlertaForgot(result.data.message, 'success');
        if (btnEnviarForgot) {
          btnEnviarForgot.textContent = 'Enlace enviado';
          btnEnviarForgot.disabled = true;
        }

        // Si se encuentra en modo DEBUG, mostrar enlace directo para pruebas inmediatas
        if (result.data.debug_reset_url && debugResetContainer && debugResetAnchor) {
          debugResetAnchor.href = result.data.debug_reset_url;
          debugResetContainer.style.display = 'block';
        }
      })
      .catch(function (err) {
        mostrarAlertaForgot('Error de conexión al enviar solicitud: ' + err.message, 'error');
        if (btnEnviarForgot) {
          btnEnviarForgot.disabled = false;
          btnEnviarForgot.textContent = 'Enviar enlace de recuperación';
        }
      });
    });
  }

  function mostrarAlertaForgot(msg, tipo) {
    if (!forgotAlertBox) return;
    forgotAlertBox.className = 'alert-box ' + tipo;
    forgotAlertBox.textContent = msg;
    forgotAlertBox.style.display = 'block';
  }

  // 4. Validación de inicio de sesión estándar
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      var emailInput = document.getElementById('email');
      var emailVal = emailInput ? emailInput.value.trim() : '';
      var passVal = inputPass ? inputPass.value.trim() : '';

      if (!emailVal || !passVal) {
        e.preventDefault();
        if (alertBox) {
          alertBox.className = 'alert-box error';
          alertBox.textContent = 'Por favor completa tu correo y contraseña.';
          alertBox.style.display = 'block';
        }
        return;
      }

      if (btnEntrar) {
        btnEntrar.disabled = true;
        btnEntrar.textContent = 'Accediendo...';
      }
    });
  }

  function getCsrfToken() {
    var cookieVal = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === 'csrftoken=') {
          cookieVal = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    if (!cookieVal) {
      var csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (csrfInput) cookieVal = csrfInput.value;
    }
    return cookieVal || '';
  }
});
