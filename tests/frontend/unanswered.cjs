const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
function setup(){
 const dom=new JSDOM(`<form id="ehrCleanForm"><div><label><input type="radio" name="nc_asma" value="Si">Si</label><label><input type="radio" name="nc_asma" value="No">No</label></div><label><input type="checkbox" name="cancer_colon" value="1">Colon</label></form>`,{runScripts:'outside-only'});
 const w=dom.window;
 let code=fs.readFileSync(path.join(root,'apps/clinical/static/clinical/js/form.js'),'utf8');
 // Avoid page navigation/network bootstrapping in these focused DOM tests.
 code=code.replace("document.addEventListener('DOMContentLoaded', async () => {","document.addEventListener('never-bootstrap', async () => {");
 w.eval(code); w.inicializarRespuestasVacias();
 return w;
}
test('initial controls serialize NULL, explicit No stays No',()=>{
 const w=setup(), form=w.document.querySelector('form');
 let data=new w.FormData(form);w.serializarRespuestasVacias(form,data);
 assert.equal(data.get('nc_asma'),'');assert.equal(data.get('cancer_colon'),'');
 form.querySelector('[value="No"]').checked=true;
 const select=form.querySelector('select');select.value='0';select.dispatchEvent(new w.Event('change'));
 data=new w.FormData(form);w.serializarRespuestasVacias(form,data);
 assert.equal(data.get('nc_asma'),'No');assert.equal(data.get('cancer_colon'),'0');
});
test('restoring NULL clears previous patient answers',()=>{
 const w=setup(),form=w.document.querySelector('form');
 for(const name of ['calcIMC','calcPredimed','actualizarHeroPresion','aplicarProteccionPrivacidadFormulario'])w[name]=()=>{};
 w.restaurarFichaDesdeObjeto({nc_asma:'Si',cancer_colon:'1'});
 assert.equal(form.querySelector('[value="Si"]').checked,true);
 w.restaurarFichaDesdeObjeto({nc_asma:null,cancer_colon:null});
 const data=new w.FormData(form);w.serializarRespuestasVacias(form,data);
 assert.equal(data.get('nc_asma'),'');assert.equal(data.get('cancer_colon'),'');
});
test('statistics use answered denominator and keep missing separate',()=>{
 const w=setup();w.eval(fs.readFileSync(path.join(root,'apps/dashboard/static/dashboard/js/core/dashboard-core.js'),'utf8').replace('const charts =','var charts =').replace('const PALETTE =','var PALETTE =').replace('let filteredRecords =','var filteredRecords =').replaceAll('initDashboard();','void 0;').replace("document.addEventListener('DOMContentLoaded', initDashboard)","document.addEventListener('never-bootstrap', initDashboard)"));
 const c=w.threeStateCounts('flag',[{flag:true},{flag:false},{flag:null},{}]);
 assert.equal(c.yes,1);assert.equal(c.no,1);assert.equal(c.missing,2);assert.equal(c.answered,2);
});

test('null icon clears explicit radio and checkbox answers without submitting',()=>{
 const w=setup(),form=w.document.querySelector('form');
 form.querySelector('[value="Si"]').checked=true;
 const select=form.querySelector('select');select.value='1';select.dispatchEvent(new w.Event('change'));
 let submits=0;form.addEventListener('submit',e=>{e.preventDefault();submits++;});
 for(const name of ['nc_asma','cancer_colon']) {
   const button=form.querySelector(`[data-clear-answer="${name}"]`);
   assert.equal(button.type,'button');button.click();
 }
 const data=new w.FormData(form);w.serializarRespuestasVacias(form,data);
 assert.equal(data.get('nc_asma'),'');assert.equal(data.get('cancer_colon'),'');
 assert.equal(submits,0);
 w.inicializarRespuestasVacias();
 assert.equal(form.querySelectorAll('[data-clear-answer]').length,2);
});

