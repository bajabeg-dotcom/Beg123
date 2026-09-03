"""Embedded web UI used when the optional static directory is missing."""

INDEX_HTML = r'''<!doctype html><html lang="bs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GM → RX DNA Studio</title><link rel="stylesheet" href="/styles.css"></head><body><header><small>KORG PA800 · FACTORY × GOLD DNA</small><h1>GM → RX DNA Studio</h1><p>GUI je ugrađen u aplikaciju, zato radi i bez static foldera.</p></header><main><section id="status" class="cards"></section><section class="panel"><div class="head"><h2>DNA baze</h2><button id="build">Obnovi DNA</button></div><div id="dna" class="cards"></div></section><section class="grid"><article class="panel"><h2>Mapping coverage</h2><div id="coverage"></div></article><article class="panel"><h2>Gold Performance DNA</h2><pre id="model"></pre></article></section><section class="panel"><h2>ChatGPT + Codex plan</h2><textarea id="goal">GM Voice convert to RX Sounds uz Factory ritmiku i Gold DNA način sviranja.</textarea><label><input id="online" type="checkbox"> OpenAI API</label><button id="plan">Generiši plan</button><div id="plans" class="grid"></div></section><section class="grid"><article class="panel"><h2>Factory import</h2><input id="factory" type="file" accept=".mid,.midi" multiple><button data-import="factory">Uvezi</button><pre id="factorylog"></pre></article><article class="panel"><h2>Gold import</h2><input id="gold" type="file" accept=".mid,.midi" multiple><button data-import="gold">Uvezi</button><pre id="goldlog"></pre></article></section><section class="panel accent"><h2>Optimizer</h2><input id="file" type="file" accept=".mid,.midi"><label>Gold jačina <input id="strength" type="range" min="0" max="100" value="70"><output id="amount">70%</output></label><button id="optimize">Konvertuj i preuzmi</button><pre id="report"></pre></section><section class="panel"><div class="head"><h2>Pa800 Test Agents</h2><div><button id="testsuite">Kreiraj test suite</button> <button id="testpack">Izvezi upute</button></div></div><p>Automatske provjere rade lokalno. Fizički playback i slušni A/B test nikad se ne označavaju kao završeni bez Pa800 rezultata.</p><div class="grid"><label>Case ID<input id="caseid" type="number" min="1"></label><label>Agent<select id="testagent"><option value="hardware_playback">Hardware Playback</option><option value="listening_review">Listening Review</option></select></label><label><input id="testpassed" type="checkbox"> Test prošao</label><label>Ocjena 1–5<input id="testrating" type="number" min="1" max="5" value="4"></label></div><textarea id="testcomments" placeholder="Pa800 OS/resources, audio chain i zapažanja"></textarea><button id="testresult">Sačuvaj fizički rezultat</button><pre id="testagents"></pre></section><section class="grid"><article class="panel"><h2>Pa800 RX katalog</h2><div id="catalog" class="table"></div></article><article class="panel"><h2>Aktivna mapiranja</h2><div id="mappings" class="table"></div></article></section><section class="panel"><h2>RX artikulacije</h2><div id="zones" class="table"></div></section></main><footer>Embedded UI · SysEx karantin · SHA-256 audit</footer><script src="/app.js"></script></body></html>'''

INDEX_HTML = INDEX_HTML.replace(
    '<article class="panel"><h2>Gold Performance DNA</h2><pre id="model"></pre></article></section>',
    '<article class="panel"><h2>Gold Performance DNA</h2><pre id="model"></pre></article>'
    '<article class="panel"><h2>Solo Instrument DNA</h2><p>Monofonija, fraze, legato, registri, bend, vibrato, expression i pressure.</p><pre id="solomodel"></pre></article></section>'
).replace(
    '<button id="optimize">Konvertuj i preuzmi</button>',
    '<label><input id="soloenabled" type="checkbox" checked> Aktiviraj detaljni Solo DNA</label>'
    '<label>Solo jačina <input id="solostrength" type="range" min="0" max="100" value="65"><output id="soloamount">65%</output></label>'
    '<label>Forsirani solo MIDI kanali (0–15, zarezom)<input id="solochannels" placeholder="npr. 0,1"></label>'
    '<button id="optimize">Konvertuj i preuzmi</button>'
)

