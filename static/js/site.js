
// Discourage casual media saving while keeping navigation and case-map controls usable.
(function(){
  var media = '.clip img,.fig img,.rv-card img,.pipeline,#rv-map';
  function protectedMedia(node){
    if (!node) return false;
    var element = node.nodeType===1 ? node : node.parentElement;
    return !!(element && element.closest && element.closest(media));
  }
  ['contextmenu','dragstart'].forEach(function(type){
    document.addEventListener(type, function(ev){
      if (protectedMedia(ev.target)) ev.preventDefault();
    }, true);
  });
  document.addEventListener('copy', function(ev){
    var selection = window.getSelection();
    if (protectedMedia(ev.target) || protectedMedia(document.activeElement) ||
        (selection && (protectedMedia(selection.anchorNode) || protectedMedia(selection.focusNode))))
      ev.preventDefault();
  }, true);
})();
function tabs(group, id){document.querySelectorAll('[data-group="'+group+'"]').forEach(function(e){var on=e.dataset.id===id;e.classList.toggle('on',on);if(e.tagName==='BUTTON')e.setAttribute('aria-pressed',String(on));});}
(function(){
  var OUT = {'collision':'#d03b3b','near-collision':'#ec835a','normal':'#0ca30c'};
  var FAMC = {'PED-TURNBACK':'#2a78d6','PED-OCCLUDED':'#eb6834','CUT-IN':'#1baf7a','BRAKE-CHAIN':'#eda100','NARROW-CONFLICT':'#e87ba4','STAGED-ACCIDENT':'#7c3aed'};
  var MAPN = {'Sai_Kung':'Sai Kung','Tuen_Mun':'Tuen Mun','HKPC':'HKPC'};
  var D = null, st = {map:'Sai_Kung', colour:'outcome', pick:null, cell:null}, vb = null;
  function el(id){return document.getElementById(id);}
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function colour(c){return st.colour==='family' ? (FAMC[c.family]||'#666') : (OUT[st.colour==='ads'?c.ads:c.outcome]||'#666');}
  function shown(c){ if(!st.cell) return true; return c.family===st.cell[0] && (st.colour==='ads'?c.ads:c.outcome)===st.cell[1]; }
  function setVb(v){vb=v; el('rv-map').setAttribute('viewBox', v.join(' '));}
  function drawMap(){
    var m = D.maps[st.map], b = m.bounds, pad = 25;
    setVb([b[0]-pad, -b[3]-pad, b[2]-b[0]+2*pad, b[3]-b[1]+2*pad]);
    el('rv-roads').innerHTML = '<path class="walk" d="'+m.walks+'"/><path class="road" d="'+m.surface+'"/><path class="centre" d="'+m.centre+'"/>';
    drawMarks();
  }
  function drawMarks(){
    var r = Math.max(2.5, (vb[2])/140), cs = D.cases.filter(function(c){return c.map===st.map;});
    cs.sort(function(a,b){return (shown(a)-shown(b)) || ((a.no===st.pick)-(b.no===st.pick));});
    el('rv-marks').innerHTML = cs.map(function(c){
      return '<circle class="mk'+(shown(c)?'':' dim')+(c.no===st.pick?' sel':'')+'" data-no="'+c.no+'" cx="'+c.x+'" cy="'+(-c.y)+'" r="'+r+'" fill="'+colour(c)+'"><title>'+e(c.no+' '+c.title)+'</title></circle>';
    }).join('');
    var p = D.cases.find(function(c){return c.no===st.pick && c.map===st.map;}), h = '';
    if (p){
      if (p.ego_path) h += '<polyline class="egop" points="'+p.ego_path.map(function(q){return q[0]+','+(-q[1]);}).join(' ')+'"/>';
      if (p.partner_path) h += '<polyline class="parp" points="'+p.partner_path.map(function(q){return q[0]+','+(-q[1]);}).join(' ')+'"/>';
    }
    el('rv-paths').innerHTML = h;
  }
  function famName(k){var f = D.families.find(function(x){return x.key===k;}); return f ? f.name : k;}
  function card(){
    var c = D.cases.find(function(x){return x.no===st.pick;});
    if (!c){ el('rv-card').innerHTML = '<p>Click a case on the map, or a count in the table below.</p><p class="ci">'+D.cases.length+' cases of the earlier trial set on the three surveyed maps (Sai Kung, Tuen Mun, HKPC): six scenario families, each case placed where its critical moment happens.</p>'; return; }
    var num = function(v, u){return (v===null||v===undefined||v==='None') ? '-' : (Math.round(v*100)/100)+(u||'');};
    el('rv-card').innerHTML = (c.thumb ? '<img src="'+c.thumb+'" alt="" draggable="false">' : '') +
      '<h4>'+e(c.no+' | '+c.title)+'</h4><div><span class="pill">'+e(famName(c.family))+'</span><span class="pill">'+e(MAPN[c.map]+' '+c.corridor)+'</span></div>' +
      '<dl><dt>Human-like driver</dt><dd><span class="oc '+c.outcome+'">'+e(c.outcome)+'</span></dd>' +
      '<dt>Cautious ADS</dt><dd><span class="oc '+c.ads+'">'+e(c.ads)+'</span></dd>' +
      '<dt>Ego speed</dt><dd>'+num(c.ego_speed_kmh,' km/h')+'</dd><dt>Impact speed</dt><dd>'+num(c.impact,' m/s')+'</dd>' +
      '<dt>Min TTC / PET</dt><dd>'+num(c.ttc,' s')+' / '+num(c.pet,' s')+'</dd></dl>' +
      '<p>'+e(c.description)+'</p>' + (c.rules ? '<p class="ci"><b>Rule broken:</b> '+e(c.rules)+'</p>' : '') +
      (c.prompt ? '<p class="ci"><b>Request:</b> '+e(c.prompt)+'</p>' : '');
  }
  function matrix(){
    var key = st.colour==='ads' ? 'ads' : 'outcome', cols = ['collision','near-collision','normal'];
    var cs = D.cases.filter(function(c){return c.map===st.map;});
    var h = '<table><tr><th>'+MAPN[st.map]+': family</th>'+cols.map(function(o){return '<th>'+o+'</th>';}).join('')+'<th>all</th></tr>';
    D.families.forEach(function(f){
      var row = cs.filter(function(c){return c.family===f.key;});
      h += '<tr><td><i style="display:inline-block;width:.6rem;height:.6rem;border-radius:50%;background:'+(FAMC[f.key]||'#666')+'"></i> '+e(f.name)+'</td>';
      cols.forEach(function(o){
        var n = row.filter(function(c){return c[key]===o;}).length, on = st.cell && st.cell[0]===f.key && st.cell[1]===o;
        h += '<td class="n'+(on?' on':'')+'" data-f="'+f.key+'" data-o="'+o+'">'+(n||'')+'</td>';
      });
      h += '<td>'+row.length+'</td></tr>';
    });
    el('rv-matrix').innerHTML = h + '</table><div class="ci">Outcome of the '+(key==='ads'?'cautious ADS':'human-like')+' driver. Click a count to show only those cases; click it again to show all.</div>';
  }
  function legend(){
    var items = st.colour==='family' ? D.families.map(function(f){return [FAMC[f.key], f.name];}) : [[OUT['collision'],'collision'],[OUT['near-collision'],'near-collision'],[OUT['normal'],'no conflict']];
    el('rv-legend').innerHTML = items.map(function(i){return '<span><i style="background:'+i[0]+'"></i>'+e(i[1])+'</span>';}).join('');
  }
  function all(){ drawMap(); card(); matrix(); legend(); }
  function init(){
    fetch('static/data/review.json').then(function(r){return r.json();}).then(function(d){
      D = d; all();
      el('rv-mapsel').onchange = function(){ st.map = this.value; st.pick = null; st.cell = null; all(); };
      el('rv-colour').onchange = function(){ st.colour = this.value; st.cell = null; drawMarks(); matrix(); legend(); };
      el('rv-marks').addEventListener('click', function(ev){ var t = ev.target.closest('.mk'); if (!t) return; st.pick = t.dataset.no; drawMarks(); card(); });
      el('rv-matrix').addEventListener('click', function(ev){ var t = ev.target.closest('td.n'); if (!t) return;
        st.cell = (st.cell && st.cell[0]===t.dataset.f && st.cell[1]===t.dataset.o) ? null : [t.dataset.f, t.dataset.o]; drawMarks(); matrix(); });
      var svg = el('rv-map'), drag = null;
      svg.addEventListener('wheel', function(ev){ ev.preventDefault(); var f = ev.deltaY > 0 ? 1.15 : 1/1.15, r = svg.getBoundingClientRect();
        var px = vb[0] + (ev.clientX - r.left)/r.width*vb[2], py = vb[1] + (ev.clientY - r.top)/r.height*vb[3];
        setVb([px - (px - vb[0])*f, py - (py - vb[1])*f, vb[2]*f, vb[3]*f]); drawMarks(); }, {passive:false});
      svg.addEventListener('pointerdown', function(ev){ if (ev.target.closest('.mk')) return; drag = [ev.clientX, ev.clientY, vb.slice()]; svg.setPointerCapture(ev.pointerId); });
      svg.addEventListener('pointermove', function(ev){ if (!drag) return; var r = svg.getBoundingClientRect();
        setVb([drag[2][0] - (ev.clientX - drag[0])/r.width*vb[2], drag[2][1] - (ev.clientY - drag[1])/r.height*vb[3], vb[2], vb[3]]); });
      svg.addEventListener('pointerup', function(){ drag = null; });
      el('rv-fit').onclick = function(){ drawMap(); };
    }).catch(function(){ el('rv-card').innerHTML = '<p>The case data could not be loaded.</p>'; });
  }
  document.addEventListener('DOMContentLoaded', function(){
    if (el('rv-map')) init();
  });
})();
