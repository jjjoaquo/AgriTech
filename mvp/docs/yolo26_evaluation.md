# Reentrenamiento experimental de YOLO26n

Se descargó la [versión pública v1 del dataset del compañero](https://universe.roboflow.com/alonmiorro-gmail-com/my-first-project-1rsof/dataset/1) en formato YOLOv8. El ZIP contiene 99 fotos originales con tres variantes aumentadas cada una, 297 imágenes y siete clases exportadas. Se separaron por **foto original**: 201 imágenes de entrenamiento, 48 de validación y 48 de prueba. Todas las variantes de un original quedaron en el mismo conjunto. Se usó semilla 42.

Se afinó el modelo preentrenado **YOLO26n** durante 20 épocas, a 512 px, lote 8, en CPU, con Ultralytics 8.4.66. El peso quedó en `models/esparragos_yolo26n_experimental.pt`. El historial está en `runs/detect/training_runs/yolo26n_roboflow_v1_pilot/results.csv` y la partición reproducible en `training_data/roboflow_v1_grouped/split_report.json`.

## Resultado

| Evaluación | YOLO26n experimental |
| --- | ---: |
| Prueba agrupada, precisión | 0,578 |
| Prueba agrupada, recall | 0,468 |
| Prueba agrupada, mAP50 | 0,494 |
| Prueba agrupada, mAP50-95 | 0,305 |
| Fotos externas de iNaturalist con clase esperada detectada | 9/96 (9,4 %) |

En las mismas 96 fotos externas, **YOLOv8n V2 detectó la clase esperada en 72/96 (75 %)** con `conf=0.25` y `imgsz=512`. Esta prueba externa solo comprueba si aparece la clase esperada en alguna caja; carece de recuadros verificados, no mide la precisión de ubicación, y no incluye la clase *Prodiplosis longifila* larva. Las fotos externas tampoco verifican el hospedero espárrago.

El mejor peso nuevo **no reemplaza** al peso V2 de la aplicación: su desempeño externo es claramente inferior en esta prueba. La validación histórica de V2 no debe compararse numéricamente con la partición agrupada actual; los conjuntos difieren y es probable que V2 haya visto los originales del Roboflow público.

## Qué falta para mejorar el detector

1. Revisar y corregir las cajas propuestas para las fotos externas, en especial las clases con pocos originales. El directorio `dataset_candidates/inaturalist/review/` y su manifiesto facilitan esa revisión.
2. Reunir fotos **nuevas de espárrago en campo peruano**, con insectos visibles y recuadros revisados por el equipo. Reservar un conjunto de esas fotos que ninguno de los modelos use al entrenar.
3. Recuperar del compañero la procedencia de las 99 fotos de internet para documentar derechos y trazabilidad.
4. Reentrenar y comparar ambos modelos con el mismo conjunto de prueba independiente, incluyendo precisión por clase, falsos positivos y velocidad de video en el dispositivo de demostración.

SIGIA/SENASA sigue como fuente de consulta fitosanitaria en el MVP; sus registros no sustituyen imágenes de campo ni verifican las identificaciones del detector.
