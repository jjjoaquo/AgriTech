# Exportación YOLOv8 del proyecto Roboflow del compañero

Fuente: [My First Project v1](https://universe.roboflow.com/alonmiorro-gmail-com/my-first-project-1rsof/dataset/1), licencia del proyecto CC BY 4.0. Descargada con sesión de Roboflow el 12 de octubre de 2026.
Como las fotos originales se recopilaron de varias páginas de internet, la
licencia del proyecto de Roboflow **no verifica por sí sola los derechos de
cada foto de origen**. Falta el registro de procedencia que conservó el equipo.

El ZIP exportado tiene 297 imágenes y 297 archivos de etiquetas, todos en `train/`. Los nombres revelan **99 fotos originales, tres variantes aumentadas por foto**. El `data.yaml` de la versión exportada enumera siete clases, en el mismo orden del peso YOLOv8 V2. La página de Roboflow enumera nueve clases porque incluye `object` y `prodiplosis longifila`, que no están en el `data.yaml` exportado.

| Clase | Originales | Variantes exportadas |
| --- | ---: | ---: |
| Chloridea virescens adulto | 10 | 30 |
| Chloridea virescens larva | 21 | 63 |
| Chrysodeixis includens adulto | 10 | 30 |
| Chrysodeixis includens larva | 20 | 60 |
| Prodiplosis longifila larva | 13 | 39 |
| Spodoptera eridania adulto | 7 | 21 |
| Spodoptera eridania larva | 18 | 54 |

`review/` contiene láminas con una variante y sus recuadros por cada original. Algunas fotos muestran plagas sobre tomate u otras plantas, o fondos de estudio. La presencia de espárrago no está verificada para todo el dataset.

`prepare_roboflow_split.py` crea `training_data/roboflow_v1_grouped/` con particiones separadas **por foto original**; todas sus variantes permanecen juntas. Las particiones creadas sirven para entrenar y revisar un YOLO26 experimental. **No son una prueba independiente frente al peso V2:** el modelo V2 probablemente se entrenó con estos mismos originales. Una comparación definitiva requiere fotos nuevas del cultivo de espárrago, con recuadros revisados, que ninguno de los dos modelos haya usado para entrenar.
