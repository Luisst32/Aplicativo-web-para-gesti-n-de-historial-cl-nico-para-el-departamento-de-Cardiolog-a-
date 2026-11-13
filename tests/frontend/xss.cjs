// Run from the repository root; jsdom is test tooling, not an application dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { test } = require('node:test');
let JSDOM;
try { ({ JSDOM } = require('jsdom')); }
catch { ({ JSDOM } = require(path.join(os.tmpdir(), 'cardio-a03-node/node_modules/jsdom'))); }
const root = path.resolve(__dirname, '../..');
const source = file => fs.readFileSync(path.join(root, file), 'utf8');
const payload = `</script><img src=x onerror="window.__xss=1"><svg onload="window.__xss=2"></svg>'\"&`;

function environment(body = '') {
  const dom = new JSDOM(`<!doctype html><body>${body}</body>`, { url: 'https://clinic.example/', runScripts: 'dangerously' });
  const w = dom.window;
  // Exercise renderers directly; prevent unrelated async page initialization.
  const listen = w.document.addEventListener.bind(w.document);
  w.document.addEventListener = (name, ...args) => name === 'DOMContentLoaded' ? undefined : listen(name, ...args);
  w.scrollTo = () => {};
  w.print = () => {};
  w.eval(source('static/js/global/utils.js'));
  return { w, close: () => w.close() };
}

function noPayloadExecution(w, element) {
  assert.equal(element.querySelectorAll('img,script,iframe,object,form').length, 0);
  for (const node of element.querySelectorAll('*')) {
    for (const attribute of node.attributes) {
      assert.ok(!/^on/i.test(attribute.name), `unexpected event handler ${attribute.name}`);
      if (['href', 'src'].includes(attribute.name)) {
        assert.ok(!/^\s*(javascript|vbscript|data):/i.test(attribute.value));
      }
    }
    node.dispatchEvent(new w.Event('error'));
    node.dispatchEvent(new w.Event('load'));
  }
  assert.equal(w.__xss, undefined);
}

function loadList(w) {
  w.eval(source('apps/clinical/static/clinical/js/pacientes.js'));
  w.eval(source('apps/clinical/static/clinical/js/list.js'));
}

function patient() {
  return { id: `p1');window.__xss=3;//`, nombre: payload, codigo: payload, cedula: payload,
    correo: payload, telefono: payload, estamento: payload, facultad: payload,
    fechaNac: '1990-01-01', sexo: 'H', historiales: [{ id: 'h_1', fechaVisita: '2026-01-01',
      numeroVisita: payload, medico: payload, tipo: payload, tas: payload, tsi: payload,
      peso: payload, talla: 170, imc: payload, riesgoGlobal: payload }] };
}

test('patient row renders stored markup as text and binds raw values without JS source interpolation', () => {
  const e = environment(); const { w } = e;
  try {
    loadList(w); const p = patient(); let received;
    w.solicitarEliminarFicha = (...args) => { received = args; };
    const row = w.crearFilaPaciente(p); w.document.body.append(row);
    assert.ok(row.textContent.includes(payload));
    assert.equal(row.querySelector('input').getAttribute('onchange'), null);
    assert.equal(row.querySelector('button').getAttribute('onclick'), null);
    // Title and data-id are text attributes and must preserve literal input.
    assert.equal(row.querySelector('button').title, `Eliminar ficha clínica de ${p.nombre}`);
    row.querySelector('button').click();
    assert.deepEqual(received, [p.id, p.nombre, p.codigo]);
    assert.equal(row.querySelectorAll('img,script,svg[onload]').length, 0);
    assert.equal(w.__xss, undefined);
  } finally { e.close(); }
});

