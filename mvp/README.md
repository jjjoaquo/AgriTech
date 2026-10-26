# MVP de inspección de plagas en cultivos

Aplicación Flask para inspectores de campo y supervisores agronómicos. La portada ofrece dos módulos:

- **Clasificación general:** ResNet‑152 de Alonso, 102 clases de plagas de distintos cultivos. Analiza la foto completa y muestra tres hipótesis; no genera cajas ni determina el cultivo. Su uso es experimental hasta confirmar el tamaño de entrada y evaluar con un conjunto independiente.
- **Inspección de espárrago:** YOLOv8n V2 analiza fotos o fotogramas de cámara y muestra recuadros, clases, confianza, conteos y velocidad observada. El usuario puede congelar la captura, corregir cajas, registrar hallazgos y consultar SIGIA de SENASA para espárrago. Esta consulta es una fuente pública externa y no valida la identificación visual.

## Ejecutar en local

Desde esta carpeta, con Python 3.10 o superior:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abrir `http://127.0.0.1:5000` para elegir un módulo. El peso ResNet no se guarda en Git: colocar `best_resnet152_baseline.safetensors` en `models/` o definir `AGRI_RESNET_WEIGHTS` con su ruta absoluta. Se puede convertir el checkpoint original `.pth` mediante [convert_resnet_checkpoint.py](convert_resnet_checkpoint.py). La cámara YOLO requiere permiso del navegador. Para verificar las funciones principales:

```powershell
python smoke_test.py
node --check static/app.js
node --check static/general.js
```

## Modelos y resultados

- `models/classes_ip102.txt` contiene las 102 etiquetas que proporcionó Alonso. `models/best_resnet152_baseline.safetensors` deriva directamente del `.pth` entregado, sin el estado del optimizador; pesa aproximadamente 234 MB y no se publica en Git. El checkpoint informa F1 macro de validación 0,6365 con `epoch=7`, pero no incluye métricas de prueba ni el valor original de `IMG_SIZE`. Se usa 224 px como valor operativo; véase [CLASIFICADOR_GENERAL.md](CLASIFICADOR_GENERAL.md). Falta confirmar con Alonso si el archivo corresponde a su entrenamiento balanceado y cómo se relaciona con las métricas del notebook.
- `models/esparragos_yolov8n_v2.pt` es el detector predeterminado del MVP. Es el peso V2 del equipo.
- `models/esparragos_yolo26n_semisupervisado.pt` es un experimento disponible solo para comparar fotografías. En 32 fotos externas reservadas detectó la clase esperada en 6, frente a 25 de V2; esta prueba no tiene cajas verificadas y no demuestra precisión en parcelas.
- El umbral inicial del detector V2 es 30 %. En la prueba de umbral a 640 px encontró la clase esperada en 24 de 32 fotos, frente a 21 con 45 %.
- Los reportes, parámetros y límites de la evaluación están en `training_runs/` y [MEJORA_MODELO.md](MEJORA_MODELO.md).

## Datos y procedencia

El repositorio conserva manifiestos, atribuciones y scripts de preparación, pero **no publica las fotos descargadas, etiquetas originales del compañero, datos de usuarios ni archivos de entrenamiento pesados**. El conjunto Roboflow v1 del colaborador tenía 99 originales y 297 variantes; su procedencia detallada aún necesita revisión. Las 24 fotos de espárrago de contexto no son imágenes negativas verificadas. Véanse los archivos `dataset_candidates/*/manifest.csv` y [ESTADO_PARA_PRESENTACION.md](ESTADO_PARA_PRESENTACION.md).

Los scripts de entrenamiento requieren los conjuntos originales en las rutas indicadas en [MEJORA_MODELO.md](MEJORA_MODELO.md). No se debe comparar un modelo con imágenes originales o variantes que ya usó para entrenar.

## Despliegue

La versión pública está en [https://esparragos.comextech.es/](https://esparragos.comextech.es/). La configuración del VPS está en [deploy/DEPLOY_VPS.md](deploy/DEPLOY_VPS.md). El sitio no requiere usuario ni contraseña; las fotos, ubicaciones e historial que se guarden serán visibles públicamente.
