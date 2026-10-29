/* Escena 3D proyectada en canvas sin dependencias externas. Es ilustrativa. */
(() => {
  const canvas = document.getElementById('cultivoCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const stage = document.getElementById('stage');
  const pressure = document.getElementById('pressure');
  const rotation = document.getElementById('rotation');
  const stageHeight = {brote: 0.8, desarrollo: 1.45, maduro: 2.0};
  const plants = [];
  for (let bed = -1; bed <= 1; bed++) {
    for (let step = -4; step <= 4; step++) {
      plants.push({x: bed * 2.2 + (step % 2) * 0.12, z: step * 1.15, seed: (bed + 2) * 13 + step + 4});
    }
  }

  function project(x, y, z, yaw, scale, width, height) {
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const rx = x * c - z * s;
    const rz = x * s + z * c;
    const pitch = 0.52;
    const vertical = y * Math.cos(pitch) - rz * Math.sin(pitch);
    const depth = y * Math.sin(pitch) + rz * Math.cos(pitch);
    const perspective = 9 / (9 + depth * 0.10);
    return [width / 2 + rx * scale * perspective, height * 0.60 - vertical * scale * perspective, depth];
  }

  function polygon(points, color, stroke) {
    ctx.beginPath();
    points.forEach((point, i) => i ? ctx.lineTo(point[0], point[1]) : ctx.moveTo(point[0], point[1]));
    ctx.closePath(); ctx.fillStyle = color; ctx.fill();
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }

  function draw() {
    const width = canvas.clientWidth || 1000;
    const height = canvas.clientHeight || 620;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#c7e4d7'); gradient.addColorStop(0.55, '#e5f3e4'); gradient.addColorStop(1, '#f7f1dd');
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, width, height);
    const yaw = Number(rotation.value) * Math.PI / 180;
    const scale = Math.min(width / 13, height / 8.2);
    const p = (x, y, z) => project(x, y, z, yaw, scale, width, height);

    polygon([p(-4.3, -0.08, -6), p(4.3, -0.08, -6), p(4.3, -0.08, 6), p(-4.3, -0.08, 6)], '#afc68d', '#779667');
    for (let bed = -1; bed <= 1; bed++) {
      const x = bed * 2.2;
      polygon([p(x - 0.68, 0, -5.7), p(x + 0.68, 0, -5.7), p(x + 0.68, 0, 5.7), p(x - 0.68, 0, 5.7)], '#85633e', '#6d5439');
      polygon([p(x - 0.48, 0.13, -5.7), p(x + 0.48, 0.13, -5.7), p(x + 0.48, 0.13, 5.7), p(x - 0.48, 0.13, 5.7)], '#9a7549');
      for (let step = -4; step <= 4; step++) {
        const dot = p(x + 0.27, 0.14, step * 1.15);
        ctx.fillStyle = '#c7a379'; ctx.beginPath(); ctx.arc(dot[0], dot[1], 1.8, 0, Math.PI * 2); ctx.fill();
      }
    }

    const heightFactor = stageHeight[stage.value];
    const sorted = [...plants].sort((a, b) => p(a.x, 0, a.z)[2] - p(b.x, 0, b.z)[2]);
    sorted.forEach((plant, index) => {
      const h = heightFactor * (0.76 + (plant.seed % 5) * 0.1);
      const base = p(plant.x, 0.15, plant.z);
      const tip = p(plant.x + 0.07, h, plant.z);
      const stemWidth = Math.max(2.5, scale * 0.07);
      ctx.strokeStyle = '#246b3e'; ctx.lineCap = 'round'; ctx.lineWidth = stemWidth;
      ctx.beginPath(); ctx.moveTo(base[0], base[1]); ctx.lineTo(tip[0], tip[1]); ctx.stroke();
      for (let level = 0.42; level < 0.95; level += 0.22) {
        const origin = p(plant.x, h * level, plant.z);
        const side = index % 2 ? -1 : 1;
        const leaf = p(plant.x + side * (0.38 + level * 0.1), h * (level + 0.09), plant.z + (index % 3 - 1) * 0.16);
        ctx.strokeStyle = level > 0.7 ? '#4c9a5a' : '#3d874a'; ctx.lineWidth = Math.max(2, stemWidth * 0.65);
        ctx.beginPath(); ctx.moveTo(origin[0], origin[1]); ctx.lineTo(leaf[0], leaf[1]); ctx.stroke();
        ctx.fillStyle = '#62a967'; ctx.beginPath(); ctx.ellipse(leaf[0], leaf[1], 8, 3.5, side * -0.35, 0, Math.PI * 2); ctx.fill();
      }
      if (index < Number(pressure.value)) {
        const spot = p(plant.x, h * 0.75, plant.z);
        ctx.fillStyle = '#efb84f'; ctx.strokeStyle = '#7d531e'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(spot[0], spot[1], 7.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    });
    ctx.fillStyle = '#275944'; ctx.font = '600 13px Segoe UI, sans-serif';
    ctx.fillText('ESCENARIO VISUAL · NO ES UNA MEDICIÓN DEL LOTE', 20, height - 20);
    document.getElementById('pressureValue').textContent = `${pressure.value} punto${pressure.value === '1' ? '' : 's'}`;
    document.getElementById('rotationValue').textContent = `${rotation.value}°`;
  }

  [stage, pressure, rotation].forEach(input => input.addEventListener('input', draw));
  document.getElementById('resetScene').addEventListener('click', () => {
    stage.value = 'desarrollo'; pressure.value = '2'; rotation.value = '-25'; draw();
  });
  let dragX = null;
  canvas.addEventListener('pointerdown', event => { dragX = event.clientX; canvas.setPointerCapture(event.pointerId); });
  canvas.addEventListener('pointermove', event => {
    if (dragX === null) return;
    rotation.value = Math.max(-65, Math.min(65, Number(rotation.value) + (event.clientX - dragX) * 0.4));
    dragX = event.clientX; draw();
  });
  canvas.addEventListener('pointerup', () => { dragX = null; });
  canvas.addEventListener('pointercancel', () => { dragX = null; });
  window.addEventListener('resize', draw);
  fetch('/api/cultivo/resumen').then(async response => {
    const box = document.getElementById('sceneData');
    if (response.status === 401) {
      box.innerHTML = 'Estás viendo una escena de ejemplo. <a href="/login?next=/cultivo-3d">Inicia sesión</a> para consultar tus inspecciones.';
      return;
    }
    if (!response.ok) throw new Error('No se pudieron consultar los datos.');
    const data = await response.json();
    box.textContent = `${data.inspections} inspecciones tuyas · ${data.confirmed} confirmadas. Los puntos 3D siguen siendo ilustrativos.`;
  }).catch(() => { document.getElementById('sceneData').textContent = 'Escenario ilustrativo; tus datos no están disponibles ahora.'; });
  draw();
})();