INDEX_HTML = INDEX_HTML.replace(
    '<article class="panel"><h2>Pa800 Strumming DNA</h2><p>Guitar Mode komande, stroke alternacija, mute, strings, arpeggio, RX Noise, chord velocity i Humanize GTR.</p><pre id="strummodel"></pre></article></section>',
    '<article class="panel"><h2>Pa800 Strumming DNA</h2><p>Guitar Mode komande, stroke alternacija, mute, strings, arpeggio, RX Noise, chord velocity i Humanize GTR.</p><pre id="strummodel"></pre></article>'
    '<article class="panel"><h2>Song Layer DNA</h2><p>Poseban Delay track, optimizacija samo postojeće terce i Gold-only Ornament modeli.</p><pre id="songdna"></pre></article></section>'
).replace(
    '<button id="optimize">Konvertuj i preuzmi</button>',
    '<label><input id="delayenabled" type="checkbox" checked> Delay DNA</label>'
    '<label><input id="delaycreate" type="checkbox" disabled> Kreiranje missing Delay je zaključano — šest pjesama služi samo za identifikaciju</label>'
    '<label>Delay jačina <input id="delaystrength" type="range" min="0" max="100" value="80"><output id="delayamount">80%</output></label>'
    '<label><input id="harmonyenabled" type="checkbox" checked> Optimizuj samo postojeću tercu (velocity + CC7/CC11)</label>'
    '<label>Terca jačina <input id="harmonystrength" type="range" min="0" max="100" value="75"><output id="harmonyamount">75%</output></label>'
    '<label><input id="ornamentenabled" type="checkbox" checked> Gold-only Trill/Ornament optimizacija postojećih ukrasa</label>'
    '<label><input id="allowreplace" type="checkbox"> Dozvoli zamjenu samo dokazano manje važnog tracka</label>'
    '<button id="optimize">Konvertuj i preuzmi</button>'
)

INDEX_HTML = INDEX_HTML.replace(
    '<article class="panel"><h2>Solo Instrument DNA</h2><p>Monofonija, fraze, legato, registri, bend, vibrato, expression i pressure.</p><pre id="solomodel"></pre></article></section>',
    '<article class="panel"><h2>Solo Instrument DNA</h2><p>Monofonija, fraze, legato, registri, bend, vibrato, expression i pressure.</p><pre id="solomodel"></pre></article>'
    '<article class="panel"><h2>Pa800 Strumming DNA</h2><p>Guitar Mode komande, stroke alternacija, mute, strings, arpeggio, RX Noise, chord velocity i Humanize GTR.</p><pre id="strummodel"></pre></article></section>'
).replace(
    '<button id="optimize">Konvertuj i preuzmi</button>',
    '<label><input id="strumenabled" type="checkbox" checked> Aktiviraj Pa800 Strumming DNA</label>'
    '<label>Strumming jačina <input id="strumstrength" type="range" min="0" max="100" value="70"><output id="strumamount">70%</output></label>'
    '<label>Humanize GTR <input id="strumhumanize" type="range" min="0" max="100" value="50"><output id="humanizeamount">50%</output></label>'
    '<label><input id="strumvariation" type="checkbox" checked> Dozvoli sigurnu Down/Up varijaciju</label>'
    '<label>Capo 0–10<input id="capo" type="number" min="0" max="10" value="0"></label>'
    '<button id="optimize">Konvertuj i preuzmi</button>'
)

