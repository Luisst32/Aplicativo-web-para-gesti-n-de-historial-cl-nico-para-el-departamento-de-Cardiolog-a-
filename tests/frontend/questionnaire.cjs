const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
const source=file=>fs.readFileSync(path.join(root,file),'utf8');

function dashboard() {
  const ids=['qd-code-search','qd-field-search','qd-only-recorded','qd-export','qd-reset','qd-code-clear','qd-code-selection','qd-code-options','qd-total','qd-universe','qd-priorities','qd-sections','qd-content','qd-status'];
  const body=ids.map(id=>id.includes('search')?`<input id="${id}">`:id==='qd-only-recorded'?`<input type="checkbox" id="${id}">`:`<div id="${id}"></div>`).join('')+
    ['qd-institution','qd-year','qd-sex'].map(id=>`<select id="${id}"><option value="">Todos</option></select>`).join('');
  const dom=new JSDOM(body,{runScripts:'dangerously',url:'https://clinic.example/dashboard/'});
  const w=dom.window;
  const fields=[{id:'covid_paso',label:'Ha pasado el COVID-19',section:'COVID-19',kind:'boolean'},
    {id:'r_apnea',label:'Apnea del sueño',section:'Factores de riesgo',kind:'boolean'},
    {id:'db:laboratory.glucose_mg_dl',label:'Glucosa',section:'Laboratorio',kind:'number'},
    {id:'details',label:'Detalle registrado',section:'COVID-19',kind:'text'},
    {id:'r_disfunc',label:'Disfunción eréctil',section:'Factores de riesgo',kind:'boolean'},
    {id:'r_irc',label:'Insuficiencia renal crónica',section:'Factores de riesgo',kind:'boolean'}];
  const records=[{id:101,code:'001',institution:'Institución A',year:2026,sex:'Hombre',values:{covid_paso:'Sí',r_apnea:'No','db:laboratory.glucose_mg_dl':0,details:true}},
    {id:202,code:'001',institution:'Institución B',year:2025,sex:'Mujer',values:{covid_paso:'No',r_apnea:'Sí','db:laboratory.glucose_mg_dl':100}},
    {id:303,code:'<img src=x onerror="window.__xss=1">',institution:'Institución A',year:2026,sex:'Hombre',values:{}}];
  const node=w.document.createElement('script');node.id='questionnaire-dashboard-data';node.type='application/json';node.textContent=JSON.stringify({fields,records});w.document.body.append(node);
  w.eval(source('apps/dashboard/static/dashboard/js/questionnaire.js'));
  return {w,close:()=>w.close()};
}

test('questionnaire counts missing separately and keeps zero in numeric means',()=>{
  const {w,close}=dashboard();try {
    assert.equal(w.document.getElementById('qd-total').textContent,'3');
    const priorities=w.document.getElementById('qd-priorities').textContent;
    assert.ok(priorities.includes('1 sí · 1 no · 50 % afirmativo'));
    assert.ok(priorities.includes('Sin respuestas válidas registradas'));
    const cards=w.document.getElementById('qd-content').textContent;
    assert.ok(cards.includes('Media 50 · Mínimo 0 · Máximo 100'));
    assert.ok(cards.includes('Contenido libre registrado'));
    assert.equal(w.document.querySelectorAll('img').length,0);
    assert.equal(w.__xss,undefined);
  }finally{close();}
});

test('all registered codes searchable and duplicate numbers select exact visit',()=>{
  const {w,close}=dashboard();try {
    const search=w.document.getElementById('qd-code-search');search.value='001';search.dispatchEvent(new w.Event('input'));
    const options=w.document.querySelectorAll('#qd-code-options button');assert.equal(options.length,2);
    options[1].click();assert.equal(w.document.getElementById('qd-total').textContent,'1');
    assert.ok(w.document.getElementById('qd-code-selection').textContent.includes('Institución B'));
    assert.ok(w.document.getElementById('qd-priorities').textContent.includes('0 sí · 1 no'));
    w.document.getElementById('qd-reset').click();assert.equal(w.document.querySelectorAll('#qd-code-options button').length,3);
    assert.equal(w.document.getElementById('qd-total').textContent,'3');
  }finally{close();}
});

test('field search, section and institution filters work together',()=>{
  const {w,close}=dashboard();try {
    const search=w.document.getElementById('qd-field-search');search.value='glucosa';search.dispatchEvent(new w.Event('input'));
    assert.equal(w.document.querySelectorAll('.qd-card').length,1);
    const select=w.document.getElementById('qd-institution');select.value='Institución B';select.dispatchEvent(new w.Event('change'));
    assert.ok(w.document.getElementById('qd-content').textContent.includes('Media 100'));
  }finally{close();}
});

