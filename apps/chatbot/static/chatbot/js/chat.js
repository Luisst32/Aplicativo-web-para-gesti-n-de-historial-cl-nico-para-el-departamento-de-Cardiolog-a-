/**
 * ============================================================================
 * CHAT-ENGINE.JS - Plantilla Visual del Asistente CARDIOUNEMI
 * ============================================================================
 * Modo plantilla / maqueta visual:
 * - Sin respuestas automáticas simuladas ni textos precargados.
 * - Control de apertura, cierre, ampliación y limpieza de la interfaz.
 * - Permite al usuario escribir y visualizar sus mensajes como maqueta.
 * ============================================================================
 */

(function () {
  'use strict';

  // Limpiar cualquier historial residual para mantener la plantilla impecable
  try {
    sessionStorage.removeItem('cardiounemi_chat_history_v1');
    sessionStorage.removeItem('cardiounemi_chat_history');
  } catch (e) {
    // ignorar
  }

  document.addEventListener('DOMContentLoaded', () => {
    inicializarElementosDOM();
  });

  function inicializarElementosDOM() {
    // Contenedores de mensajes
    const contMensajesPagina = document.getElementById('chat-page-messages');
    const contMensajesWidget = document.getElementById('chat-messages');

    // Formularios e inputs
    const formPagina = document.getElementById('chat-page-form');
    const inputPagina = document.getElementById('chat-page-input');
    const formWidget = document.getElementById('formulario-chat');
    const inputWidget = document.getElementById('chat-input');

    // Botones del widget
    const btnFlotante = document.getElementById('btn-flotante-chat');
    const ventanaWidget = document.getElementById('contenedor-chat');
    const btnCerrar = document.getElementById('btn-cerrar-chat');
    const btnMinimizar = document.getElementById('btn-minimizar-chat');
    const btnExpandir = document.getElementById('btn-expandir-chat');
    const backdropWidget = document.getElementById('chat-backdrop-widget');

    // Limpiar contenido previo que pudiera quedar en el DOM
    if (contMensajesPagina) contMensajesPagina.innerHTML = '';
    if (contMensajesWidget) contMensajesWidget.innerHTML = '';

    // Mensaje de prueba inicial
    mostrarMensajeBot('Hola');

    // Manejador en página completa
    if (formPagina && inputPagina) {
      formPagina.addEventListener('submit', (e) => {
        e.preventDefault();
        const texto = inputPagina.value.trim();
        if (!texto) return;
        inputPagina.value = '';
        agregarMensajeUsuario(texto);
      });
    }

    // Manejador en widget flotante
    if (formWidget && inputWidget) {
      formWidget.addEventListener('submit', (e) => {
        e.preventDefault();
        const texto = inputWidget.value.trim();
        if (!texto) return;
        inputWidget.value = '';
        agregarMensajeUsuario(texto);
      });
    }

    // Abrir widget flotante
    if (btnFlotante && ventanaWidget) {
      btnFlotante.addEventListener('click', () => {
        ventanaWidget.classList.remove('oculta');
        btnFlotante.classList.add('oculto');
        if (inputWidget) setTimeout(() => inputWidget.focus(), 150);
        hacerScrollAlFinal();
      });
    }

    // Cerrar widget flotante
    if (btnCerrar && ventanaWidget && btnFlotante) {
      btnCerrar.addEventListener('click', () => {
        ventanaWidget.classList.add('oculta');
        ventanaWidget.classList.remove('modo-centrado');
        if (backdropWidget) backdropWidget.classList.remove('activo');
        btnFlotante.classList.remove('oculto');
      });
    }

    // Minimizar widget flotante
    if (btnMinimizar && ventanaWidget && btnFlotante) {
      btnMinimizar.addEventListener('click', () => {
        ventanaWidget.classList.add('oculta');
        btnFlotante.classList.remove('oculto');
      });
    }

    // Expandir / modo centrado
    if (btnExpandir && ventanaWidget) {
      btnExpandir.addEventListener('click', () => {
        ventanaWidget.classList.toggle('modo-centrado');
        if (backdropWidget) {
          backdropWidget.classList.toggle('activo', ventanaWidget.classList.contains('modo-centrado'));
        }
      });
    }

    if (backdropWidget && ventanaWidget) {
      backdropWidget.addEventListener('click', () => {
        ventanaWidget.classList.remove('modo-centrado');
        backdropWidget.classList.remove('activo');
      });
    }

    // Limpiar conversación
    const todosBtnLimpiar = document.querySelectorAll('#btn-limpiar-chat, #btn-limpiar-chat-page');
    todosBtnLimpiar.forEach(btn => {
      btn.addEventListener('click', () => {
        if (contMensajesPagina) contMensajesPagina.innerHTML = '';
        if (contMensajesWidget) contMensajesWidget.innerHTML = '';
        mostrarMensajeBot('Hola');
      });
    });
  }

  function mostrarMensajeBot(texto) {
    const conts = [
      document.getElementById('chat-page-messages'),
      document.getElementById('chat-messages')
    ].filter(Boolean);

    conts.forEach(cont => {
      const div = document.createElement('div');
      div.className = 'mensaje mensaje-bot';
      div.innerText = texto;
      cont.appendChild(div);
    });

    hacerScrollAlFinal();
  }

  function agregarMensajeUsuario(texto) {
    const conts = [
      document.getElementById('chat-page-messages'),
      document.getElementById('chat-messages')
    ].filter(Boolean);

    conts.forEach(cont => {
      const div = document.createElement('div');
      div.className = 'mensaje mensaje-usuario';
      div.innerText = texto;
      cont.appendChild(div);
    });

    hacerScrollAlFinal();

    // Respuesta de prueba
    setTimeout(() => {
      mostrarMensajeBot('Hola');
    }, 400);
  }

  function hacerScrollAlFinal() {
    setTimeout(() => {
      const conts = [
        document.getElementById('chat-page-messages'),
        document.getElementById('chat-messages')
      ].filter(Boolean);

      conts.forEach(cont => {
        cont.scrollTop = cont.scrollHeight;
      });
    }, 50);
  }

  // Objeto global para control de apertura/cierre
  window.CardioUnemiChat = {
    abrirWidget: () => {
      const v = document.getElementById('contenedor-chat');
      const b = document.getElementById('btn-flotante-chat');
      if (v) v.classList.remove('oculta');
      if (b) b.classList.add('oculto');
    },
    cerrarWidget: () => {
      const v = document.getElementById('contenedor-chat');
      const b = document.getElementById('btn-flotante-chat');
      if (v) v.classList.add('oculta');
      if (b) b.classList.remove('oculto');
    }
  };

})();