STYLE_CSS = r''':root{--ink:#16211e;--green:#174f42;--gold:#d69d38;--paper:#f4f0e5;--panel:#fffdf7;--line:#d7d1c2}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-monospace,monospace}header{padding:55px 6vw;background:var(--green);color:white;border-bottom:7px solid var(--gold)}h1{font:700 clamp(40px,7vw,76px)/1 Georgia,serif;margin:5px 0}main{width:min(1200px,94vw);margin:26px auto}.cards,.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.cards{grid-template-columns:repeat(4,1fr)}.card{background:var(--ink);color:white;padding:15px}.card b{display:block;color:#b9d8c7;font:700 26px Georgia,serif}.panel{background:var(--panel);border:1px solid var(--line);box-shadow:5px 5px 0 #ded8ca;padding:21px;margin-bottom:18px}.accent{border-top:5px solid var(--gold)}.head{display:flex;justify-content:space-between}.panel h2{font:700 26px Georgia,serif;margin-top:0}input,textarea,select{width:100%;padding:9px;border:1px solid #aaa;margin:5px 0 10px;font:inherit;background:white}input[type=checkbox]{width:auto}button{border:0;background:var(--green);color:white;padding:10px 14px;font-weight:bold;cursor:pointer}pre{white-space:pre-wrap;background:#202926;color:#d8e6de;padding:12px;max-height:330px;overflow:auto}.table{max-height:420px;overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:7px;border-bottom:1px solid var(--line);text-align:left}th{position:sticky;top:0;background:#ebe5d7}footer{text-align:center;padding:25px}@media(max-width:760px){.cards,.grid{grid-template-columns:1fr 1fr}}@media(max-width:500px){.cards,.grid{grid-template-columns:1fr}}'''