function formEnvironment() {
  const ids=['f_nombre','f_apellido1','f_apellido2','f_cedula','f_correo','f_telefono','f_codigo'];
  const dom=new JSDOM('<form id="ehrCleanForm">'+ids.map(id=>`<input id="${id}" name="${id}"${id==='f_correo'?' type="email"':''}>`).join('')+'</form><div id="heroNombre"></div><div id="heroAvatar"></div>',{runScripts:'dangerously',url:'https://clinic.example/clinical/formulario/?paciente=101'});
  const w=dom.window;
  w.document.addEventListener=()=>{};
  let privateMode=true;
  w.esModoPrivacidadActivo=()=>privateMode;
  w.alert=()=>{};
  w.eval(source('apps/clinical/static/clinical/js/form.js')+'\nwindow.__setPatient = p => {pacienteActual=p;};');
  w.eval('calcIMC=()=>{};calcPredimed=()=>{};actualizarHeroPresion=()=>{};');
  const exact={f_nombre:'María José',f_apellido1:'De la Cruz',f_apellido2:'O\'Connor',f_cedula:'SYNTHETIC-ID',f_correo:'synthetic@example.invalid',f_telefono:'SYNTHETIC-PHONE',f_codigo:'001'};
  w.__setPatient({id:101,codigo:'001',nombre:'María José De la Cruz O\'Connor'});
  return {w,exact,toggle:value=>{privateMode=value;w.dispatchEvent(new w.Event('cardio_privacy_mode_changed'));},close:()=>w.close()};
}

test('form privacy masks server restored identity, retains ficha and restores exact surnames',()=>{
  const {w,exact,toggle,close}=formEnvironment();try {
    w.restaurarFichaDesdeObjeto(exact);
    for(const id of Object.keys(exact).filter(id=>id!=='f_codigo')){
      assert.equal(w.document.getElementById(id).value,'******');assert.equal(w.document.getElementById(id).readOnly,true);
    }
    assert.equal(w.document.getElementById('f_codigo').value,'001');
    assert.ok(!w.document.getElementById('heroNombre').textContent.includes('María'));
    toggle(false);
    for(const [id,value] of Object.entries(exact)) assert.equal(w.document.getElementById(id).value,value);
    assert.equal(w.document.getElementById('f_correo').type,'email');
    toggle(true);toggle(false);
    assert.equal(w.document.getElementById('f_apellido1').value,'De la Cruz');
  }finally{close();}
});

test('saving with privacy omits masked identity instead of overwriting stored patient',async()=>{
  const {w,exact,close}=formEnvironment();try {
    w.restaurarFichaDesdeObjeto(exact);let sent;
    w.fetch=async(url,options)=>{sent=options.body;return {ok:false,json:async()=>({success:false,error:'synthetic'})};};
    await w.guardarFichaCompleta();
    for(const id of Object.keys(exact).filter(id=>id!=='f_codigo'))assert.equal(sent.has(id),false);
    assert.equal(sent.get('idPaciente'),'101');assert.equal(sent.get('f_codigo'),'001');
  }finally{close();}
});

test('patient pagination is 20 and privacy adds no protected-by-privacy message',()=>{
  const code=source('apps/clinical/static/clinical/js/list.js');
  assert.match(code,/PACIENTES_POR_PAGINA = 20/);assert.ok(code.includes('(20 por pág.)'));
  assert.ok(!/protegido por privacidad/i.test(code));
});

test('patient list actually renders 20 rows then the remaining row',()=>{
  const dom=new JSDOM('<table><tbody id="pacientesTbody"></tbody></table><div id="tablaVaciaMensaje"></div><div id="paginacionBar"><div id="paginacionResumen"></div><div id="paginacionNumeros"></div></div>',{runScripts:'dangerously',url:'https://clinic.example/clinical/listado/'});
  const w=dom.window;
  try {
    w.document.addEventListener=()=>{};w.scrollTo=()=>{};
    w.eval(source('apps/clinical/static/clinical/js/pacientes.js'));
    w.eval(source('apps/clinical/static/clinical/js/list.js'));
    w.eval(`obtenerPacientesFiltrados=()=>Array.from({length:21},(_,i)=>({id:String(i)}));
      actualizarIconosOrdenCabeceras=()=>{};actualizarStatsCards=()=>{};actualizarEstadoSeleccion=()=>{};
      crearFilaPaciente=p=>{const row=document.createElement('tr');row.textContent=p.id;return row;};`);
    w.renderPacientesTabla();
    assert.equal(w.document.querySelectorAll('#pacientesTbody tr').length,20);
    assert.ok(w.document.getElementById('paginacionResumen').textContent.includes('1-20 de 21'));
    w.cambiarPagina(2);
    assert.equal(w.document.querySelectorAll('#pacientesTbody tr').length,1);
    assert.ok(w.document.getElementById('paginacionResumen').textContent.includes('21-21 de 21'));
  } finally {w.close();}
});
