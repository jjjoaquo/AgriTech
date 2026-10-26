const $ = id => document.getElementById(id);
const state = {stream:null, running:false, generation:0, latest:null, imageData:null,
  tracks:[], nextTrackId:1, frameTimes:[], location:null, mode:null, products:[], senasaLookupClass:null, selected:-1, addBox:false, drag:null, photoBlob:null, photoRequest:0};
const sourceCanvas = document.createElement('canvas');
const sourceCtx = sourceCanvas.getContext('2d');
const overlay = $('overlay');
const overlayCtx = overlay.getContext('2d');
for(const name of window.PEST_CLASSES)$('boxClass').add(new Option(name,name));

function message(text, error=false){
  // Avoid announcing the same camera status on every frame.
  if($('message').textContent!==text)$('message').textContent=text;
  $('message').classList.toggle('error',error);
}
function recordMessage(text, error=false){
  $('saveMessage').textContent=text;
  $('saveMessage').classList.toggle('error',error);
}
function photoBusy(busy){
  $('viewport').setAttribute('aria-busy',String(busy));
  $('analysisProgress').hidden=!busy;
  if(busy)$('livePill').textContent='Analizando…';
}
function clearResultView(text='Esperando una imagen'){
  $('totalCount').textContent='—';$('resultSummary').textContent=text;
  $('senasaClass').disabled=true;$('senasaBtn').disabled=true;
  $('resultModel').textContent='—';$('fps').textContent='— FPS';
  $('detections').replaceChildren();
  const empty=document.createElement('p');empty.className='muted';empty.textContent=text;
  $('detections').append(empty);
  $('resultDot').classList.remove('active');
  $('saveBtn').disabled=true;$('saveHelp').textContent='Primero analiza una foto o un fotograma.';
  $('saveMessage').textContent='';
  $('alertTitle').textContent='Sin alerta activa';
  $('alertText').textContent='Revisa el resultado cuando termine el análisis.';
  $('alertTitle').closest('.alert-card').classList.remove('active');
}

function confidence(){ return Number($('confidence').value)/100; }
function setupCanvas(){ overlay.width=$('viewport').clientWidth; overlay.height=$('viewport').clientHeight; drawOverlay(); }
window.addEventListener('resize', setupCanvas);
$('confidence').addEventListener('input',()=>{$('confidenceValue').textContent=$('confidence').value+' %';$('confidence').setAttribute('aria-valuetext',$('confidence').value+' por ciento');});