APP_JS = r'''const $=x=>document.getElementById(x);async function api(p,o={}){const r=await fetch(p,{headers:{'Content-Type':'application/json'},...o}),x=await r.json();if(!r.ok)throw Error(x.error||'Greška');return x}function b64(f){return new Promise((a,b)=>{const r=new FileReader;r.onload=()=>a(r.result.split(',')[1]);r.onerror=b;r.readAsDataURL(f)})}function table(a,c){return !a.length?'<p>Nema podataka.</p>':`<table><thead><tr>${c.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${a.map(r=>`<tr>${c.map(x=>`<td>${r[x]??''}</td>`).join('')}</tr>`).join('')}</tbody></table>`}async function refreshTests(){const t=await api('/api/test-agents');$('testagents').textContent=JSON.stringify({gate:t.gate,agents:t.reports,cases:t.cases.map(x=>({id:x.id,file:x.filename,section:x.section}))},null,2)}async function refresh(){const[s,d,c,m,z,cv,g]=await Promise.all(['/api/status','/api/dna-status','/api/pa800-catalog','/api/mappings','/api/rx-zones','/api/coverage','/api/gold-model'].map(api));$('status').innerHTML=[['Factory',s.factory.files],['Gold',s.gold.files],['Mape',s.factory.mappings],['Ready',s.ready?'DA':'NE']].map(x=>`<div class=card><b>${x[1]}</b>${x[0]}</div>`).join('');$('dna').innerHTML=Object.entries(d).map(([n,x])=>`<div class=card><b>${x.exists?'OK':'—'}</b>${n}<small>${x.tracks||0} / ${x.profiles||0}</small></div>`).join('');$('coverage').innerHTML=`<h3>${cv.track_coverage_percent}% traka · ${cv.note_coverage_percent}% nota</h3><pre>${JSON.stringify(cv.by_role,null,2)}</pre>`;$('model').textContent=JSON.stringify(Object.fromEntries(Object.entries(g.roles).map(([k,v])=>[k,{notes:v.note_count,swing:v.swing_ratio.mean,velocity:v.velocity.mean,gate:v.duration_quarters.mean}])),null,2);$('catalog').innerHTML=table(c,['name','category','bank_msb','bank_lsb','program_ui']);$('mappings').innerHTML=table(m,['source_bank_msb','source_bank_lsb','source_program_ui','role','rx_name','confidence']);$('zones').innerHTML=table(z,['profile_name','oscillator','articulation','velocity_min','velocity_max','switch_value']);await refreshTests()}$('build').onclick=async()=>{try{$('build').textContent='Gradim…';await api('/api/build-dna',{method:'POST',body:'{}'});refresh()}catch(e){alert(e.message)}finally{$('build').textContent='Obnovi DNA'}};$('testsuite').onclick=async()=>{await api('/api/test-agents/create',{method:'POST',body:JSON.stringify({name:'Pa800 A/B Release'})});refreshTests()};$('testpack').onclick=async()=>{const x=await api('/api/test-agents/export',{method:'POST',body:'{}'});$('testagents').textContent=JSON.stringify(x,null,2)};$('testresult').onclick=async()=>{const rating=+$('testrating').value;await api('/api/test-agents/result',{method:'POST',body:JSON.stringify({case_id:+$('caseid').value,agent_id:$('testagent').value,passed:$('testpassed').checked,timing_rating:rating,rx_rating:rating,drum_rating:rating,articulation_rating:rating,comments:$('testcomments').value})});refreshTests()};$('strength').oninput=e=>$('amount').textContent=e.target.value+'%';$('plan').onclick=async()=>{const x=await api('/api/plan',{method:'POST',body:JSON.stringify({context:$('goal').value,use_openai:$('online').checked})});$('plans').innerHTML=x.map(p=>`<pre><b>${p.agent}</b>\n${p.plan}</pre>`).join('')};document.querySelectorAll('[data-import]').forEach(b=>b.onclick=async()=>{const k=b.dataset.import,l=$(k+'log');for(const f of $(k).files){try{const x=await api('/api/import',{method:'POST',body:JSON.stringify({corpus:k,filename:f.name,data_base64:await b64(f)})});l.textContent+=f.name+': '+(x.deduplicated?'duplikat':'uvezen')+'\n'}catch(e){l.textContent+=e.message+'\n'}}refresh()});$('optimize').onclick=async()=>{const f=$('file').files[0];if(!f)return $('report').textContent='Odaberi MIDI.';try{const x=await api('/api/optimize',{method:'POST',body:JSON.stringify({filename:f.name,data_base64:await b64(f),strength:+$('strength').value/100})});$('report').textContent=JSON.stringify(x.report,null,2);const a=document.createElement('a');a.href='data:audio/midi;base64,'+x.data_base64;a.download=x.filename;a.click()}catch(e){$('report').textContent=e.message}};refresh().catch(e=>$('status').textContent=e.message);'''

APP_JS = APP_JS.replace(
    "strength:+$('strength').value/100})",
    "strength:+$('strength').value/100,solo_enabled:$('soloenabled').checked,solo_strength:+$('solostrength').value/100,solo_channels:$('solochannels').value.split(',').map(x=>+x.trim()).filter(x=>Number.isInteger(x)&&x>=0&&x<=15)})"
)
APP_JS += r'''$('solostrength').oninput=e=>$('soloamount').textContent=e.target.value+'%';api('/api/solo-model').then(x=>$('solomodel').textContent=JSON.stringify({tracks:x.tracks,candidates:x.candidates,models:x.models,rules:x.rules},null,2)).catch(e=>$('solomodel').textContent=e.message);'''

APP_JS = APP_JS.replace(
    "solo_channels:$('solochannels').value.split(',').map(x=>+x.trim()).filter(x=>Number.isInteger(x)&&x>=0&&x<=15)})",
    "solo_channels:$('solochannels').value.split(',').map(x=>+x.trim()).filter(x=>Number.isInteger(x)&&x>=0&&x<=15),strumming_strength:$('strumenabled').checked?+$('strumstrength').value/100:0,strumming_humanize:+$('strumhumanize').value/100,strumming_variation:$('strumvariation').checked,capo:+$('capo').value})"
)
APP_JS += r'''$('strumstrength').oninput=e=>$('strumamount').textContent=e.target.value+'%';$('strumhumanize').oninput=e=>$('humanizeamount').textContent=e.target.value+'%';api('/api/strumming-model').then(x=>$('strummodel').textContent=JSON.stringify({tracks:x.tracks,events:x.events,models:x.models,sound_profiles:x.sound_profiles,sections:x.sections,sounds:x.sounds,commands:x.commands,chord_types:x.chord_types,chord_profiles:x.chord_profiles,rules:x.rules},null,2)).catch(e=>$('strummodel').textContent=e.message);'''