test('history evaluator and delete/PDF actions preserve data without executing it', () => {
  const ids = ['topPageTitle','expAvatar','expNombre','expEdadSexo','expEstamentoFacultad','timelineHistoriales'];
  const e = environment(ids.map(id => `<div id="${id}"></div>`).join('')); const { w } = e;
  try {
    loadList(w); w.__patients = [patient()]; w.eval('pacientes = window.__patients');
    let received; w.solicitarEliminarFicha = (...args) => { received = args; };
    w.abrirHistorialesPaciente(w.__patients[0].id);
    const timeline = w.document.getElementById('timelineHistoriales');
    assert.ok(timeline.textContent.includes(payload));
    noPayloadExecution(w, timeline);
    timeline.querySelector('[data-clinical-action="delete"]').click();
    assert.equal(received[1], payload);
  } finally { e.close(); }
});

test('printed clinical summary contains literal values, with no injected elements', () => {
  const e = environment('<div id="printFormsContainer"></div>'); const { w } = e;
  try {
    loadList(w); w.__patients = [patient()]; w.eval('pacientes = window.__patients');
    w.exportarPDFPaciente(w.__patients[0].id);
    const summary = w.document.getElementById('printFormsContainer');
    assert.ok(summary.textContent.includes(payload)); noPayloadExecution(w, summary);
  } finally { e.close(); }
});

test('sharing success/error cards escape provider output and copy through a closure', () => {
  const e = environment('<div id="listaCodigosGenerados"></div>'); const { w } = e;
  try {
    loadList(w); let received; w.copiarCodigoAcceso = (...args) => { received = args; };
    w.renderizarResultadosCodigos([{success:true,code:payload,email:payload,expires_display:payload},
      {success:false,email:payload,error:payload}]);
    const cards = w.document.getElementById('listaCodigosGenerados');
    assert.ok(cards.textContent.includes(payload));
    assert.equal(cards.querySelectorAll('img,script,svg[onload]').length,0);
    cards.querySelector('[data-copy-code]').click();
    assert.equal(received[1],payload); assert.equal(received[2],payload);
    assert.equal(w.__xss,undefined);
  } finally { e.close(); }
});

test('delete confirmation uses text nodes', () => {
  const e = environment('<div id="modalEliminarFicha"><p id="deleteModalMensaje"></p></div>'); const { w } = e;
  try {
    w.eval(source('static/js/global/eliminar_ficha.js'));
    w.solicitarEliminarFicha('1', payload, payload);
    const message = w.document.getElementById('deleteModalMensaje');
    assert.ok(message.textContent.includes(payload)); noPayloadExecution(w,message);
  } finally { e.close(); }
});

test('profile menu escapes user-controlled text and attributes', () => {
  const e = environment('<div data-user-menu></div>'); const { w } = e;
  try {
    w.CURRENT_USER = { nombre:payload, rol:payload, correo:payload };
    w.eval(source('static/js/global/ui.js')); w.initUserMenu();
    const menu = w.document.getElementById('userMenu');
    assert.ok(menu.textContent.includes(payload));
    assert.equal(menu.querySelectorAll('img,script,svg[onload]').length,0);
    assert.equal(w.__xss,undefined);
  } finally { e.close(); }
});

function loadChat(w, sanitizer=true, parser=true) {
  if (sanitizer) w.eval(source('static/vendor/dompurify/purify.min.js'));
  if (parser) w.eval(source('apps/chatbot/static/chatbot/vendor/marked.min.js'));
  // Test-only exposure of actual private rendering functions; application code is unchanged.
  const script = source('apps/chatbot/static/chatbot/js/chat.js').replace(/\}\)\(\);\s*$/,
    'window.__renderBot = agregarBurbujaBot; window.__renderChart = renderizarGraficoEnBurbuja; })();');
  w.eval(script);
}

test('bot Markdown strips scripts, event handlers, forms, SVG and javascript URLs', () => {
  const e = environment('<div id="chat-messages"></div>'); const { w } = e;
  try {
    loadChat(w);
    w.__renderBot(payload + '\n[unsafe](javascript:alert(1))\n<form><input autofocus onfocus="window.__xss=9"></form>');
    const bubble = w.document.querySelector('.mensaje-asistente');
    noPayloadExecution(w,bubble);
    for(const a of bubble.querySelectorAll('a')) assert.ok(!/^javascript:/i.test(a.getAttribute('href') || ''));
  } finally { e.close(); }
});