function iou(a,b){
  const x1=Math.max(a[0],b[0]),y1=Math.max(a[1],b[1]),x2=Math.min(a[2],b[2]),y2=Math.min(a[3],b[3]);
  const intersection=Math.max(0,x2-x1)*Math.max(0,y2-y1);
  const areaA=Math.max(0,a[2]-a[0])*Math.max(0,a[3]-a[1]);
  const areaB=Math.max(0,b[2]-b[0])*Math.max(0,b[3]-b[1]);
  return intersection/(areaA+areaB-intersection||1);
}
function updateTracks(detections){
  const old=state.tracks.filter(t=>t.missed<3);
  const used=new Set();
  state.tracks=detections.map(d=>{
    let match=null,best=0;
    for(const t of old){
      if(used.has(t.id)||t.class_name!==d.class_name)continue;
      const score=iou(t.xyxy,d.xyxy);
      if(score>.25&&score>best){best=score;match=t;}
    }
    if(match){used.add(match.id);return {...d,id:match.id,streak:match.streak+1,missed:0};}
    return {...d,id:state.nextTrackId++,streak:1,missed:0};
  });
  for(const t of old)if(!used.has(t.id))state.tracks.push({...t,missed:t.missed+1,streak:0});
  return state.tracks.filter(t=>t.missed===0);
}
function drawOverlay(){
  overlayCtx.clearRect(0,0,overlay.width,overlay.height);
  if(!state.latest)return;
  const media=state.mode==='camera' ? $('video') : $('photo');
  if(media.hidden)return;
  const outer=$('viewport').getBoundingClientRect(),rect=media.getBoundingClientRect();
  const offsetX=rect.left-outer.left,offsetY=rect.top-outer.top;
  const sx=rect.width/state.latest.width,sy=rect.height/state.latest.height;
  for(const d of state.latest.detections){
    const [x1,y1,x2,y2]=d.xyxy;
    const x=offsetX+x1*sx,y=offsetY+y1*sy,w=(x2-x1)*sx,h=(y2-y1)*sy;
    const active=state.tracks.some(t=>t.missed===0&&t.class_name===d.class_name&&iou(t.xyxy,d.xyxy)>.8&&t.streak>=3);
    const color=state.mode==='photo'&&state.selected===state.latest.detections.indexOf(d)?'#50c9ff':active?'#f3b454':'#d6ef75';
    overlayCtx.strokeStyle=color;overlayCtx.lineWidth=3;overlayCtx.strokeRect(x,y,w,h);
    const label=d.manual?`${d.class_name} · manual`:`${d.class_name} · ${Math.round(d.confidence*100)} %`;
    overlayCtx.font='bold 13px Segoe UI, Arial';
    const labelWidth=Math.min(overlayCtx.measureText(label).width+14,overlay.width-x-3);
    const labelY=Math.max(0,y-25);
    overlayCtx.fillStyle=color;overlayCtx.fillRect(x,labelY,labelWidth,24);
    overlayCtx.fillStyle='#103a2d';overlayCtx.fillText(label,x+7,labelY+16,labelWidth-10);
  }
  if(state.drag?.type==='add'){
    const [x1,y1,x2,y2]=state.drag.box;
    overlayCtx.strokeStyle='#50c9ff';overlayCtx.lineWidth=2;overlayCtx.setLineDash([7,4]);
    overlayCtx.strokeRect(x1,y1,x2-x1,y2-y1);overlayCtx.setLineDash([]);
  }
}
function refreshReview(){
  const editable=state.mode==='photo'&&!!state.latest;
  $('addBoxBtn').disabled=!editable;$('removeBoxBtn').disabled=!editable||state.selected<0;
  $('boxClass').disabled=!editable||state.selected<0;
  if(state.selected>=0&&state.latest?.detections[state.selected])$('boxClass').value=state.latest.detections[state.selected].class_name;
  $('reviewHint').textContent=editable?(state.addBox?'Arrastra sobre la imagen para dibujar la caja nueva.':state.selected>=0?'Caja seleccionada: arrástrala para moverla o arrastra una esquina para redimensionarla.':'Selecciona un recuadro para editarlo.'):'Primero analiza una foto o congela un fotograma.';
  overlay.classList.toggle('editable',editable);
  $('boxSelection').disabled=!editable;
  const choices=editable?state.latest.detections:[];
  // Keep the focused native select stable during camera updates and pointer edits.
  const key=String(editable)+JSON.stringify(choices.map(d=>d.class_name));
  if($('boxSelection').dataset.options!==key){
    $('boxSelection').replaceChildren(new Option(editable?'Selecciona un recuadro':'Primero analiza una imagen','-1'));
    choices.forEach((d,i)=>$('boxSelection').add(new Option('Recuadro '+(i+1)+' · '+d.class_name,String(i))));
    $('boxSelection').dataset.options=key;
  }
  $('boxSelection').value=String(state.selected);
  $('addBoxBtn').setAttribute('aria-pressed',String(state.addBox));
}
$('boxSelection').addEventListener('change',()=>{
  state.selected=Number($('boxSelection').value);state.addBox=false;
  $('addBoxBtn').classList.remove('active');refreshReview();drawOverlay();
});
function mediaGeometry(){
  const media=$('photo'),outer=$('viewport').getBoundingClientRect(),rect=media.getBoundingClientRect();
  return {left:rect.left-outer.left,top:rect.top-outer.top,width:rect.width,height:rect.height};
}
function toImagePoint(event){
  const rect=overlay.getBoundingClientRect(),m=mediaGeometry();
  return [Math.max(0,Math.min(state.latest.width,(event.clientX-rect.left-m.left)*state.latest.width/m.width)),
          Math.max(0,Math.min(state.latest.height,(event.clientY-rect.top-m.top)*state.latest.height/m.height))];
}
function normalizeBox(box){
  return [Math.max(0,Math.min(box[0],box[2])),Math.max(0,Math.min(box[1],box[3])),
          Math.min(state.latest.width,Math.max(box[0],box[2])),Math.min(state.latest.height,Math.max(box[1],box[3]))];
}
overlay.addEventListener('pointerdown',event=>{
  if(state.mode!=='photo'||!state.latest)return;
  const point=toImagePoint(event);
  if(state.addBox){state.drag={type:'add',start:point,box:[event.offsetX,event.offsetY,event.offsetX,event.offsetY]};overlay.setPointerCapture(event.pointerId);return;}
  let selected=-1;
  for(let i=state.latest.detections.length-1;i>=0;i--){const [x1,y1,x2,y2]=state.latest.detections[i].xyxy;
    if(point[0]>=x1&&point[0]<=x2&&point[1]>=y1&&point[1]<=y2){selected=i;break;}}
  state.selected=selected;refreshReview();drawOverlay();
  if(selected<0)return;
  const box=state.latest.detections[selected].xyxy.slice();
  const margin=Math.max(12,Math.min(state.latest.width,state.latest.height)*.025);
  let corner=-1;for(let i=0;i<4;i++){const cx=i%2?box[2]:box[0],cy=i>=2?box[3]:box[1];if(Math.hypot(point[0]-cx,point[1]-cy)<margin){corner=i;break;}}
  state.drag={type:corner>=0?'resize':'move',start:point,original:box,corner};overlay.setPointerCapture(event.pointerId);
});
overlay.addEventListener('pointermove',event=>{
  if(!state.drag||!state.latest)return;
  const point=toImagePoint(event),d=state.drag;
  if(d.type==='add'){
    const m=mediaGeometry();const x=m.left+point[0]*m.width/state.latest.width,y=m.top+point[1]*m.height/state.latest.height;
    d.box[2]=x;d.box[3]=y;drawOverlay();return;
  }
  const box=d.original.slice();
  if(d.type==='move'){
    const dx=point[0]-d.start[0],dy=point[1]-d.start[1],w=box[2]-box[0],h=box[3]-box[1];
    box[0]=Math.max(0,Math.min(state.latest.width-w,box[0]+dx));box[1]=Math.max(0,Math.min(state.latest.height-h,box[1]+dy));box[2]=box[0]+w;box[3]=box[1]+h;
  }else{
    box[d.corner%2?2:0]=point[0];box[d.corner>=2?3:1]=point[1];
  }
  state.latest.detections[state.selected].xyxy=normalizeBox(box);
  state.latest.detections[state.selected].manual=true;state.latest.detections[state.selected].confidence=0;
  drawOverlay();
});
overlay.addEventListener('pointerup',event=>{
  if(!state.drag)return;
  const d=state.drag;state.drag=null;
  if(d.type==='add'){
    const point=toImagePoint(event),box=normalizeBox([d.start[0],d.start[1],point[0],point[1]]);
    if(box[2]-box[0]>=5&&box[3]-box[1]>=5){
      state.latest.detections.push({class_name:$('boxClass').value||window.PEST_CLASSES[0],confidence:0,xyxy:box,manual:true});
      state.selected=state.latest.detections.length-1;
    }
    state.addBox=false;$('addBoxBtn').classList.remove('active');
  }
  $('reviewed').checked=false;updateUI(state.latest);refreshReview();
});
$('addBoxBtn').addEventListener('click',()=>{state.addBox=!state.addBox;state.selected=-1;$('addBoxBtn').classList.toggle('active',state.addBox);refreshReview();});
$('removeBoxBtn').addEventListener('click',()=>{if(state.selected<0)return;state.latest.detections.splice(state.selected,1);state.selected=-1;$('reviewed').checked=false;updateUI(state.latest);refreshReview();});
$('boxClass').addEventListener('change',()=>{if(state.selected<0)return;state.latest.detections[state.selected].class_name=$('boxClass').value;state.latest.detections[state.selected].manual=true;state.latest.detections[state.selected].confidence=0;$('reviewed').checked=false;updateUI(state.latest);refreshReview();});
function updateUI(result){
  state.latest=result;
  result.counts={};for(const detection of result.detections)result.counts[detection.class_name]=(result.counts[detection.class_name]||0)+1;
  const active=updateTracks(result.detections);
  $('totalCount').textContent=result.detections.length;
  $('resultSummary').textContent=state.mode==='camera'?'En el fotograma actual':'En la imagen analizada';
  $('saveHelp').textContent='Añade el lote y el estado de revisión para guardar.';
  $('latency').textContent=result.inference_ms+' ms';
  $('frameState').textContent=result.detections.length?'Detección activa':'Sin plagas detectadas';
  $('resultDot').classList.toggle('active',result.detections.length>0);
  $('saveBtn').disabled=false;
  $('modelName').textContent='Modelo '+result.model;
  $('resultModel').textContent=result.model.includes('yolo26')?'YOLO26n experimental':'YOLOv8n V2';
  const counts=Object.entries(result.counts).sort((a,b)=>b[1]-a[1]);
  if(state.senasaLookupClass&&!counts.some(([name])=>name===state.senasaLookupClass)){
    state.senasaLookupClass=null;state.products=[];$('productsCard').hidden=true;
    $('senasaResult').textContent='Selecciona una plaga detectada para consultar SIGIA.';
  }
  $('detections').replaceChildren();
  if(!counts.length){const p=document.createElement('p');p.className='muted';p.textContent='No se encontraron objetos sobre el umbral actual. Esto no descarta la presencia de plagas; verifica la imagen en campo.';$('detections').append(p);}
  for(const [name,count] of counts){
    const row=document.createElement('div');row.className='detection-row';
    const label=document.createElement('span');label.textContent=name;
    const detail=document.createElement('small');detail.className='detection-detail';
    const detections=result.detections.filter(d=>d.class_name===name);
    const scores=detections.filter(d=>!d.manual).map(d=>Math.round(d.confidence*100));
    if(scores.length){
      const low=Math.min(...scores),high=Math.max(...scores);
      detail.textContent='Confianza: '+low+(low===high?'':'–'+high)+' %';
      if(detections.some(d=>d.manual))detail.textContent+=' · incluye revisión manual';
    }else detail.textContent='Recuadros corregidos manualmente';
    label.append(detail);
    const value=document.createElement('strong');value.textContent='× '+count;
    row.append(label,value);$('detections').append(row);
  }
  $('senasaClass').disabled=false;
  const oldSelection=$('senasaClass').value;
  $('senasaClass').replaceChildren(new Option('Selecciona una plaga',''));
  for(const [name] of counts)$('senasaClass').add(new Option(name,name));
  if(counts.some(([name])=>name===oldSelection))$('senasaClass').value=oldSelection;
  else if(counts.length===1)$('senasaClass').value=counts[0][0];
  $('senasaBtn').disabled=!$('senasaClass').value;
  const stable=state.mode==='camera' ? active.filter(t=>t.streak>=3) : active;
  $('alertTitle').textContent=stable.length?`${stable.length} detección${stable.length===1?'':'es'} para revisar`:'Sin alerta activa';
  $('alertText').textContent=stable.length?(state.mode==='camera'?'La detección persistió en varios fotogramas. Confirma la especie antes de actuar.':'Revisa cada recuadro y confirma la especie antes de actuar.'):'La alerta se activa si la misma clase aparece en varios fotogramas consecutivos.';
  $('alertTitle').closest('.alert-card').classList.toggle('active',stable.length>0);
  state.frameTimes.push(performance.now());state.frameTimes=state.frameTimes.filter(t=>performance.now()-t<3000);
  $('fps').textContent=state.mode==='camera'&&state.frameTimes.length>1?((state.frameTimes.length-1)*1000/(state.frameTimes.at(-1)-state.frameTimes[0])).toFixed(1)+' FPS':'— FPS';
  drawOverlay();
  refreshReview();
}
async function detectBlob(blob){
  const form=new FormData();form.append('image',blob,'fotograma.jpg');form.append('confidence',String(confidence()));form.append('model',$('modelChoice').value);
  const response=await fetch('/api/detect',{method:'POST',body:form});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Error de detección');
  return data;
}
async function stopCamera(){
  state.running=false;state.generation++;
  if(state.stream)for(const track of state.stream.getTracks())track.stop();
  state.stream=null;$('video').srcObject=null;$('video').hidden=true;
  $('cameraBtn').disabled=$('modelChoice').value==='candidate';$('stopBtn').disabled=true;
  $('freezeBtn').disabled=true;
  $('modelChoice').disabled=false;
  $('livePill').classList.remove('active');$('livePill').textContent='Sin cámara';
  if(state.mode==='camera'){state.mode=null;state.latest=null;state.imageData=null;state.tracks=[];$('emptyState').hidden=false;$('viewportMeta').hidden=true;clearResultView();setupCanvas();refreshReview();}
}
$('freezeBtn').addEventListener('click',async()=>{
  if(!state.imageData||!state.latest)return;
  const image=state.imageData,result=state.latest;
  state.running=false;state.generation++;
  if(state.stream)for(const track of state.stream.getTracks())track.stop();
  state.stream=null;$('video').srcObject=null;$('video').hidden=true;
  $('cameraBtn').disabled=$('modelChoice').value==='candidate';$('stopBtn').disabled=true;$('freezeBtn').disabled=true;
  $('modelChoice').disabled=false;
  $('livePill').classList.remove('active');$('livePill').textContent='Captura congelada';
  state.mode='photo';state.latest=result;state.imageData=image;state.selected=-1;state.tracks=[];
  state.photoBlob=await (await fetch(image)).blob();
  $('photo').src=image;$('photo').hidden=false;await $('photo').decode();setupCanvas();refreshReview();
  message('Fotograma congelado. Revisa clases y cajas antes de confirmarlo.');
});
async function captureLoop(generation){
  if(!state.running||generation!==state.generation)return;
  const video=$('video');
  if(video.videoWidth&&video.videoHeight){
    const scale=Math.min(1,960/video.videoWidth);
    sourceCanvas.width=Math.round(video.videoWidth*scale);sourceCanvas.height=Math.round(video.videoHeight*scale);
    sourceCtx.drawImage(video,0,0,sourceCanvas.width,sourceCanvas.height);
    const dataUrl=sourceCanvas.toDataURL('image/jpeg',.8);
    const blob=await new Promise(resolve=>sourceCanvas.toBlob(resolve,'image/jpeg',.8));
    try{
      const result=await detectBlob(blob);
      if(generation!==state.generation)return;
       state.imageData=dataUrl;updateUI(result);$('freezeBtn').disabled=false;message('Cámara activa. Congela un fotograma para revisar sus cajas.');
    }catch(error){if(generation===state.generation)message(error.message,true);}
  }
  if(state.running&&generation===state.generation)setTimeout(()=>captureLoop(generation),120);
}
$('cameraBtn').addEventListener('click',async()=>{
  if($('modelChoice').value!=='baseline')return message('Selecciona YOLOv8n V2 para inspección con cámara.',true);
  state.photoRequest++;photoBusy(false);
  await stopCamera();$('photo').hidden=true;clearResultView('Preparando cámara…');
  $('cameraBtn').disabled=true;
  try{
    const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false});
     state.stream=stream;state.mode='camera';state.running=true;state.tracks=[];state.frameTimes=[];state.selected=-1;$('reviewed').checked=false;
    $('modelChoice').disabled=true;
    $('video').srcObject=stream;$('video').hidden=false;await $('video').play();
    $('emptyState').hidden=true;$('viewportMeta').hidden=false;
    $('livePill').classList.add('active');$('livePill').textContent='EN VIVO';
    $('cameraBtn').disabled=true;$('stopBtn').disabled=false;setupCanvas();captureLoop(state.generation);
  }catch(error){message('No se pudo abrir la cámara: '+error.message,true);stopCamera();}
});
$('stopBtn').addEventListener('click',stopCamera);
$('photoInput').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  event.target.value='';
  if(!file.size||file.size>10*1024*1024)return message('Selecciona una imagen de entre 1 byte y 10 MB.',true);
  if(file.type&&!file.type.startsWith('image/'))return message('Selecciona un archivo de imagen, por ejemplo JPG o PNG.',true);
   await stopCamera();state.mode='photo';state.tracks=[];state.frameTimes=[];state.selected=-1;state.addBox=false;$('reviewed').checked=false;
  state.photoBlob=file;const photoRequest=++state.photoRequest;
  $('livePill').textContent='Foto cargada';
  state.latest=null;state.imageData=null;
  clearResultView('Preparando imagen…');refreshReview();setupCanvas();photoBusy(true);
  const reader=new FileReader();
  reader.onload=async()=>{
    if(photoRequest!==state.photoRequest)return;
    state.imageData=reader.result;$('photo').src=reader.result;
    $('photo').hidden=false;$('emptyState').hidden=true;$('viewportMeta').hidden=false;
    try{await $('photo').decode();}
    catch(error){
      if(photoRequest===state.photoRequest){
        photoBusy(false);$('photo').hidden=true;$('emptyState').hidden=false;$('viewportMeta').hidden=true;
        $('livePill').textContent='Imagen no compatible';clearResultView('No se pudo abrir la imagen.');
        message('No se pudo abrir la imagen. Prueba con otra foto JPG o PNG.',true);
      }
      return;
    }
    if(photoRequest!==state.photoRequest)return;
    setupCanvas();message('Analizando imagen…');
     try{const result=await detectBlob(file);if(photoRequest!==state.photoRequest)return;updateUI(result);$('livePill').textContent='Foto analizada';message('Análisis terminado. Revisa las cajas y confirma el hallazgo.');}
    catch(error){if(photoRequest===state.photoRequest){$('livePill').textContent='Análisis no disponible';clearResultView('No se pudo completar el análisis.');message(error.message,true);}}
    finally{if(photoRequest===state.photoRequest)photoBusy(false);}
  };
  reader.onerror=()=>{
    if(photoRequest!==state.photoRequest)return;
    photoBusy(false);$('livePill').textContent='No se pudo leer';
    clearResultView('Selecciona la imagen nuevamente.');message('No se pudo leer el archivo. Selecciona la imagen nuevamente.',true);
  };
  reader.readAsDataURL(file);
});
async function reanalyzePhoto(){
  if(state.mode!=='photo'||!state.photoBlob)return;
  const photoRequest=++state.photoRequest;state.latest=null;state.selected=-1;$('reviewed').checked=false;
  clearResultView('Analizando con la nueva configuración…');refreshReview();photoBusy(true);setupCanvas();message('Analizando la foto con la configuración seleccionada…');
  try{const result=await detectBlob(state.photoBlob);if(photoRequest!==state.photoRequest)return;updateUI(result);$('livePill').textContent='Foto analizada';message('Análisis actualizado. Revisa el resultado antes de registrar.');}
  catch(error){if(photoRequest===state.photoRequest){$('livePill').textContent='Análisis no disponible';clearResultView('No se pudo completar el análisis.');message(error.message,true);}}
  finally{if(photoRequest===state.photoRequest)photoBusy(false);}
}
$('modelChoice').addEventListener('change',reanalyzePhoto);
$('modelChoice').addEventListener('change',()=>{$('cameraBtn').disabled=$('modelChoice').value==='candidate';});
$('confidence').addEventListener('change',reanalyzePhoto);
$('senasaClass').addEventListener('change',()=>{$('senasaBtn').disabled=!$('senasaClass').value;});
$('senasaBtn').addEventListener('click',async()=>{
  const name=$('senasaClass').value;if(!name)return;
  $('productsCard').hidden=true;state.senasaLookupClass=null;
  $('senasaBtn').disabled=true;$('senasaResult').textContent='Consultando SIGIA de SENASA… La detección sigue disponible.';
  try{
    const start=await fetch('/api/senasa/consultas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_name:name})});
    const job=await start.json();if(!start.ok)throw new Error(job.error);
    for(let attempt=0;attempt<60;attempt++){
      await new Promise(resolve=>setTimeout(resolve,2000));
      const response=await fetch(`/api/senasa/consultas/${job.job_id}`);
      const result=await response.json();
      if(result.status==='success'){
        if(!state.latest?.detections.some(d=>d.class_name===name)){
          $('senasaResult').textContent='La consulta terminó, pero esa plaga ya no aparece en la imagen actual. Selecciónala de nuevo si deseas ver su ficha.';
          return;
        }
        state.senasaLookupClass=name;
        $('senasaResult').replaceChildren();
        const a=document.createElement('a');a.href=result.pdf_url;a.target='_blank';a.rel='noopener';a.textContent='Abrir PDF descargado de SIGIA ↗';
        $('senasaResult').append(`Consulta completada para ${result.crop}: ${result.product_count} registros en ${result.pages} páginas. `,a);
        const productsResponse=await fetch(`/api/senasa/consultas/${job.job_id}/productos`);
        if(productsResponse.ok){state.products=await productsResponse.json();$('productsCard').hidden=false;renderProducts();}
        return;
      }
      if(result.status==='error')throw new Error(result.message||'SIGIA no respondió.');
    }
    throw new Error('La consulta demoró demasiado. Abre SIGIA directamente.');
  }catch(error){
    $('senasaResult').replaceChildren(document.createTextNode(`No se pudo recuperar el PDF: ${error.message}. `));
    const a=document.createElement('a');a.href='https://servicios.senasa.gob.pe/SIGIAWeb/sigia_consulta_plaga.html';a.target='_blank';a.rel='noopener';a.textContent='Abrir SIGIA ↗';$('senasaResult').append(a);
  }finally{$('senasaBtn').disabled=!$('senasaClass').value;}
});
function renderProducts(){
  const query=$('productSearch').value.trim().toLocaleLowerCase('es');
  const filtered=state.products.filter(p=>[p.registration,p.name,p.ingredient,p.category].some(v=>v.toLocaleLowerCase('es').includes(query)));
  $('productsCount').textContent=state.products.length+' registros';
  $('productsBody').replaceChildren();
  for(const product of filtered.slice(0,100)){
    const row=document.createElement('tr');
    for(const key of ['registration','name','ingredient','category','pc','lmr']){
      const cell=document.createElement('td');cell.textContent=product[key]||'—';row.append(cell);
    }
    $('productsBody').append(row);
  }
  $('productsShown').textContent=`Mostrando ${Math.min(filtered.length,100)} de ${filtered.length} coincidencias. Busca por nombre, ingrediente o registro para filtrar.`;
}
$('productSearch').addEventListener('input',renderProducts);
$('locationBtn').addEventListener('click',()=>{
  if(!navigator.geolocation){$('locationStatus').textContent='Este navegador no ofrece ubicación.';return;}
  $('locationStatus').textContent='Solicitando ubicación…';
  navigator.geolocation.getCurrentPosition(pos=>{
    state.location={lat:pos.coords.latitude,lon:pos.coords.longitude};
    $('locationStatus').textContent=`Ubicación añadida: ${state.location.lat.toFixed(5)}, ${state.location.lon.toFixed(5)}`;
  },()=>{$('locationStatus').textContent='Ubicación no disponible; puedes guardar sin ella.';},{enableHighAccuracy:true,timeout:10000});
});
$('sector').addEventListener('input',()=>{
  if($('sector').value.trim()){$('sectorError').hidden=true;$('sector').removeAttribute('aria-invalid');}
});
$('saveBtn').addEventListener('click',async()=>{
  if(!state.latest||!state.imageData)return recordMessage('Primero analiza una imagen.',true);
  const sector=$('sector').value.trim();
  $('sectorError').hidden=!!sector;$('sector').setAttribute('aria-invalid',String(!sector));
  if(!sector){$('sector').focus();return recordMessage('Falta el sector o lote.',true);}
  if($('reviewStatus').value==='confirmado'&&(state.mode!=='photo'||!$('reviewed').checked||!state.latest.detections.length))
    return recordMessage('Para confirmar, congela el fotograma y revisa cada caja, clase e imagen.',true);
  $('saveBtn').disabled=true;$('saveBtn').textContent='Guardando…';recordMessage('Guardando el hallazgo…');
  try{
    const response=await fetch('/api/hallazgos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      sector,observations:$('observations').value,status:$('reviewStatus').value,lat:state.location?.lat,lon:state.location?.lon,
       detections:state.latest.detections,image:state.imageData,model:state.latest.model,reviewed:$('reviewed').checked&&state.mode==='photo'})});
    const result=await response.json();if(!response.ok)throw new Error(result.error);
    recordMessage('Hallazgo guardado. Ya puedes consultarlo en el historial.');loadHistory();
  }catch(error){recordMessage(error.message,true);}finally{$('saveBtn').disabled=!state.latest;$('saveBtn').textContent='Guardar hallazgo';}
});
async function loadHistory(){
  $('history').setAttribute('aria-busy','true');
  $('refreshBtn').disabled=true;$('historyMessage').textContent='Cargando historial…';
  try{
    const response=await fetch('/api/hallazgos');
    if(!response.ok)throw new Error('No se pudo recuperar el historial.');
    const findings=await response.json();
    $('historyMessage').textContent=findings.length?findings.length+' registro(s) recientes':'Tu próximo hallazgo aparecerá aquí.';
    $('history').replaceChildren();
    if(!findings.length){const p=document.createElement('p');p.className='muted';p.textContent='Aún no hay hallazgos guardados.';$('history').append(p);return;}
    for(const item of findings){
      const row=document.createElement('div');row.className='history-item';
      const img=document.createElement('img');img.src=item.image_url;img.alt='Captura del hallazgo en '+item.sector;img.loading='lazy';
      const info=document.createElement('div');const title=document.createElement('strong');title.textContent=item.sector;
      const date=document.createElement('small');date.textContent=new Date(item.created_at).toLocaleString('es-PE');
      const summary=document.createElement('p');summary.textContent=`${item.detections.length} detección(es) · ${[...new Set(item.detections.map(d=>d.class_name))].join(', ') || 'Sin detecciones'}`;
      const status=document.createElement('span');status.className='history-status';status.dataset.status=item.status;
      status.textContent=({pendiente:'Pendiente de revisión',confirmado:'Confirmado',falso_positivo:'Falso positivo'})[item.status]||item.status;
      const model=document.createElement('small');model.textContent='Modelo: '+item.model;
      info.append(title,date,summary,model,status);
      if(item.lat!==null&&item.lon!==null){const map=document.createElement('a');map.href=`https://www.google.com/maps?q=${encodeURIComponent(item.lat+','+item.lon)}`;map.target='_blank';map.rel='noopener';map.textContent='Ver ubicación ↗';info.append(map);}
      row.append(img,info);$('history').append(row);
    }
  }catch(error){$('historyMessage').textContent='No se pudo cargar el historial. Usa Actualizar para volver a intentarlo.';}
  finally{$('history').setAttribute('aria-busy','false');$('refreshBtn').disabled=false;}
}
$('refreshBtn').addEventListener('click',loadHistory);
async function loadModelComparison(){
  try{
    const response=await fetch('/api/model-comparison');if(!response.ok)return;
    const report=await response.json();
    $('baselineHits').textContent=`${report.baseline.hit_count}/${report.baseline.total}`;
    $('candidateHits').textContent=`${report.candidate.hit_count}/${report.candidate.total}`;
    $('baselineExtra').textContent=`${report.baseline.other_class_boxes} cajas de otras clases · ${Math.round(report.baseline.median_inference_ms)} ms/foto`;
    $('candidateExtra').textContent=`${report.candidate.other_class_boxes} cajas de otras clases · ${Math.round(report.candidate.median_inference_ms)} ms/foto`;
    $('comparisonBody').replaceChildren();
    window.PEST_CLASSES.forEach((name,index)=>{
      const row=document.createElement('tr'),label=document.createElement('td');label.textContent=name;row.append(label);
      for(const key of ['baseline','candidate']){
        const cell=document.createElement('td'),entry=report[key].by_class[String(index)];
        cell.textContent=entry?`${entry.hits}/${entry.total}`:'Sin datos';row.append(cell);
      }
      $('comparisonBody').append(row);
    });
    $('comparisonCard').hidden=false;
  }catch(error){/* La comparación es opcional y no afecta la inspección. */}
}
// Anchor navigation remains usable without JavaScript.
const navigationLinks=[...document.querySelectorAll('.top-nav a')];
function markNavigation(hash){
  navigationLinks.forEach(link=>{
    if(link.hash===hash)link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
  });
}
navigationLinks.forEach(link=>link.addEventListener('click',()=>markNavigation(link.hash)));
window.addEventListener('hashchange',()=>{
  if(navigationLinks.some(link=>link.hash===location.hash))markNavigation(location.hash);
});
loadModelComparison();
loadHistory();setupCanvas();