APP_JS = APP_JS.replace(
    "capo:+$('capo').value})",
    "capo:+$('capo').value,delay_enabled:$('delayenabled').checked,delay_create:$('delaycreate').checked,delay_strength:+$('delaystrength').value/100,harmony_enabled:$('harmonyenabled').checked,harmony_create:false,harmony_strength:+$('harmonystrength').value/100,ornament_enabled:$('ornamentenabled').checked,allow_track_replacement:$('allowreplace').checked})"
)
APP_JS += r'''$('delaystrength').oninput=e=>$('delayamount').textContent=e.target.value+'%';$('harmonystrength').oninput=e=>$('harmonyamount').textContent=e.target.value+'%';api('/api/song-dna').then(x=>$('songdna').textContent=JSON.stringify(x,null,2)).catch(e=>$('songdna').textContent=e.message);'''

INDEX_HTML = INDEX_HTML.replace(
    '<section class="panel accent"><h2>Optimizer</h2>',
    '<section class="panel"><h2>Musical Intelligence — Trill + Layer DNA</h2><p>Factory/Balkan trill evidence, confidence komponente, negativna pravila i Solo→postojeća Terca/Delay odnosi. Terca generation je zaključan.</p><pre id="musicalintel"></pre></section>'
    '<section class="panel"><h2>Factory Sound Intelligence + Headroom</h2><p>Nepoznati User Sound se klasifikuje po načinu sviranja, zatim dobija najbliži dokazani Factory Sound. Factory određuje mix prostor, Gold izvedbu.</p><pre id="soundintel"></pre></section>'
    '<section class="panel"><h2>Instrument Identity + Full Structure DNA</h2><p>Svih 128 GM identiteta, Factory section/CV struktura i Gold korekcija istog instrumenta. Cross-instrument zamjene su blokirane.</p><pre id="instrumentstructure"></pre></section>'
    '<section class="panel accent"><h2>Optimizer</h2>'
).replace(
    '<button id="optimize">Konvertuj i preuzmi</button>',
    '<label><input id="assignunknown" type="checkbox" checked> Prepoznaj User Sound i dodijeli najbolji Factory Sound</label>'
    '<label><input id="headroomenabled" type="checkbox" checked> Factory-first kalibracija (Velocity + CC7/CC11 + headroom)</label>'
    '<label>Factory kalibracija <input id="headroomstrength" type="range" min="0" max="100" value="85"><output id="headroomamount">85%</output></label>'
    '<label><input id="guitarrepair" type="checkbox" checked> Popravi regularnu ritam-gitaru bez promjene akorda</label>'
    '<label>Guitar Repair jačina <input id="guitarrepairstrength" type="range" min="0" max="100" value="65"><output id="guitarrepairamount">65%</output></label>'
    '<button id="optimize">Konvertuj i preuzmi</button>'
)