test('safe Markdown formatting, tables, links and math text survive sanitization', () => {
  const e = environment('<div id="chat-messages"></div>'); const { w } = e;
  try {
    loadChat(w);
    w.__renderBot('**Importante**\n\n- Uno\n- Dos\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n[guía](https://example.org/)\n\n$x^2$');
    const bubble=w.document.querySelector('.mensaje-asistente');
    assert.equal(bubble.querySelector('strong').textContent,'Importante');
    assert.equal(bubble.querySelectorAll('li').length,2);
    assert.equal(bubble.querySelectorAll('td').length,2);
    assert.equal(bubble.querySelector('a').href,'https://example.org/');
    assert.ok(bubble.textContent.includes('$x^2$'));
  } finally { e.close(); }
});

for(const missing of ['sanitizer','parser']) test(`missing ${missing} falls back to literal text`, () => {
  const e = environment('<div id="chat-messages"></div>'); const { w } = e;
  try {
    loadChat(w,missing!=='sanitizer',missing!=='parser'); w.__renderBot(payload);
    const bubble=w.document.querySelector('.mensaje-asistente');
    assert.equal(bubble.textContent,payload); noPayloadExecution(w,bubble);
  } finally { e.close(); }
});

test('chart titles from model responses use text nodes', () => {
  const e = environment('<div id="chart"></div>'); const { w } = e;
  try {
    loadChat(w); w.HTMLCanvasElement.prototype.getContext = () => ({}); w.Chart = function(){};
    const chart=w.document.getElementById('chart');
    w.__renderChart(chart,{title:payload,type:'pie',labels:['Synthetic'],data:[1]});
    assert.ok(chart.textContent.includes(payload)); noPayloadExecution(w,chart);
  } finally { e.close(); }
});

test('KaTeX still renders formulas and refuses untrusted hyperlink commands', () => {
  const e = environment('<div id="chat-messages"></div>'); const { w } = e;
  try {
    w.eval(source('apps/chatbot/static/chatbot/vendor/katex/katex.min.js'));
    w.eval(source('apps/chatbot/static/chatbot/vendor/katex/auto-render.min.js'));
    loadChat(w);
    w.__renderBot('$x^2$ and $\\href{javascript:alert(1)}{x}$');
    const bubble = w.document.querySelector('.mensaje-asistente');
    assert.ok(bubble.querySelector('.katex'));
    noPayloadExecution(w,bubble);
  } finally { e.close(); }
});

test('import mapping table keeps malicious column names as literal text', () => {
  const e = environment('<table><tbody id="savMappingTbody"></tbody></table>'); const { w } = e;
  try {
    w.eval(source('static/js/global/sav_importer.js') +
      '\nwindow.__setMappings = items => { currentColumnMappings = items; };');
    w.__mappings = [{spss_column:payload, corrected_name:payload, has_correction:true,
      correction_detail:payload, destination_module:payload, destination_field:payload}];
    w.__setMappings(w.__mappings); w.renderMappingTable();
    const table = w.document.getElementById('savMappingTbody');
    assert.ok(table.textContent.includes(payload)); noPayloadExecution(w,table);
  } finally { e.close(); }
});


test('A04 uses real visit IDs and never manufactures history from a patient ID', () => {
  const { w, close } = environment();
  try {
    w.eval(source('apps/clinical/static/clinical/js/pacientes.js'));
    const patient = { id: '6101', codigo: '800000', historiales: [] };
    assert.equal(w.obtenerHistorialesPaciente(patient).length, 0);
    assert.equal(patient.historiales.length, 0);
    patient.historiales = [{ id: '9101', fechaVisita: '2026-01-01' }];
    assert.equal(w.obtenerUltimoHistorial(patient).id, '9101');
  } finally { close(); }
});
