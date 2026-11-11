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
        btnEnviarForgot.textContent = 'Enviando correo de recuperación...';
      }
      if (forgotAlertBox) forgotAlertBox.style.display = 'none';

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
        var data = result.data || {};
        if (!result.ok || data.status === 'error') {
          mostrarAlertaForgot(data.message || 'Error al procesar la solicitud.', 'error');
          if (btnEnviarForgot) {
            btnEnviarForgot.disabled = false;
            btnEnviarForgot.textContent = 'Enviar correo de recuperación';
          }
          return;
        }

        // Caso 1: Correo entregado exitosamente por SMTP real
        if (data.smtp_delivered) {
          mostrarAlertaForgot(data.message, 'success');
          if (btnEnviarForgot) {
            btnEnviarForgot.textContent = 'Correo enviado';
            btnEnviarForgot.disabled = true;
          }
          return;
        }

        // Caso 2: Puertos SMTP bloqueados por ISP o entorno local, proveemos enlace directo de recuperación
        if (data.reset_url) {
          var warningHtml = '<div style="margin-bottom: 10px;">' +
            '<strong>Aviso de conexión de red:</strong> ' +
            escapeHtml(data.message) +
            '</div>' +
            '<div style="text-align: center; margin: 12px 0 6px 0;">' +
            '<a href="' + data.reset_url + '" class="btn-direct-reset">' +
            'Restablecer mi contraseña ahora &rarr;' +
            '</a>' +
            '</div>';
          mostrarAlertaForgotHtml(warningHtml, 'warning');
          if (btnEnviarForgot) {
            btnEnviarForgot.disabled = false;
            btnEnviarForgot.textContent = 'Generar nuevo enlace';
          }
          return;
        }

        // Caso genérico
        mostrarAlertaForgot(data.message || 'Solicitud procesada correctamente.', 'info');
      })
      .catch(function (err) {
        mostrarAlertaForgot('Error de conexión al enviar solicitud: ' + err.message, 'error');
        if (btnEnviarForgot) {
          btnEnviarForgot.disabled = false;
          btnEnviarForgot.textContent = 'Enviar correo de recuperación';
        }
      });
    });
  }

  function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function mostrarAlertaForgotHtml(html, tipo) {
    if (!forgotAlertBox) return;
    forgotAlertBox.className = 'alert-box ' + tipo;
    forgotAlertBox.innerHTML = html;
    forgotAlertBox.style.display = 'block';
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
