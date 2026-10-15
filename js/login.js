document.getElementById('btnEye').addEventListener('click', function () {
  var input = document.getElementById('password');
  var eye = document.getElementById('iconEye');
  var eyeSlash = document.getElementById('iconEyeSlash');
  var showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  eye.style.display = showing ? 'block' : 'none';
  eyeSlash.style.display = showing ? 'none' : 'block';
});

document.getElementById('btnForgot').addEventListener('click', function () {
  alert('Para restablecer tu contraseña, contacta a la administración de la clínica.');
});

document.getElementById('loginForm').addEventListener('submit', function (e) {
  e.preventDefault();
  var email = document.getElementById('email').value.trim();
  var pass = document.getElementById('password').value.trim();
  var alertBox = document.getElementById('alertBox');
  var btn = document.getElementById('btnEntrar');

  alertBox.className = 'alert-box';

  if (!email || !pass) {
    alertBox.className = 'alert-box error';
    alertBox.textContent = 'Por favor completa tu correo y contraseña.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Accediendo...';

  setTimeout(function () {
    alertBox.className = 'alert-box success';
    alertBox.textContent = 'Credenciales correctas. Ingresando...';
    btn.disabled = false;
    btn.textContent = 'Entrar';
    setTimeout(function() {
      window.location.href = 'formularios-listado.html';
    }, 400);
  }, 600);
});
