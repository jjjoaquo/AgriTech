# Entrenamiento del candidato IP102 balanceado

El archivo `ip102_balanced_stylegan2.zip` contiene fotografías en `train`, `val` y `test`, con carpetas de clases `0` a `101`. **No es un modelo entrenado.** El peso actualmente publicado en `/general` es el ResNet‑152 no balanceado que entregó Alonso. Su entrada es de 256 × 256 px.

`train_ip102_balanced.py` ajusta primero la capa de clasificación del peso vigente y luego su bloque `layer4`. Selecciona la mejor época por F1 macro de **validación**. Solo después evalúa tanto el candidato como el peso vigente sobre el mismo conjunto `test`. Guarda los pesos del candidato y `comparison.json` por separado; no modifica producción. El conjunto de prueba del ZIP puede coincidir con imágenes usadas en entrenamientos anteriores, por lo que sus métricas no sustituyen una evaluación externa con fotos nuevas.

## Ejecutar en un equipo con GPU CUDA

Copiar el ZIP y `best_resnet152_baseline.safetensors` al equipo de entrenamiento. Instalar PyTorch compatible con su GPU, TorchVision, Pillow y `safetensors`. Desde `mvp/`:

```bash
python train_ip102_balanced.py \
  --dataset /ruta/ip102_balanced_stylegan2.zip \
  --baseline /ruta/best_resnet152_baseline.safetensors \
  --output /ruta/resultado_ip102 \
  --head-epochs 2 --fine-epochs 4 --batch-size 16 --workers 2
```

Si falta memoria GPU, bajar `--batch-size` a 8. El entrenamiento completo se detiene antes de empezar si no hay CUDA. Se ofrece `--smoke` para comprobar el proceso con cuatro imágenes por conjunto en CPU; ese modo **no produce un modelo final**.

## Criterio para publicar

1. Comprobar en `comparison.json` que el candidato mejora al peso actual en F1 macro sobre el mismo `test`. Revisar también accuracy, balanced accuracy y recall por clase para detectar daños en clases concretas.
2. Confirmar que las clases, el tamaño de entrada y la normalización coinciden con el servicio. El archivo de salida es `best_resnet152_balanced_candidate.safetensors`; conserva exactamente la arquitectura de 102 salidas.
3. Revisar imágenes nuevas de los cultivos objetivo y la procedencia de las fotografías sintéticas. No atribuir a SENASA una validación del modelo.
4. Solo entonces instalar el peso candidato en el VPS y hacer una prueba de la API antes de comunicarlo como modelo final. Mantener copia del peso anterior para revertir si falla.

El ZIP y los pesos permanecen fuera del repositorio por tamaño y por la revisión pendiente de derechos de uso de las imágenes.
