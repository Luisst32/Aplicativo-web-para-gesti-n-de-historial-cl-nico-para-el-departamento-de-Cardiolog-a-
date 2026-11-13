/* Recorded values only. All labels and database values are rendered as text. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const node = byId('questionnaire-dashboard-data');
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const records = data.records || [];
  const fields = data.fields || [];
  let selectedVisit = '';
  let selectedSection = '';
  let selected = records;
  const fold = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  const text = (tag, value, cls) => {
    const el = document.createElement(tag); el.textContent = value;
    if (cls) el.className = cls;
    return el;
  };
  const number = value => new Intl.NumberFormat('es-EC', { maximumFractionDigits: 2 }).format(value);
  const present = value => value !== undefined && value !== null && value !== '';
  const sections = [...new Set(fields.map(f => f.section))];

  function stats(field, rows = selected) {
    const values = rows.map(r => r.values[field.id]).filter(present);
    const categories = new Map();
    values.forEach(value => categories.set(String(value), (categories.get(String(value)) || 0) + 1));
    return { values, categories, recorded: values.length, missing: rows.length - values.length };
  }

  function populateSelect(id, values) {
    const select = byId(id);
    [...new Set(values.filter(present))].sort((a,b) => String(a).localeCompare(String(b), 'es', { numeric: true })).forEach(value => {
      const option = text('option', value); option.value = value; select.append(option);
    });
    select.addEventListener('change', render);
  }

  function renderCodes() {
    const target = byId('qd-code-options'); target.replaceChildren();
    const search = fold(byId('qd-code-search').value);
    const matches = [...records].sort((a,b) => a.code.localeCompare(b.code, 'es', { numeric: true }))
      .filter(r => fold(r.code + ' ' + r.institution).includes(search));
    for (const row of matches) {
      const button = text('button', `${row.code || 'Sin número registrado'} · ${row.institution} · ${row.year}`);
      button.type = 'button'; button.setAttribute('aria-pressed', String(String(row.id) === selectedVisit));
      button.addEventListener('click', () => {
        selectedVisit = String(row.id);
        byId('qd-code-selection').textContent = `N.° Ficha Clínica ${row.code} · ${row.institution} · ${row.year}`;
        renderCodes(); render();
      });
      target.append(button);
    }
    if (!matches.length) target.append(text('p', 'No hay fichas que coincidan con la búsqueda.', 'qd-muted'));
  }

  function renderPriority() {
    const target = byId('qd-priorities'); target.replaceChildren();
    for (const [id,label] of [['covid_paso','Ha pasado el COVID-19'],['r_apnea','Apnea del sueño'],['r_disfunc','Disfunción eréctil'],['r_irc','Insuficiencia renal crónica']]) {
      const field = fields.find(f => f.id === id);
      const s = stats(field || {id});
      const yes = s.categories.get('Sí') || 0;
      const no = s.categories.get('No') || 0;
      const valid = yes + no;
      const card = text('article', '', 'qd-priority');
      card.append(text('h2', label), text('strong', valid ? `${yes}` : 'Sin datos'));
      card.append(text('p', valid ? `${yes} sí · ${no} no · ${number(yes / valid * 100)} % afirmativo` : 'Sin respuestas válidas registradas'));
      card.append(text('small', `${selected.length - valid} sin respuesta válida de ${selected.length} fichas`));
      target.append(card);
    }
  }

  function renderCard(field) {
    const s = stats(field);
    const card = text('article', '', 'qd-card');
    card.append(text('h3', field.label));
    card.append(text('p', `${s.recorded} con dato · ${s.missing} sin dato · ${selected.length} fichas`, 'qd-coverage'));
    if (!s.recorded) {
      card.append(text('p', 'Sin datos registrados en la selección.', 'qd-muted'));
    } else if (field.kind === 'number') {
      const values = s.values.filter(v => typeof v === 'number' && Number.isFinite(v));
      if (values.length) {
        const sum = values.reduce((a,b) => a+b,0);
        // No spread of an unbounded array into Math.min/max.
        const minimum = values.reduce((a,b) => Math.min(a,b));
        const maximum = values.reduce((a,b) => Math.max(a,b));
        card.append(text('p', `Media ${number(sum / values.length)} · Mínimo ${number(minimum)} · Máximo ${number(maximum)}`, 'qd-metric'));
      }
    } else if (field.kind === 'text') {
      card.append(text('p', 'Contenido libre registrado. Se muestra su cobertura.', 'qd-muted'));
    } else {
      const list = text('div', '', 'qd-distribution');
      [...s.categories].sort((a,b) => b[1] - a[1]).forEach(([value,count]) => {
        const row = text('div', '', 'qd-category');
        row.append(text('span', value), text('strong', `${count} (${number(count / s.recorded * 100)} %)`));
        const bar = document.createElement('meter'); bar.min=0; bar.max=s.recorded; bar.value=count;
        bar.setAttribute('aria-label', `${value}: ${count} de ${s.recorded}`); row.append(bar); list.append(row);
      });
      card.append(list);
    }
    return card;
  }

  function render() {
    selected = records.filter(r => (!selectedVisit || String(r.id) === selectedVisit)
      && (!byId('qd-institution').value || r.institution === byId('qd-institution').value)
      && (!byId('qd-year').value || String(r.year) === byId('qd-year').value)
      && (!byId('qd-sex').value || r.sex === byId('qd-sex').value));
    byId('qd-total').textContent = selected.length;
    byId('qd-universe').textContent = `de ${records.length} fichas registradas`;
    renderPriority();
    const search = fold(byId('qd-field-search').value);
    const onlyRecorded = byId('qd-only-recorded').checked;
    const target = byId('qd-content'); target.replaceChildren();
    const nav = byId('qd-sections'); nav.replaceChildren();
    const all = text('button', 'Todas las secciones'); all.type='button';
    all.setAttribute('aria-pressed', String(!selectedSection)); all.addEventListener('click',()=>{selectedSection='';render();}); nav.append(all);
    let visibleFields = 0;
    for (const section of sections) {
      const button = text('button', section); button.type='button'; button.setAttribute('aria-pressed',String(section===selectedSection));
      button.addEventListener('click',()=>{selectedSection=section;render();}); nav.append(button);
      if (selectedSection && selectedSection !== section) continue;
      const matches = fields.filter(f=>f.section===section && fold(f.label+' '+section).includes(search)
        && (!onlyRecorded || stats(f).recorded));
      if (!matches.length) continue;
      const block = text('section', '', 'qd-section'); block.append(text('h2',section));
      const grid = text('div','','qd-grid'); matches.forEach(f=>grid.append(renderCard(f))); block.append(grid);target.append(block);
      visibleFields += matches.length;
    }
    byId('qd-status').textContent = selected.length ? `${visibleFields} campos · ${selected.length} fichas en la selección` : 'No hay fichas para la combinación de filtros seleccionada.';
  }

  populateSelect('qd-institution', records.map(r=>r.institution));
  populateSelect('qd-year', records.map(r=>r.year));
  populateSelect('qd-sex', records.map(r=>r.sex));
  byId('qd-code-search').addEventListener('input',renderCodes);
  byId('qd-field-search').addEventListener('input',render);
  byId('qd-only-recorded').addEventListener('change',render);
  byId('qd-code-clear').addEventListener('click',()=>{
    selectedVisit='';byId('qd-code-selection').textContent='Todas las fichas';renderCodes();render();
  });
  byId('qd-reset').addEventListener('click',()=>{
    selectedVisit='';selectedSection='';
    ['qd-code-search','qd-field-search','qd-institution','qd-year','qd-sex'].forEach(id=>{byId(id).value='';});
    byId('qd-only-recorded').checked=false;byId('qd-code-selection').textContent='Todas las fichas';renderCodes();render();
  });
  byId('qd-export').addEventListener('click',()=>{
    const rows=[['Sección','Campo','Con dato','Sin dato','Respuesta o estadística','Cantidad']];
    for (const field of fields) {
      const s=stats(field); const base=[field.section,field.label,s.recorded,s.missing];
      if (field.kind==='text' || !s.recorded) rows.push([...base,'Cobertura',s.recorded]);
      else if (field.kind==='number') rows.push([...base,'Media',s.values.reduce((a,b)=>a+b,0)/s.recorded]);
      else for (const [value,count] of s.categories) rows.push([...base,value,count]);
    }
    // Prevent formula execution in spreadsheet consumers, including stored option labels.
    const csv=rows.map(row=>row.map(value=>{let v=String(value??'');if (/^[=+@\-\t\r]/.test(v)) v="'"+v;return '"'+v.replace(/"/g,'""')+'"';}).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='CardioUNEMI_Cuestionario_2026.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  byId('qd-print')?.addEventListener('click',()=>window.print());
  byId('qd-ppt')?.addEventListener('click',async()=>{
    if (!window.PptxGenJS) {
      byId('qd-status').textContent='No se pudo cargar la exportación PowerPoint. Recarga la página e inténtalo de nuevo.';
      return;
    }
    const button=byId('qd-ppt');button.disabled=true;
    try {
      const ppt=new window.PptxGenJS();ppt.layout='LAYOUT_WIDE';ppt.author='CardioUNEMI';ppt.subject='Cuestionario UNEMI 2026';
      for (const section of sections) {
        const entries=fields.filter(f=>f.section===section);
        for (let offset=0;offset<entries.length;offset+=7) {
          const slide=ppt.addSlide();slide.background={color:'F8FBFD'};
          slide.addText(section,{x:.5,y:.35,w:12.3,h:.6,fontSize:22,bold:true,color:'173854'});
          slide.addText(`${selected.length} fichas seleccionadas · Cuestionario UNEMI 2026`,{x:.5,y:1,w:12,h:.35,fontSize:11,color:'526478'});
          const rows=entries.slice(offset,offset+7).map(field=>{
            const s=stats(field);
            let value='Sin datos';
            if (s.recorded && field.kind==='number') value=`Media ${number(s.values.reduce((a,b)=>a+b,0)/s.recorded)}`;
            else if (s.recorded && field.kind==='text') value='Texto registrado (contenido reservado)';
            else if (s.recorded) value=[...s.categories].map(([v,n])=>`${v}: ${n}`).join('; ');
            return [field.label,`${s.recorded} con dato / ${s.missing} sin dato`,value];
          });
          slide.addTable([['Campo','Cobertura','Resultado'],...rows],{x:.5,y:1.6,w:12.3,h:4.8,border:{type:'solid',color:'DCE5EE',pt:.5},fontSize:11,color:'183047',fill:'FFFFFF',margin:.1,colW:[4.7,2.4,5.2],autoPage:true,autoPageRepeatHeader:true});
        }
      }
      await ppt.writeFile({fileName:'CardioUNEMI_Cuestionario_2026.pptx'});
    } catch (error) {
      byId('qd-status').textContent='No se pudo generar el PowerPoint. Puedes exportar el resumen CSV.';
    } finally {button.disabled=false;}
  });
  renderCodes();render();
})();
