/**
 * ============================================================================
 * CHAT.JS - Motor del Asistente Clínico & Estadístico CARDIOUNEMI
 * ============================================================================
 * Maneja la interacción en tiempo real del Chatbot:
 * - Comunicación asíncrona con el endpoint /chatbot/query/
 * - Renderizado de Markdown rico (Marked.js) y fórmulas KaTeX
 * - Soporte sincronizado para Widget Flotante y Vista Completa
 * - Chips de sugerencias interactivas
 * - Indicadores de procesamiento y manejo de errores
 * ============================================================================
 */

(function () {
  'use strict';

  // Configuración de Marked para Markdown seguro
  if (typeof marked !== 'undefined') {
    marked.setOptions({
      gfm: true,
      breaks: true,
      headerIds: false
    });
  }

  // Obtener cookie CSRF de Django
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Renderizar fórmulas LaTeX con KaTeX
  function renderLatex(container) {
    if (typeof renderMathInElement === 'function' && container) {
      try {
        renderMathInElement(container, {
          delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '$', right: '$', display: false },
            { left: '\\(', right: '\\)', display: false },
            { left: '\\[', right: '\\]', display: true }
          ],
          throwOnError: false
        });
      } catch (err) {
        console.warn('KaTeX render warning:', err);
      }
    }
  }

  const MENSAJE_BIENVENIDA = `¡Hola! Soy el **Asistente Clínico & Estadístico de CARDIOUNEMI**.

Estoy aquí para responder preguntas analíticas, estadísticas y epidemiológicas sobre la cohorte institucional de salud cardiovascular ($N = 59$ evaluados).

*Puedes consultarme por ejemplo:*
- *¿Cuántos evaluados hay en total y cómo se distribuyen por sexo?*
- *¿Cuál es la prevalencia de hipertensión arterial y cifras medias?*
- *¿Qué porcentaje de la cohorte tiene sobrepeso u obesidad?*
- *¿Cuáles son los principales hallazgos en el electrocardiograma?*
- *¿Cómo se estratifica el riesgo cardiovascular global de los trabajadores?*`;

  const SUGERENCIAS = [
    '¿Cuántos evaluados hay en total?',
    'Prevalencia de hipertensión arterial',
    'Distribución de IMC y obesidad',
    'Hallazgos en el electrocardiograma',
    'Estratificación de riesgo cardiovascular'
  ];

  document.addEventListener('DOMContentLoaded', () => {
    inicializarChat();
  });

  function inicializarChat() {
    // Contenedores
    const contMensajesPagina = document.getElementById('chat-page-messages');
    const contMensajesWidget = document.getElementById('chat-messages');

    // Inputs y Formularios
    const formPagina = document.getElementById('chat-page-form');
    const inputPagina = document.getElementById('chat-page-input');
    const formWidget = document.getElementById('formulario-chat');
    const inputWidget = document.getElementById('chat-input');

    // Botones del Widget
    const btnFlotante = document.getElementById('btn-flotante-chat');
    const ventanaWidget = document.getElementById('contenedor-chat');
    const btnCerrar = document.getElementById('btn-cerrar-chat');
    const btnExpandir = document.getElementById('btn-expandir-chat');
    const backdropWidget = document.getElementById('chat-backdrop-widget');

    // Limpiar y mostrar bienvenida inicial con sugerencias
    if (contMensajesPagina) contMensajesPagina.innerHTML = '';
    if (contMensajesWidget) contMensajesWidget.innerHTML = '';

    mostrarBienvenida();

    // Eventos de envío
    if (formPagina && inputPagina) {
      formPagina.addEventListener('submit', (e) => {
        e.preventDefault();
        const texto = inputPagina.value.trim();
        if (!texto) return;
        inputPagina.value = '';
        enviarConsulta(texto);
      });
    }

    if (formWidget && inputWidget) {
      formWidget.addEventListener('submit', (e) => {
        e.preventDefault();
        const texto = inputWidget.value.trim();
        if (!texto) return;
        inputWidget.value = '';
        enviarConsulta(texto);
      });
    }

    // Apertura del widget flotante
    if (btnFlotante && ventanaWidget) {
      btnFlotante.addEventListener('click', () => {
        ventanaWidget.classList.remove('oculta');
        btnFlotante.classList.add('oculto');
        if (inputWidget) setTimeout(() => inputWidget.focus(), 150);
        hacerScrollAlFinal();
      });
    }

    // Cierre del widget flotante
    if (btnCerrar && ventanaWidget && btnFlotante) {
      btnCerrar.addEventListener('click', () => {
        ventanaWidget.classList.add('oculta');
        ventanaWidget.classList.remove('modo-centrado');
        if (backdropWidget) backdropWidget.classList.remove('activo');
        btnFlotante.classList.remove('oculto');
      });
    }

    // Modo expandido / centrado
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
        mostrarBienvenida();
      });
    });
  }

  function mostrarBienvenida() {
    agregarBurbujaBot(MENSAJE_BIENVENIDA, true);
  }

  function agregarBurbujaUsuario(texto) {
    const conts = [
      document.getElementById('chat-page-messages'),
      document.getElementById('chat-messages')
    ].filter(Boolean);

    conts.forEach(cont => {
      const div = document.createElement('div');
      div.className = 'mensaje mensaje-usuario';
      div.textContent = texto;
      cont.appendChild(div);
    });

    hacerScrollAlFinal();
  }

  function agregarBurbujaBot(markdownTexto, incluirSugerencias = false) {
    const conts = [
      document.getElementById('chat-page-messages'),
      document.getElementById('chat-messages')
    ].filter(Boolean);

    conts.forEach(cont => {
      const div = document.createElement('div');
      div.className = 'mensaje mensaje-asistente';

      let htmlContenido = '';
      if (typeof marked !== 'undefined') {
        htmlContenido = marked.parse(markdownTexto);
      } else {
        htmlContenido = `<p>${markdownTexto.replace(/\n/g, '<br>')}</p>`;
      }

      div.innerHTML = htmlContenido;
      renderLatex(div);

      // Si se solicitan chips de sugerencia rápida
      if (incluirSugerencias) {
        const chipsContainer = document.createElement('div');
        chipsContainer.className = 'chat-suggestion-chips';
        chipsContainer.style.cssText = 'display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(148, 163, 184, 0.35);';

        SUGERENCIAS.forEach(sug => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'chat-chip-btn';
          chip.style.cssText = 'background: #F1F5F9; border: 1px solid #CBD5E1; color: #1E293B; font-size: 11.5px; padding: 5px 10px; border-radius: 14px; cursor: pointer; transition: all 0.15s ease; font-weight: 500; text-align: left;';
          chip.textContent = sug;

          chip.addEventListener('mouseenter', () => {
            chip.style.background = '#3AA0FF';
            chip.style.borderColor = '#2563EB';
            chip.style.color = '#FFFFFF';
          });
          chip.addEventListener('mouseleave', () => {
            chip.style.background = '#F1F5F9';
            chip.style.borderColor = '#CBD5E1';
            chip.style.color = '#1E293B';
          });

          chip.addEventListener('click', () => {
            enviarConsulta(sug);
          });

          chipsContainer.appendChild(chip);
        });

        div.appendChild(chipsContainer);
      }

      cont.appendChild(div);
    });

    hacerScrollAlFinal();
  }

  function mostrarIndicador(mostrar) {
    const indPage = document.getElementById('typing-indicator-page');
    const indWidget = document.getElementById('typing-indicator');

    [indPage, indWidget].filter(Boolean).forEach(el => {
      if (mostrar) {
        el.classList.remove('oculto');
      } else {
        el.classList.add('oculto');
      }
    });

    // Deshabilitar temporalmente inputs mientras se procesa
    const btnSendPage = document.getElementById('btn-enviar-chat-page');
    const btnSendWidget = document.getElementById('send-btn');
    [btnSendPage, btnSendWidget].filter(Boolean).forEach(b => {
      b.disabled = mostrar;
      b.style.opacity = mostrar ? '0.6' : '1';
    });

    if (mostrar) hacerScrollAlFinal();
  }

  async function enviarConsulta(pregunta) {
    const q = (pregunta || '').trim();
    if (!q) return;

    // Mostrar mensaje del usuario
    agregarBurbujaUsuario(q);

    // Mostrar indicador de "procesando..."
    mostrarIndicador(true);

    try {
      const csrftoken = getCookie('csrftoken') || (document.querySelector('[name=csrfmiddlewaretoken]')?.value) || '';

      const resp = await fetch('/chatbot/query/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ question: q })
      });

      const data = await resp.json();
      mostrarIndicador(false);

      if (data && data.response) {
        agregarBurbujaBot(data.response);
      } else if (data && data.message) {
        agregarBurbujaBot(`⚠️ ${data.message}`);
      } else {
        agregarBurbujaBot('Lo siento, ocurrió un error inesperado al procesar su consulta.');
      }

    } catch (err) {
      console.error('Error al consultar al chatbot:', err);
      mostrarIndicador(false);
      agregarBurbujaBot('⚠️ Error de comunicación con el servidor. Por favor verifique su conexión o intente nuevamente.');
    }
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
    }, 60);
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
    },
    enviarMensaje: (texto) => {
      enviarConsulta(texto);
    }
  };

})();