APP_JS = APP_JS.replace(
    "allow_track_replacement:$('allowreplace').checked})",
    "allow_track_replacement:$('allowreplace').checked,assign_unknown_sounds:$('assignunknown').checked,mix_headroom:$('headroomenabled').checked,headroom_strength:+$('headroomstrength').value/100,guitar_repair:$('guitarrepair').checked,guitar_repair_strength:+$('guitarrepairstrength').value/100})"
)
APP_JS += r'''$('headroomstrength').oninput=e=>$('headroomamount').textContent=e.target.value+'%';$('guitarrepairstrength').oninput=e=>$('guitarrepairamount').textContent=e.target.value+'%';api('/api/sound-intelligence').then(x=>$('soundintel').textContent=JSON.stringify(x,null,2)).catch(e=>$('soundintel').textContent=e.message);'''
APP_JS += r'''api('/api/instrument-structure').then(x=>$('instrumentstructure').textContent=JSON.stringify(x,null,2)).catch(e=>$('instrumentstructure').textContent=e.message);'''
APP_JS += r'''api('/api/musical-intelligence').then(x=>$('musicalintel').textContent=JSON.stringify(x,null,2)).catch(e=>$('musicalintel').textContent=e.message);'''

INDEX_HTML = INDEX_HTML.replace('Gold jačina <input id="strength"','Gold izražaj (timing/gate/relativni akcenti) <input id="strength"')
INDEX_HTML = INDEX_HTML.replace(
    '<input id="file" type="file" accept=".mid,.midi">',
    '<input id="file" type="file" accept=".mid,.midi">'
    '<label>RX Sound mapiranje<select id="rxmappingmode"><option value="strict">Strict evidence — ne mijenjaj nepotvrđen Sound</option><option value="catalog_review">Catalog review — identity-safe A/B test</option></select></label>'
)
APP_JS = APP_JS.replace(
    "guitar_repair_strength:+$('guitarrepairstrength').value/100})",
    "guitar_repair_strength:+$('guitarrepairstrength').value/100,rx_mapping_mode:$('rxmappingmode').value})"
)

INDEX_HTML = INDEX_HTML.replace(
    '<section class="panel"><div class="head"><h2>Pa800 Test Agents</h2>',
    '<section class="panel"><div class="head"><h2>RX Noise Hardware Probes</h2><button id="noiseprobes">Kreiraj probe za odabrani MIDI</button></div>'
    '<input id="noiseprobefile" type="file" accept=".mid,.midi">'
    '<p>Svaki RX Noise profil dobija odvojen MIDI sa svim C7–G9 notama na velocity 1/42/84/127. Sve ostaje UNVERIFIED dok ne potvrdiš na Pa800.</p>'
    '<div class="grid"><label>Probe file ID<input id="noiseprobeid" type="number" min="1"></label>'
    '<label>Rezultat<select id="noiseprobestatus"><option value="confirmed">Confirmed</option><option value="partial">Partial</option><option value="rejected">Rejected</option></select></label></div>'
    '<label>Potvrđeni događaji nota:velocity<input id="noiseconfirmed" placeholder="96:1,96:42"></label>'
    '<label>Odbačeni događaji nota:velocity<input id="noiserejected" placeholder="97:84,97:127"></label>'
    '<textarea id="noisecomments" placeholder="Šta se čulo na Pa800, OS/resources i velocity"></textarea>'
    '<button id="noiseresult">Sačuvaj RX Noise rezultat</button><pre id="noiseprobestate"></pre></section>'
    '<section class="panel"><div class="head"><h2>Pa800 Test Agents</h2>'
)
APP_JS += r'''function probeEvents(id){return $(id).value.split(',').map(x=>x.trim()).filter(Boolean).map(x=>{const p=x.split(':').map(Number);return{note:p[0],velocity:p[1]}}).filter(x=>Number.isInteger(x.note)&&x.note>=0&&x.note<=127&&Number.isInteger(x.velocity)&&x.velocity>=1&&x.velocity<=127)}async function refreshNoise(){const x=await api('/api/rx-noise-probes');$('noiseprobestate').textContent=JSON.stringify(x,null,2)}$('noiseprobes').onclick=async()=>{const f=$('noiseprobefile').files[0];if(!f)return $('noiseprobestate').textContent='Odaberi MIDI koji nije među šest Delay/Terca referenci.';try{$('noiseprobes').textContent='Kreiram…';const x=await api('/api/rx-noise-probes/create',{method:'POST',body:JSON.stringify({filename:f.name,data_base64:await b64(f)})});$('noiseprobestate').textContent=JSON.stringify(x,null,2)}catch(e){$('noiseprobestate').textContent=e.message}finally{$('noiseprobes').textContent='Kreiraj probe za odabrani MIDI'}};$('noiseresult').onclick=async()=>{try{const x=await api('/api/rx-noise-probes/result',{method:'POST',body:JSON.stringify({probe_file_id:+$('noiseprobeid').value,status:$('noiseprobestatus').value,confirmed_events:probeEvents('noiseconfirmed'),rejected_events:probeEvents('noiserejected'),comments:$('noisecomments').value})});$('noiseprobestate').textContent=JSON.stringify(x,null,2)}catch(e){$('noiseprobestate').textContent=e.message}};refreshNoise().catch(e=>$('noiseprobestate').textContent=e.message);'''

