const input = document.getElementById('generalImage');
const button = document.getElementById('classifyBtn');
const photo = document.getElementById('generalPhoto');
const empty = document.getElementById('generalEmpty');
const message = document.getElementById('classifyMessage');
const hint = document.getElementById('generalResultHint');
const results = document.getElementById('generalResults');
const time = document.getElementById('generalTime');
let selectedFile = null;
let previewUrl = null;

input.addEventListener('change', () => {
  const file = input.files[0];
  selectedFile = null;
  button.disabled = true;
  results.replaceChildren();
  hint.textContent = 'Esperando análisis.';
  time.textContent = '';
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  if (!file) return;
  if (!file.size || file.size > 10 * 1024 * 1024 || (file.type && !file.type.startsWith('image/'))) {
    message.textContent = 'Selecciona una imagen JPG o PNG de hasta 10 MB.';
    photo.hidden = true;
    empty.hidden = false;
    return;
  }
  selectedFile = file;
  previewUrl = URL.createObjectURL(file);
  photo.src = previewUrl;
  photo.hidden = false;
  empty.hidden = true;
  button.disabled = button.dataset.available !== 'true';
  message.textContent = button.disabled ? 'El peso ResNet no está instalado en este servidor.' : 'Imagen lista para clasificar.';
});

button.addEventListener('click', async () => {
  if (!selectedFile) return;
  button.disabled = true;
  message.textContent = 'Clasificando fotografía… La primera carga puede tardar más.';
  hint.textContent = 'Analizando la imagen completa…';
  results.replaceChildren();
  time.textContent = '';
  try {
    const form = new FormData();
    form.append('image', selectedFile, selectedFile.name);
    const response = await fetch('/api/classify', {method: 'POST', body: form});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo clasificar la imagen.');
    hint.textContent = 'Tres hipótesis para revisar:';
    for (const prediction of data.predictions) {
      const item = document.createElement('li');
      const label = document.createElement('strong');
      label.textContent = prediction.class_name;
      const score = document.createElement('span');
      score.textContent = `${Math.round(prediction.score * 100)} %`;
      item.append(label, score);
      results.append(item);
    }
    time.textContent = `${data.model} · ${data.inference_ms} ms en este servidor`;
    message.textContent = 'Clasificación lista. Confirma la especie con un especialista.';
  } catch (error) {
    hint.textContent = 'Sin resultado.';
    message.textContent = error.message;
  } finally {
    button.disabled = !selectedFile || button.dataset.available !== 'true';
  }
});