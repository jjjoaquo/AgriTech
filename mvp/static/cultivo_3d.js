/* Escena 3D interactiva del cultivo de espárrago con soporte para reportes PDF y YOLO. */
(() => {
  const canvas = document.getElementById('cultivoCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // Controles y elementos del DOM
  const stage = document.getElementById('stage');
  const pressure = document.getElementById('pressure');
  const rotation = document.getElementById('rotation');
  const resetBtn = document.getElementById('resetScene');
  const csrfToken = document.getElementById('csrfToken') ? document.getElementById('csrfToken').value : '';

  // Modo de visualización: 'camas' o 'grid'
  let currentMode = 'camas';
  const btnModeCamas = document.getElementById('btnModeCamas');
  const btnModeGrid = document.getElementById('btnModeGrid');

  // Formulario y estado de PDF
  const formAnalizarPdf = document.getElementById('formAnalizarPdf');
  const pdfInput = document.getElementById('pdfInput');
  const confSelect = document.getElementById('confSelect');
  const analysisProgress = document.getElementById('analysisProgress');
  const analysisError = document.getElementById('analysisError');
  const statsRibbon = document.getElementById('statsRibbon');
  const btnGuardarLote = document.getElementById('btnGuardarLote');
  const btnModoIlustrativo = document.getElementById('btnModoIlustrativo');
  const sceneData = document.getElementById('sceneData');

  // Modal y detalle de planta
  const plantModal = document.getElementById('plantModal');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const plantDetailCanvas = document.getElementById('plantDetailCanvas');
  const selectedPlantQuickview = document.getElementById('selectedPlantQuickview');
  const btnOpenModal = document.getElementById('btnOpenModal');

  // Estado de los datos de inspección
  let reportData = null; // Almacenará la respuesta del backend
  let activePlants = [];  // Arreglo de plantas en 3D con coordenadas proyectadas
  let selectedPlant = null;
  let hoveredPlant = null;

  const stageHeight = { brote: 0.8, desarrollo: 1.45, maduro: 2.0 };

  // --- Proyección 3D en perspectiva ---
  function project(x, y, z, yaw, scale, width, height) {
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const rx = x * c - z * s;
    const rz = x * s + z * c;
    const pitch = 0.52;
    const vertical = y * Math.cos(pitch) - rz * Math.sin(pitch);
    const depth = y * Math.sin(pitch) + rz * Math.cos(pitch);
    const perspective = 9 / (9 + depth * 0.10);
    return [
      width / 2 + rx * scale * perspective,
      height * 0.60 - vertical * scale * perspective,
      depth
    ];
  }

  function polygon(points, color, stroke) {
    ctx.beginPath();
    points.forEach((pt, i) => i ? ctx.lineTo(pt[0], pt[1]) : ctx.moveTo(pt[0], pt[1]));
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  // --- Generación de posiciones según modo ---
  function buildPlantPositions() {
    activePlants = [];
    if (!reportData || !reportData.plants || !reportData.plants.length) {
      // Modo ilustrativo inicial (3 camas fijas)
      const maxPressure = pressure ? Number(pressure.value) : 2;
      for (let bed = -1; bed <= 1; bed++) {
        for (let step = -4; step <= 4; step++) {
          const index = activePlants.length;
          activePlants.push({
            id: index + 1,
            x: bed * 2.2 + (step % 2) * 0.12,
            z: step * 1.15,
            status: index < maxPressure ? 'alerta' : 'limpio',
            seed: (bed + 2) * 13 + step + 4,
            detections: index < maxPressure ? [{ class_name: 'spodoptera eridania larva', confidence: 0.88 }] : [],
            image: null,
            isIllustrative: true,
          });
        }
      }
      return;
    }

    const plants = reportData.plants;
    const count = plants.length;

    if (currentMode === 'camas') {
      // Distribución a lo largo de las 3 camas de espárrago
      const beds = [-2.2, 0, 2.2];
      const perBed = Math.ceil(count / 3);
      const spanZ = Math.max(7, perBed * 1.5);
      const stepZ = spanZ / Math.max(1, perBed - 1);

      plants.forEach((p, idx) => {
        const bedIdx = idx % 3;
        const rowInBed = Math.floor(idx / 3);
        const zPos = -spanZ / 2 + rowInBed * stepZ;
        activePlants.push({
          ...p,
          x: beds[bedIdx] + ((rowInBed % 2) * 0.15),
          z: zPos,
          seed: idx * 7 + 3,
        });
      });
    } else {
      // Modo Cuadrícula de Parcelas (Grid N x M)
      const cols = (reportData.grid && reportData.grid.cols) || Math.min(4, count);
      const rows = Math.ceil(count / cols);
      const cellWidth = 1.6;
      const cellDepth = 1.4;
      const originX = -((cols - 1) * cellWidth) / 2;
      const originZ = -((rows - 1) * cellDepth) / 2;

      plants.forEach((p, idx) => {
        const r = Math.floor(idx / cols);
        const c = idx % cols;
        activePlants.push({
          ...p,
          gridRow: r,
          gridCol: c,
          x: originX + c * cellWidth,
          z: originZ + r * cellDepth,
          seed: idx * 11 + 5,
        });
      });
    }
  }

  // --- Dibujado principal de la escena ---
  function draw() {
    const width = canvas.clientWidth || 1000;
    const height = canvas.clientHeight || 620;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);

    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    // Fondo degradado de campo y cielo
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#c7e4d7');
    gradient.addColorStop(0.55, '#e5f3e4');
    gradient.addColorStop(1, '#f7f1dd');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    const yaw = Number(rotation ? rotation.value : -25) * Math.PI / 180;
    const scale = Math.min(width / 13, height / 8.2);
    const p = (x, y, z) => project(x, y, z, yaw, scale, width, height);

    // 1. Dibujar el terreno base
    if (currentMode === 'camas') {
      // Suelo general
      polygon([p(-4.8, -0.08, -6.5), p(4.8, -0.08, -6.5), p(4.8, -0.08, 6.5), p(-4.8, -0.08, 6.5)], '#afc68d', '#779667');
      // 3 Camas de espárrago
      for (let bed = -1; bed <= 1; bed++) {
        const x = bed * 2.2;
        polygon([p(x - 0.72, 0, -6), p(x + 0.72, 0, -6), p(x + 0.72, 0, 6), p(x - 0.72, 0, 6)], '#85633e', '#6d5439');
        polygon([p(x - 0.50, 0.13, -6), p(x + 0.50, 0.13, -6), p(x + 0.50, 0.13, 6), p(x - 0.50, 0.13, 6)], '#9a7549');
      }
    } else {
      // Malla de parcelas (Grid)
      polygon([p(-5.2, -0.05, -5.2), p(5.2, -0.05, -5.2), p(5.2, -0.05, 5.2), p(-5.2, -0.05, 5.2)], '#b4caa0', '#6f8f5d');
      if (reportData && activePlants.length) {
        const cellW = 1.45, cellD = 1.25;
        activePlants.forEach(plant => {
          const px = plant.x, pz = plant.z;
          const isAlert = plant.status === 'alerta';
          const isSel = selectedPlant && selectedPlant.id === plant.id;
          const fillColor = isSel ? '#e0f2fe' : (isAlert ? '#fde8e4' : '#e6f4ea');
          const strokeColor = isSel ? '#2563eb' : (isAlert ? '#e54b3c' : '#72aa7c');
          polygon([
            p(px - cellW / 2, 0.02, pz - cellD / 2),
            p(px + cellW / 2, 0.02, pz - cellD / 2),
            p(px + cellW / 2, 0.02, pz + cellD / 2),
            p(px - cellW / 2, 0.02, pz + cellD / 2)
          ], fillColor, strokeColor);
        });
      }
    }

    // 2. Ordenar plantas de atrás hacia adelante por profundidad Z
    const heightFactor = stage && stageHeight[stage.value] ? stageHeight[stage.value] : 1.45;
    const sorted = [...activePlants].sort((a, b) => p(a.x, 0, a.z)[2] - p(b.x, 0, b.z)[2]);

    sorted.forEach((plant, index) => {
      const h = heightFactor * (0.8 + (plant.seed % 4) * 0.08);
      const base = p(plant.x, 0.15, plant.z);
      const tip = p(plant.x + 0.07, h, plant.z);
      const stemWidth = Math.max(2.5, scale * 0.07);

      // Guardar coordenadas de pantalla del centroide para detección de clics
      const spot = p(plant.x, h * 0.72, plant.z);
      plant.screenX = spot[0];
      plant.screenY = spot[1];
      plant.radius = Math.max(14, scale * 0.28);

      const isSelected = selectedPlant && selectedPlant.id === plant.id;
      const isHovered = hoveredPlant && hoveredPlant.id === plant.id;
      const hasAlert = plant.status === 'alerta';

      // Halo de selección
      if (isSelected || isHovered) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(spot[0], spot[1], plant.radius + 6, 0, Math.PI * 2);
        ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.35)' : 'rgba(16, 185, 129, 0.25)';
        ctx.fill();
        ctx.strokeStyle = isSelected ? '#2563eb' : '#059669';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.restore();
      }

      // Tallo principal
      ctx.strokeStyle = hasAlert ? '#2f6d41' : '#23733d';
      ctx.lineCap = 'round';
      ctx.lineWidth = stemWidth;
      ctx.beginPath();
      ctx.moveTo(base[0], base[1]);
      ctx.lineTo(tip[0], tip[1]);
      ctx.stroke();

      // Ramas y plumillas de espárrago
      for (let level = 0.40; level < 0.95; level += 0.22) {
        const origin = p(plant.x, h * level, plant.z);
        const side = index % 2 ? -1 : 1;
        const leaf = p(plant.x + side * (0.35 + level * 0.1), h * (level + 0.09), plant.z + (index % 3 - 1) * 0.14);
        ctx.strokeStyle = level > 0.7 ? '#4c9a5a' : '#3d874a';
        ctx.lineWidth = Math.max(1.8, stemWidth * 0.62);
        ctx.beginPath();
        ctx.moveTo(origin[0], origin[1]);
        ctx.lineTo(leaf[0], leaf[1]);
        ctx.stroke();

        ctx.fillStyle = hasAlert ? '#68a666' : '#5fb567';
        ctx.beginPath();
        ctx.ellipse(leaf[0], leaf[1], 7.5, 3.2, side * -0.35, 0, Math.PI * 2);
        ctx.fill();
      }

      // Marcador de diagnóstico fitosanitario
      ctx.save();
      ctx.beginPath();
      ctx.arc(spot[0], spot[1], isSelected ? 11 : 8.5, 0, Math.PI * 2);
      ctx.fillStyle = hasAlert ? '#e54b3c' : '#2da44e';
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2.5;
      ctx.fill();
      ctx.stroke();

      // Número o icono dentro del marcador
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 10px Segoe UI, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(plant.id), spot[0], spot[1]);
      ctx.restore();

      // Etiqueta flotante si tiene plaga
      if (hasAlert && (isSelected || isHovered || currentMode === 'grid')) {
        ctx.save();
        const pestName = plant.detections && plant.detections[0] ? plant.detections[0].class_name : 'Plaga detectada';
        const labelText = `#${plant.id} ${pestName}`;
        ctx.font = '600 11px Segoe UI, sans-serif';
        const textWidth = ctx.measureText(labelText).width;
        const boxX = spot[0] - textWidth / 2 - 8;
        const boxY = spot[1] - 28;

        ctx.fillStyle = 'rgba(168, 30, 20, 0.92)';
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(boxX, boxY, textWidth + 16, 20, 4) : ctx.rect(boxX, boxY, textWidth + 16, 20);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, boxX + 8, boxY + 10);
        ctx.restore();
      }
    });

    // Pie de canvas informativo
    ctx.fillStyle = '#275944';
    ctx.font = '600 12px Segoe UI, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    const modeDesc = currentMode === 'camas' ? 'CAMAS DE ESPÁRRAGO' : 'CUADRÍCULA DE PARCELAS';
    const statusDesc = reportData ? `REPORTE: ${reportData.filename || 'PDF'} · ${reportData.total_plants} PLANTAS (${reportData.infested_count} CON FOCOS)` : 'MODO SIMULACIÓN EJEMPLO';
    ctx.fillText(`${modeDesc} · ${statusDesc}`, 20, height - 20);

    if (rotation && document.getElementById('rotationValue')) {
      document.getElementById('rotationValue').textContent = `${rotation.value}°`;
    }
    if (pressure && document.getElementById('pressureValue')) {
      document.getElementById('pressureValue').textContent = `${pressure.value} punto${pressure.value === '1' ? '' : 's'}`;
    }
  }

  // --- Detección de clics sobre plantas (Raycasting 2D) ---
  function getPlantAtPosition(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;

    let closest = null;
    let minDistance = Infinity;

    activePlants.forEach(plant => {
      if (plant.screenX === undefined || plant.screenY === undefined) return;
      const dx = mouseX - plant.screenX;
      const dy = mouseY - plant.screenY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist <= (plant.radius || 18) + 6 && dist < minDistance) {
        minDistance = dist;
        closest = plant;
      }
    });

    return closest;
  }

  // --- Modal de inspección detallada con recuadros de YOLO ---
  function openPlantModal(plant) {
    if (!plant) return;
    selectedPlant = plant;

    const modalTitle = document.getElementById('modalPlantTitle');
    const modalEyebrow = document.getElementById('modalPlantEyebrow');
    const modalStatusCard = document.getElementById('modalStatusCard');
    const modalStatusHeading = document.getElementById('modalStatusHeading');
    const modalStatusDesc = document.getElementById('modalStatusDescription');
    const detectionsContainer = document.getElementById('modalDetectionsContainer');

    modalEyebrow.textContent = `PLANTA #${plant.id} ${plant.gridRow !== undefined ? `· FILA ${plant.gridRow + 1}, COL ${plant.gridCol + 1}` : ''}`;
    modalTitle.textContent = plant.status === 'alerta' ? 'Alerta Fitosanitaria Detectada' : 'Planta Aparentemente Sana';

    modalStatusCard.className = `modal-status-card ${plant.status}`;
    if (plant.status === 'alerta') {
      const countsDesc = Object.entries(plant.counts || {})
        .map(([cls, cnt]) => `${cnt} × ${cls}`)
        .join(', ');
      modalStatusHeading.textContent = `⚠ ${plant.detections.length} plaga(s) localizada(s)`;
      modalStatusDesc.textContent = countsDesc || 'Se observaron insectos sospechosos con el modelo detector YOLOv8.';
    } else {
      modalStatusHeading.textContent = '✓ Sin signos de plagas detectadas';
      modalStatusDesc.textContent = 'El modelo YOLOv8 no encontró recuadros de plagas en esta toma de espárrago.';
    }

    // Renderizar lista de detecciones
    detectionsContainer.innerHTML = '';
    if (!plant.detections || !plant.detections.length) {
      detectionsContainer.innerHTML = '<p class="small muted">No se registraron recuadros de plagas en esta fotografía.</p>';
    } else {
      plant.detections.forEach((det, i) => {
        const item = document.createElement('div');
        item.className = 'detection-item';
        item.innerHTML = `
          <span class="detection-name">#${i + 1} ${det.class_name}</span>
          <span class="detection-conf">Certeza: ${Math.round(det.confidence * 100)}%</span>
        `;
        detectionsContainer.appendChild(item);
      });
    }

    // Dibujar la foto con los recuadros de YOLO sobre el canvas del modal
    drawPlantDetailImage(plant);

    plantModal.hidden = false;
    plantModal.setAttribute('aria-hidden', 'false');
  }

  function drawPlantDetailImage(plant) {
    const detailCtx = plantDetailCanvas.getContext('2d');
    detailCtx.clearRect(0, 0, plantDetailCanvas.width, plantDetailCanvas.height);

    if (!plant.image) {
      // Placeholder si es simulación ilustrativa
      detailCtx.fillStyle = '#1c3524';
      detailCtx.fillRect(0, 0, plantDetailCanvas.width, plantDetailCanvas.height);
      detailCtx.fillStyle = '#ffffff';
      detailCtx.font = '600 16px Segoe UI, sans-serif';
      detailCtx.textAlign = 'center';
      detailCtx.fillText(`Fotografía ilustrativa · Planta #${plant.id}`, plantDetailCanvas.width / 2, plantDetailCanvas.height / 2 - 10);
      detailCtx.font = '13px Segoe UI, sans-serif';
      detailCtx.fillStyle = '#a3cfb0';
      detailCtx.fillText('Carga un reporte PDF para ver fotografías reales.', plantDetailCanvas.width / 2, plantDetailCanvas.height / 2 + 18);
      return;
    }

    const img = new Image();
    img.onload = () => {
      plantDetailCanvas.width = img.naturalWidth || 640;
      plantDetailCanvas.height = img.naturalHeight || 640;
      detailCtx.drawImage(img, 0, 0);

      // Dibujar cada recuadro (bounding box) de YOLO
      (plant.detections || []).forEach(det => {
        if (!det.xyxy || det.xyxy.length !== 4) return;
        const [x1, y1, x2, y2] = det.xyxy;
        const boxW = x2 - x1;
        const boxH = y2 - y1;

        // Fondo semitransparente del recuadro
        detailCtx.fillStyle = 'rgba(239, 68, 68, 0.22)';
        detailCtx.fillRect(x1, y1, boxW, boxH);

        // Borde nítido
        detailCtx.strokeStyle = '#ef4444';
        detailCtx.lineWidth = Math.max(3, plantDetailCanvas.width / 220);
        detailCtx.strokeRect(x1, y1, boxW, boxH);

        // Etiqueta con clase y confianza
        const tagText = `${det.class_name} (${Math.round(det.confidence * 100)}%)`;
        detailCtx.font = 'bold 15px Segoe UI, sans-serif';
        const tagWidth = detailCtx.measureText(tagText).width;
        const tagY = y1 > 26 ? y1 - 24 : y1;

        detailCtx.fillStyle = '#ef4444';
        detailCtx.fillRect(x1, tagY, tagWidth + 14, 24);

        detailCtx.fillStyle = '#ffffff';
        detailCtx.fillText(tagText, x1 + 7, tagY + 17);
      });
    };
    img.src = plant.image;
  }

  function closePlantModal() {
    plantModal.hidden = true;
    plantModal.setAttribute('aria-hidden', 'true');
  }

  // --- Eventos de interacción del Canvas ---
  let dragX = null;
  canvas.addEventListener('pointerdown', event => {
    dragX = event.clientX;
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener('pointermove', event => {
    // 1. Manejo del giro arrastrando
    if (dragX !== null && rotation) {
      rotation.value = String(Math.max(-65, Math.min(65, Number(rotation.value) + (event.clientX - dragX) * 0.4)));
      dragX = event.clientX;
      draw();
      return;
    }

    // 2. Hover sobre plantas
    const hit = getPlantAtPosition(event.clientX, event.clientY);
    if (hit !== hoveredPlant) {
      hoveredPlant = hit;
      canvas.style.cursor = hit ? 'pointer' : 'grab';
      draw();
    }
  });

  canvas.addEventListener('pointerup', event => {
    if (dragX !== null) {
      // Si casi no se movió, interpretar como clic
      const plant = getPlantAtPosition(event.clientX, event.clientY);
      if (plant) {
        selectedPlant = plant;
        updateQuickview(plant);
        openPlantModal(plant);
      }
    }
    dragX = null;
    draw();
  });

  canvas.addEventListener('pointercancel', () => { dragX = null; });

  function updateQuickview(plant) {
    if (!selectedPlantQuickview) return;
    selectedPlantQuickview.hidden = false;
    document.getElementById('quickviewTitle').textContent = `Planta #${plant.id}`;
    const statusPill = document.getElementById('quickviewStatus');
    statusPill.className = `status-pill ${plant.status}`;
    statusPill.textContent = plant.status === 'alerta' ? '⚠ Foco de plaga detectado' : '✓ Aparentemente sana';
  }

  if (btnOpenModal) {
    btnOpenModal.addEventListener('click', () => {
      if (selectedPlant) openPlantModal(selectedPlant);
    });
  }

  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', closePlantModal);
  }
  if (plantModal) {
    plantModal.addEventListener('click', event => {
      if (event.target === plantModal) closePlantModal();
    });
  }
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && plantModal && !plantModal.hidden) closePlantModal();
  });

  // --- Alternancia de modos (Camas vs Cuadrícula) ---
  if (btnModeCamas && btnModeGrid) {
    btnModeCamas.addEventListener('click', () => {
      currentMode = 'camas';
      btnModeCamas.classList.add('active');
      btnModeGrid.classList.remove('active');
      buildPlantPositions();
      draw();
    });

    btnModeGrid.addEventListener('click', () => {
      currentMode = 'grid';
      btnModeGrid.classList.add('active');
      btnModeCamas.classList.remove('active');
      buildPlantPositions();
      draw();
    });
  }

  // --- Procesamiento del Formulario PDF ---
  if (formAnalizarPdf) {
    formAnalizarPdf.addEventListener('submit', async event => {
      event.preventDefault();
      const file = pdfInput.files && pdfInput.files[0];
      if (!file) {
        showError('Selecciona un archivo PDF.');
        return;
      }

      analysisError.hidden = true;
      analysisProgress.hidden = false;
      document.getElementById('progressText').textContent = 'Extrayendo fotografías del PDF y ejecutando inferencia con YOLO...';

      const formData = new FormData();
      formData.append('reporte', file);
      formData.append('confidence', confSelect.value || '0.30');

      try {
        const response = await fetch('/api/cultivo/analizar-pdf', {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRF-Token': csrfToken }
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'No se pudo procesar el reporte.');
        }

        // Éxito: almacenar datos y actualizar vistas
        reportData = data;
        analysisProgress.hidden = true;

        // Actualizar cinta de estadísticas
        statsRibbon.hidden = false;
        document.getElementById('statTotal').textContent = String(data.total_plants);
        document.getElementById('statHealthy').textContent = String(data.healthy_count);
        document.getElementById('statInfested').textContent = String(data.infested_count);

        const pestsEntries = Object.entries(data.pests_summary || {});
        document.getElementById('statPestsList').textContent = pestsEntries.length
          ? pestsEntries.map(([name, count]) => `${name} (${count})`).join(', ')
          : 'Ninguna plaga identificada';

        // Ocultar controles ilustrativos y mostrar botón para volver
        if (btnModoIlustrativo) btnModoIlustrativo.style.display = 'inline-block';
        if (btnGuardarLote) btnGuardarLote.style.display = 'inline-block';

        sceneData.textContent = `Reporte procesado: ${data.total_plants} plantas analizadas (${data.infested_count} con alerta).`;

        // Construir geometría y seleccionar la primera planta con alerta (o la primera)
        buildPlantPositions();
        const firstAlert = activePlants.find(p => p.status === 'alerta') || activePlants[0];
        if (firstAlert) {
          selectedPlant = firstAlert;
          updateQuickview(firstAlert);
        }
        draw();
      } catch (err) {
        analysisProgress.hidden = true;
        showError(err.message);
      }
    });
  }

  function showError(msg) {
    if (!analysisError) return;
    analysisError.textContent = msg;
    analysisError.hidden = false;
  }

  // Guardar lote opcional en historial
  if (btnGuardarLote) {
    btnGuardarLote.addEventListener('click', async () => {
      if (!reportData || !reportData.plants) return;
      btnGuardarLote.disabled = true;
      btnGuardarLote.textContent = 'Guardando...';

      try {
        const response = await fetch('/api/cultivo/guardar-lote', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
          },
          body: JSON.stringify({
            sector: `Reporte PDF: ${reportData.filename || 'Lote 3D'}`,
            plants: reportData.plants
          })
        });

        const resData = await response.json();
        if (!response.ok) throw new Error(resData.error || 'Error al guardar.');

        btnGuardarLote.textContent = `✓ ${resData.message || 'Lote guardado'}`;
        btnGuardarLote.classList.remove('account-secondary');
        btnGuardarLote.classList.add('account-primary');
      } catch (err) {
        alert(err.message);
        btnGuardarLote.disabled = false;
        btnGuardarLote.textContent = '💾 Reintentar guardar en historial';
      }
    });
  }

  // Volver a simulación ilustrativa
  if (btnModoIlustrativo) {
    btnModoIlustrativo.addEventListener('click', () => {
      reportData = null;
      selectedPlant = null;
      statsRibbon.hidden = true;
      btnModoIlustrativo.style.display = 'none';
      if (btnGuardarLote) btnGuardarLote.style.display = 'none';
      sceneData.textContent = 'Modo ilustrativo reactivado.';
      buildPlantPositions();
      draw();
    });
  }

  // Controladores de giro y reinicio
  if (rotation) rotation.addEventListener('input', draw);
  if (stage) stage.addEventListener('input', draw);
  if (pressure) {
    pressure.addEventListener('input', () => {
      if (!reportData) {
        buildPlantPositions();
        draw();
      }
    });
  }
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (rotation) rotation.value = '-25';
      draw();
    });
  }
  window.addEventListener('resize', draw);

  // Inicialización
  buildPlantPositions();
  draw();
})();