INDEX_HTML = INDEX_HTML.replace(
    '<section class="panel"><div class="head"><h2>RX Noise Hardware Probes</h2>',
    '<section class="panel"><div class="head"><h2>Factory/Gold Single Articulation Probes</h2><button id="artprobes">Izgradi single-shot probe</button></div>'
    '<p>Jedan fajl aktivira jednu opaženu artikulaciju tačno jednom. Prethodna/sljedeća nota se dodaje samo iz radne zone istog Sounda. Šest Delay/Terca pjesama se ne koristi.</p>'
    '<div class="grid"><label>Probe file ID<input id="artprobeid" type="number" min="1"></label>'
    '<label>Rezultat<select id="artstatus"><option value="confirmed">Confirmed</option><option value="partial">Partial</option><option value="rejected">Rejected</option></select></label></div>'
    '<label>Šta se stvarno čulo<input id="artheard" placeholder="slide up, fret noise, mute..."></label>'
    '<div class="grid"><label>Pa800 OS<input id="artos" placeholder="npr. 2.01"></label>'
    '<label>Musical Resources<input id="artresources" placeholder="verzija/SET"></label></div>'
    '<label>Audio/MIDI lanac<input id="artchain" placeholder="Pa800 outputs, mixer/audio interface"></label>'
    '<textarea id="artcomments" placeholder="Pa800 OS/resources i zapažanja"></textarea>'
    '<button id="artresult">Sačuvaj artikulacijski rezultat</button> <button id="artqueue">Pripremi Evidence Review Queue</button><pre id="artstate"></pre></section>'
    '<section class="panel"><div class="head"><h2>RX Noise Hardware Probes</h2>'
)
APP_JS += r'''async function refreshArt(){const[x,q]=await Promise.all([api('/api/articulation-probes'),api('/api/articulation-promotion-queue')]);$('artstate').textContent=JSON.stringify({probes:x,promotion_queue:q},null,2)}$('artprobes').onclick=async()=>{try{$('artprobes').textContent='Analiziram Factory/Gold…';const x=await api('/api/articulation-probes/create',{method:'POST',body:'{}'});$('artstate').textContent=JSON.stringify(x,null,2)}catch(e){$('artstate').textContent=e.message}finally{$('artprobes').textContent='Izgradi single-shot probe'}};$('artresult').onclick=async()=>{try{const x=await api('/api/articulation-probes/result',{method:'POST',body:JSON.stringify({probe_file_id:+$('artprobeid').value,status:$('artstatus').value,heard_articulation:$('artheard').value,pa800_os:$('artos').value,resources_version:$('artresources').value,audio_chain:$('artchain').value,comments:$('artcomments').value})});$('artstate').textContent=JSON.stringify(x,null,2)}catch(e){$('artstate').textContent=e.message}};$('artqueue').onclick=async()=>{try{const x=await api('/api/articulation-promotion-queue/create',{method:'POST',body:'{}'});$('artstate').textContent=JSON.stringify(x,null,2)}catch(e){$('artstate').textContent=e.message}};refreshArt().catch(e=>$('artstate').textContent=e.message);'''