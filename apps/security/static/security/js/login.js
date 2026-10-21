/**
 * LOGIN.JS
 * Lógica de cliente para la interfaz de inicio de sesión:
 * alternar visibilidad de contraseña, validación previa de campos y feedback visual.
 */

document.addEventListener('DOMContentLoaded', function () {
  var btnEye = document.getElementById('btnEye');
  var inputPass = document.getElementById('password');
  var iconEye = document.getElementById('iconEye');
  var iconEyeSlash = document.getElementById('iconEyeSlash');
  var btnForgot = document.getElementById('btnForgot');
  var form = document.getElementById('loginForm');
  var alertBox = document.getElementById('alertBox');
  var btnEntrar = document.getElementById('btnEntrar');

  if (btnEye && inputPass) {
    btnEye.addEventListener('click', function () {
      var isPassword = inputPass.type === 'password';
      inputPass.type = isPassword ? 'text' : 'password';
      if (iconEye) iconEye.style.display = isPassword ? 'none' : 'block';
      if (iconEyeSlash) iconEyeSlash.style.display = isPassword ? 'block' : 'none';
    });
  }

  if (btnForgot) {
    btnForgot.addEventListener('click', function () {
      alert('Para restablecer tu contraseña, contacta al administrador del sistema.');
    });
  }

  if (form) {
    form.addEventListener('submit', function (e) {
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
});