test('three reported charts stay empty for an unanswered patient and recover after filtering',()=>{
 const w=setup();
 w.document.body.innerHTML='<div><canvas id="chart-mod-predimed"></canvas></div><div><canvas id="chart-fam-carga-global"></canvas></div><div><div id="chart-nc-comorbilidades"></div></div>';
 w.eval(fs.readFileSync(path.join(root,'apps/dashboard/static/dashboard/js/core/dashboard-core.js'),'utf8').replace('const charts =','var charts =').replace('const PALETTE =','var PALETTE =').replace('let filteredRecords =','var filteredRecords =').replaceAll('initDashboard();','void 0;').replace("document.addEventListener('DOMContentLoaded', initDashboard)","document.addEventListener('never-bootstrap', initDashboard)"));
 for(const file of ['factores-modificables','antecedentes-familiares','historia-no-cardio'])w.eval(fs.readFileSync(path.join(root,'apps/dashboard/static/dashboard/js/sections',file+'.js'),'utf8'));
 let created=0,destroyed=0;
 w.createDashboardChart=(el,config)=>{created++;return {data:config.data,options:config.options,update(){},destroy(){destroyed++;}}};
 w.createDashboardApexChart=(el,config)=>{created++;w._lastComorb=config;return {render(){},updateOptions(config){w._lastComorb=config;},destroy(){destroyed++;}}};
 const row=values=>new Proxy(values,{get:(obj,key)=>key in obj?obj[key]:''});
 function render(values){w._testRows=[row(values)];w.eval('filteredRecords = window._testRows');w.renderTabFactoresModificables();w.renderTabAntecedentesFamiliares();w.renderTabHistoriaNoCardio();}
 const missing={respiratorio_desc:'Sin dato',salud_mental_desc:'Sin dato',predimed_adherencia:null};
 render(missing);assert.equal(created,0);
 for(const id of ['chart-mod-predimed','chart-fam-carga-global','chart-nc-comorbilidades']){assert.equal(w.document.getElementById(id).hidden,true);assert.equal(w.document.querySelector(`[data-empty-chart="${id}"]`).hidden,false);}
 render({...missing,predimed_adherencia:'Buena Adherencia',ant_fam_hta:false,ant_fam_dm:false,ant_fam_dlp:false,ant_fam_cv_mayor:false,asma:true});assert.equal(created,3);
 render({...missing,cancer:true});
 assert.equal(w._lastComorb.series[0].data[0],0);assert.equal(w._lastComorb.series[0].data[1],0);assert.equal(w._lastComorb.series[0].data[4],1);
 render(missing);assert.equal(destroyed,3);
});

test('every clinical radio group has a NULL button and family selectors start at Seleccionar',()=>{
 const w=setup();
 const modules=path.join(root,'apps/clinical/templates/clinical/modules');
 w.document.body.innerHTML='<form id="ehrCleanForm">'+fs.readdirSync(modules).filter(f=>f.endsWith('.html')).map(f=>fs.readFileSync(path.join(modules,f),'utf8')).join('')+'</form>';
 const form=w.document.querySelector('form');
 w.inicializarRespuestasVacias();
 const names=new Set([...form.querySelectorAll('input[type="radio"]')].map(r=>r.name));
 for(const name of names){
   assert.ok([...form.querySelectorAll('[data-clear-answer]')].some(b=>b.dataset.clearAnswer===name),name);
   assert.equal([...form.elements[name]].find(r=>r.checked).value,'',name);
 }
 for(const name of ['ant_padre_hta','ant_padre_dm','ant_padre_dislip','ant_madre_hta','ant_madre_dm','ant_madre_dislip']){
   const input=form.elements[name];
   assert.equal(input._answerSelect.value,'');
   assert.equal(input._answerSelect.options[0].textContent,'Seleccionar');
 }
 const radio=form.querySelector('[name="res_fsvi"][value="Normal"]');radio.checked=true;
 [...form.querySelectorAll('[data-clear-answer]')].find(b=>b.dataset.clearAnswer==='res_fsvi').click();
 const data=new w.FormData(form);w.serializarRespuestasVacias(form,data);
 assert.equal(data.get('res_fsvi'),'');
});
test('universal value label style, forest plot 2-line formatting and non-overlapping markers', () => {
  const w = setup();
  w.eval(fs.readFileSync(path.join(root, 'apps/dashboard/static/dashboard/js/core/chart-style.js'), 'utf8'));
  assert.equal(w.UNIVERSAL_VALUE_LABEL_STYLE.color, '#ffffff');
  assert.equal(w.UNIVERSAL_VALUE_LABEL_STYLE.fontWeight, 'bold');
  assert.equal(w.UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow.enabled, true);

  const twoLines = ['21 de 55 · 38,2%', 'IC 95%: 26,5–51,4%'];
  assert.deepEqual(w.dashboardLabelLines(twoLines), twoLines);
  assert.deepEqual(w.dashboardVerticalLabel(twoLines), twoLines);
  assert.equal(w.dashboardLabelLines('21 de 55 · 38,2%'), '21 de 55 · 38,2%');

  const svg = w.document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const group = w.document.createElementNS('http://www.w3.org/2000/svg', 'g');
  group.setAttribute('class', 'apexcharts-bar-goals-groups');
  const line = w.document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', '100');
  line.setAttribute('y1', '40');
  line.setAttribute('x2', '100');
  line.setAttribute('y2', '80');
  group.appendChild(line);
  svg.appendChild(group);
  w.document.body.appendChild(svg);

  w.redesignForestPlotGoals(svg);
  assert.equal(line.getAttribute('data-redesigned'), 'true');
  assert.equal(line.getAttribute('y1'), '33');
  assert.equal(line.getAttribute('y2'), '40');
  const bottomTick = group.querySelector('.forest-goal-bottom-tick');
  assert.ok(bottomTick);
  assert.equal(bottomTick.getAttribute('y1'), '80');
  assert.equal(bottomTick.getAttribute('y2'), '87');
  const diamond = group.querySelector('.forest-goal-diamond');
  assert.ok(diamond);
  assert.equal(diamond.getAttribute('fill'), '#0f172a');
});
