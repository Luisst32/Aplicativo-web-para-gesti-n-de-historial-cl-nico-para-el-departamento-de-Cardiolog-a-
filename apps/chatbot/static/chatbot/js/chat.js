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

  function dividirEnLineas(texto, maxLongitud = 20) {
    if (typeof texto !== 'string' || texto.length <= maxLongitud) return texto;
    const palabras = texto.split(' ');
    const lineas = [];
    let lineaActual = '';
    palabras.forEach(palabra => {
      if ((lineaActual + ' ' + palabra).trim().length <= maxLongitud) {
        lineaActual = (lineaActual + ' ' + palabra).trim();
      } else {
        if (lineaActual) lineas.push(lineaActual);
        lineaActual = palabra;
      }
    });
    if (lineaActual) lineas.push(lineaActual);
    return lineas;
  }

  function renderizarGraficoEnBurbuja(divContenedor, cfg) {
    try {
      divContenedor.classList.add('mensaje-con-grafico');

      const card = document.createElement('div');
      card.className = 'chat-chart-card';
      card.style.cssText = 'margin-top: 14px; padding: 14px 16px; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); width: 100%; box-sizing: border-box; overflow: hidden;';

      if (cfg.title) {
        const titleEl = document.createElement('div');
        titleEl.style.cssText = 'font-weight: 700; font-size: 13.5px; color: #0F172A; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; line-height: 1.35;';
        titleEl.innerHTML = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2.3" style="flex-shrink:0;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg> <span>${cfg.title}</span>`;
        card.appendChild(titleEl);
      }

      const canvasWrap = document.createElement('div');
      canvasWrap.style.cssText = 'position: relative; width: 100%;';
      const canvas = document.createElement('canvas');
      canvasWrap.appendChild(canvas);
      card.appendChild(canvasWrap);
      divContenedor.appendChild(card);

      const palette = ['#2563EB', '#0D9488', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#10B981', '#6366F1'];
      const tipo = (cfg.type || 'bar').toLowerCase();

      if (tipo === 'pie' || tipo === 'doughnut') {
        canvasWrap.style.height = '230px';
        new Chart(canvas.getContext('2d'), {
          type: 'pie',
          data: {
            labels: cfg.labels || [],
            datasets: [{
              data: cfg.data || [],
              backgroundColor: palette.slice(0, (cfg.labels || []).length),
              borderWidth: 2,
              borderColor: '#FFFFFF'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: { color: '#000000', font: { size: 11, weight: 'bold' }, boxWidth: 12, padding: 8 }
              },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    const unit = cfg.unit ? ` ${cfg.unit}` : '';
                    return ` ${ctx.label}: ${ctx.raw}${unit}`;
                  }
                }
              }
            }
          }
        });
      } else if (tipo === 'scatter') {
        canvasWrap.style.height = '240px';
        new Chart(canvas.getContext('2d'), {
          type: 'scatter',
          data: {
            datasets: [{
              label: cfg.title || 'Cohorte',
              data: cfg.points || [],
              backgroundColor: 'rgba(37, 99, 235, 0.75)',
              borderColor: '#1D4ED8',
              pointRadius: 5,
              pointHoverRadius: 7
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                title: { display: !!cfg.xLabel, text: cfg.xLabel || '', color: '#000000', font: { weight: 'bold', size: 11 } },
                ticks: { color: '#000000', font: { weight: '600' } },
                grid: { color: 'rgba(0,0,0,0.06)' }
              },
              y: {
                title: { display: !!cfg.yLabel, text: cfg.yLabel || '', color: '#000000', font: { weight: 'bold', size: 11 } },
                ticks: { color: '#000000', font: { weight: '600' } },
                grid: { color: 'rgba(0,0,0,0.06)' }
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    const xL = cfg.xLabel || 'X';
                    const yL = cfg.yLabel || 'Y';
                    return ` ${xL}: ${ctx.raw.x} | ${yL}: ${ctx.raw.y}`;
                  }
                }
              }
            }
          }
        });
      } else {
        // Gráfico de barras inteligente:
        // Si las etiquetas son descriptivas o largas, usar barras horizontales para legibilidad óptima
        const rawLabels = cfg.labels || [];
        const tieneEtiquetaLarga = rawLabels.some(l => typeof l === 'string' && l.length > 9);
        const esHorizontal = cfg.horizontal || (cfg.indexAxis === 'y') || tieneEtiquetaLarga || (rawLabels.length <= 5);

        const formattedLabels = rawLabels.map(l => dividirEnLineas(l, esHorizontal ? 22 : 14));
        const numItems = rawLabels.length;
        const alturaCanvas = esHorizontal 
          ? Math.max(160, Math.min(360, numItems * 50 + 45))
          : Math.max(220, 240);
        canvasWrap.style.height = `${alturaCanvas}px`;

        new Chart(canvas.getContext('2d'), {
          type: 'bar',
          data: {
            labels: formattedLabels,
            datasets: [{
              data: cfg.data || [],
              backgroundColor: palette.slice(0, numItems),
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: esHorizontal ? 'y' : 'x',
            responsive: true,
            maintainAspectRatio: false,
            layout: {
              padding: {
                right: esHorizontal ? 32 : 10,
                top: esHorizontal ? 6 : 18
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    const unit = cfg.unit ? ` ${cfg.unit}` : '';
                    return ` ${ctx.raw}${unit}`;
                  }
                }
              }
            },
            scales: esHorizontal ? {
              x: {
                beginAtZero: true,
                suggestedMax: (cfg.unit === '%' || (cfg.data && Math.max(...cfg.data) > 60 && Math.max(...cfg.data) <= 100)) ? 100 : undefined,
                ticks: {
                  color: '#000000',
                  font: { weight: '600', size: 11 },
                  callback: function (val) {
                    return (cfg.unit === '%') ? val + '%' : val;
                  }
                },
                grid: { color: 'rgba(0,0,0,0.06)' }
              },
              y: {
                ticks: {
                  color: '#000000',
                  font: { weight: '600', size: 11.5 },
                  autoSkip: false
                },
                grid: { display: false }
              }
            } : {
              x: {
                ticks: {
                  color: '#000000',
                  font: { weight: '600', size: 11 },
                  maxRotation: 0,
                  minRotation: 0,
                  autoSkip: false
                },
                grid: { display: false }
              },
              y: {
                beginAtZero: true,
                suggestedMax: (cfg.unit === '%' || (cfg.data && Math.max(...cfg.data) > 60 && Math.max(...cfg.data) <= 100)) ? 100 : undefined,
                ticks: {
                  color: '#000000',
                  font: { weight: '600' },
                  callback: function (val) {
                    return (cfg.unit === '%') ? val + '%' : val;
                  }
                },
                grid: { color: 'rgba(0,0,0,0.06)' }
              }
            }
          },
          plugins: [{
            id: 'barValuesPlugin',
            afterDatasetsDraw(chart) {
              const { ctx } = chart;
              chart.data.datasets.forEach((dataset, datasetIdx) => {
                const meta = chart.getDatasetMeta(datasetIdx);
                if (!meta.hidden) {
                  meta.data.forEach((barEl, idx) => {
                    const val = dataset.data[idx];
                    if (val !== undefined && val !== null) {
                      const unit = cfg.unit ? ` ${cfg.unit}` : '';
                      const txt = `${val}${unit}`;
                      ctx.save();
                      ctx.font = 'bold 11px Inter, sans-serif';
                      ctx.fillStyle = '#0F172A';
                      if (esHorizontal) {
                        const xPos = Math.min(barEl.x + 8, chart.width - 40);
                        ctx.textAlign = 'left';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(txt, xPos, barEl.y);
                      } else {
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(txt, barEl.x, Math.max(barEl.y - 4, 12));
                      }
                      ctx.restore();
                    }
                  });
                }
              });
            }
          }]
        });
      }
    } catch (err) {
      console.warn('Error instanciando gráfico Chart.js en chatbot:', err);
    }
  }

  function agregarBurbujaBot(markdownTexto, incluirSugerencias = false) {
    const conts = [
      document.getElementById('chat-page-messages'),
      document.getElementById('chat-messages')
    ].filter(Boolean);

    // Extraer bloque json_chart si existe
    const chartRegex = /```json_chart\s*([\s\S]*?)```/i;
    const chartMatch = (markdownTexto || '').match(chartRegex);
    let chartConfig = null;
    let textoMarkdownLimpio = markdownTexto || '';

    if (chartMatch) {
      try {
        chartConfig = JSON.parse(chartMatch[1].trim());
        textoMarkdownLimpio = markdownTexto.replace(chartRegex, '').trim();
      } catch (e) {
        console.warn('Error al parsear bloque json_chart:', e);
      }
    }

    conts.forEach(cont => {
      const div = document.createElement('div');
      div.className = 'mensaje mensaje-asistente';

      let htmlContenido = '';
      if (typeof marked !== 'undefined') {
        htmlContenido = marked.parse(textoMarkdownLimpio);
      } else {
        htmlContenido = `<p>${textoMarkdownLimpio.replace(/\n/g, '<br>')}</p>`;
      }

      div.innerHTML = htmlContenido;
      renderLatex(div);

      // Renderizar gráfico interactivo Chart.js si se solicitó
      if (chartConfig && typeof Chart !== 'undefined') {
        renderizarGraficoEnBurbuja(div, chartConfig);
      }

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
