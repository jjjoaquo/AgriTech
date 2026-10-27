# Entrenamiento del candidato IP102 balanceado

El archivo `ip102_balanced_stylegan2.zip` contiene fotografías en `train`, `val` y `test`, con carpetas de clases `0` a `101`. **No es un modelo entrenado.** El peso actualmente publicado en `/general` es el ResNet‑152 no balanceado que entregó Alonso. Su entrada es de 256 × 256 px.

`train_ip102_balanced.py` ajusta primero la capa de clasificación del peso vigente y luego su bloque `layer4`. Selecciona la mejor época por F1 macro de **validación**. Solo después evalúa tanto el candidato como el peso vigente sobre el mismo conjunto `test`. Guarda los pesos del candidato y `comparison.json` por separado; no modifica producción. El conjunto de prueba del ZIP puede coincidir con imágenes usadas en entrenamientos anteriores, por lo que sus métricas no sustituyen una evaluación externa con fotos nuevas.

La auditoría de SHA-256 de las 99 123 imágenes encontró cuatro grupos de duplicados exactos; dos cruzan `train` y `test` (clases 56 y 92). Véase `training_runs/ip102_split_audit.json`. El efecto numérico directo sobre 22 619 fotos de prueba es pequeño, pero la métrica del ZIP no debe describirse como prueba completamente independiente. La auditoría de bytes no detecta duplicados visuales reescalados o recortados.

## Google Colab

Abrir [colab_entrenar_ip102.ipynb](colab_entrenar_ip102.ipynb) en Colab y activar una GPU CUDA. El cuaderno usa los dos enlaces de Drive que compartió Alonso, verificados por nombre y tamaño con Google Drive: el ZIP de 3 698 825 898 bytes y el checkpoint original de 701 581 674 bytes. Comprueba además sus SHA‑256 contra los archivos recibidos localmente. El resultado se guarda en `/content/AgriTech-IP102-resultado` y debe descargarse antes de cerrar la sesión; no solicita acceso al Drive personal del usuario. Las sesiones T4 del 26 de octubre de 2026 perdieron conexión antes de obtener un informe final verificable; sus checkpoints temporales no se consideran resultados publicados.

## Ejecutar en un equipo con GPU CUDA

Copiar el ZIP y `best_resnet152_baseline.safetensors` al equipo de entrenamiento. Instalar PyTorch compatible con su GPU, TorchVision, Pillow y `safetensors`. Desde `mvp/`:

```bash
python train_ip102_balanced.py \
  --dataset /ruta/ip102_balanced_stylegan2.zip \
  --baseline /ruta/best_resnet152_baseline.safetensors \
  --output /ruta/resultado_ip102 \
  --head-epochs 2 --fine-epochs 4 --batch-size 16 --workers 2
```

Si falta memoria GPU, bajar `--batch-size` a 8. Sin CUDA se exige `--allow-cpu`, pues el procesamiento puede tardar muchas horas. Se ofrece `--smoke` para comprobar el proceso con cuatro imágenes por conjunto en CPU; ese modo **no produce un modelo final**.

## Ejecución local en el equipo de Michelle

El equipo tiene Intel Core i5-1135G7, Intel Iris Xe y PyTorch 2.12 para CPU, sin CUDA. El 26 de octubre de 2026 se inició una ejecución local persistente que usa **todas** las imágenes del ZIP, una época de ajuste de la capa final y una época de `layer4`. La salida está en `training_runs/ip102_cpu_candidate/` y los registros en `training_runs/ip102_cpu_train.log` y `.err.log`. Comando equivalente:

```bash
python mvp/train_ip102_balanced.py --dataset C:/Users/ANGIE/Downloads/ip102_balanced_stylegan2.zip \
  --baseline mvp/models/best_resnet152_baseline.safetensors \
  --output mvp/training_runs/ip102_cpu_candidate \
  --head-epochs 1 --fine-epochs 1 --batch-size 8 --workers 2 --allow-cpu
```

La ejecución local es un **candidato en curso**; no se considerará terminada hasta que aparezca `comparison.json` con `status=completed` y se valide el archivo de pesos.

Tras el reinicio inesperado de Windows del 27 de octubre de 2026, la ejecución inicial perdió el avance de su primera época porque todavía no había guardado pesos. El script ahora guarda `training_checkpoint.pt` cada 250 lotes y al terminar cada época. Al relanzar el mismo comando con los mismos parámetros, reanuda desde el último checkpoint y registra el número de imágenes procesadas. El archivo temporal se reemplaza de forma atómica y se excluye de Git.

## Criterio para publicar

1. Comprobar en `comparison.json` que el candidato mejora al peso actual en F1 macro sobre el mismo `test`. Revisar también accuracy, balanced accuracy y recall por clase para detectar daños en clases concretas.
2. Confirmar que las clases, el tamaño de entrada y la normalización coinciden con el servicio. El archivo de salida es `best_resnet152_balanced_candidate.safetensors`; conserva exactamente la arquitectura de 102 salidas.
3. Revisar imágenes nuevas de los cultivos objetivo y la procedencia de las fotografías sintéticas. No atribuir a SENASA una validación del modelo.
4. Solo entonces instalar el peso candidato en el VPS y hacer una prueba de la API antes de comunicarlo como modelo final. Mantener copia del peso anterior para revertir si falla.

El ZIP y los pesos permanecen fuera del repositorio por tamaño y por la revisión pendiente de derechos de uso de las imágenes.
