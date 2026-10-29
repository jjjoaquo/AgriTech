# Mejora del detector para inspección de espárrago

## Decisión de diseño

El público principal son inspectores de campo y supervisores agronómicos del espárrago en Perú. El detector debe mostrar cajas y datos con baja latencia, permitir confirmar o corregir cada hallazgo y registrar su procedencia. SIGIA de SENASA se consulta por separado como fuente oficial sobre plagas y registros; sus datos no son etiquetas de imágenes ni validan las cajas del modelo.

La clase *Prodiplosis longifila* merece seguimiento de campo: aparece entre las plagas de interés del [protocolo fitosanitario de exportación de espárrago de SENASA](https://repositorio.senasa.gob.pe/items/24995e91-e2df-4427-a719-ab4c551d7c21). No se encontraron fotografías externas con licencia CC0 o CC BY y anotación de larva en la búsqueda de iNaturalist de este experimento, así que **no se medirá su generalización externa** con los resultados actuales.

## Datos y control de fugas

- Se conservan las siete clases y su orden del peso V2 y de la exportación YOLOv8 v1 del compañero `alonmiorro-gmail-com`.
- La versión de Roboflow contiene 99 fotos originales y 297 variantes aumentadas. Para el entrenamiento final, 249 variantes van a entrenamiento y 48 a validación, siempre agrupadas por original. La partición anterior llamada `test` pasó a entrenamiento; **no se reportará como prueba**.
- Se añadieron 44 fotos externas de iNaturalist a entrenamiento. V2 propuso las cajas, filtradas por clase de la fotografía, confianza ≥ 0,35 y área plausible. Son **pseudoetiquetas sin revisión humana**, no verdad de referencia. El archivo `training_data/semisupervised_v2/provenance.json` guarda foto, licencia, atribución, decisión y conjunto.
- Otras 32 fotos externas, de observaciones diferentes, se reservaron antes de entrenar para comparar modelos. Se comprobó que no hay duplicados visuales muy cercanos frente a la exportación Roboflow ni las 64 candidatas externas de entrenamiento mediante dHash (distancia ≤ 5). Esta prueba solo puede decir si aparece la clase esperada; carece de cajas revisadas y no confirma hospedero espárrago.
- Hay además 24 fotografías licenciadas de *Asparagus officinalis* en `dataset_candidates/asparagus_context/`, con atribución y observaciones diferentes. Sirven para contar alertas en imágenes del cultivo; **no están verificadas como libres de plagas** y no entran al entrenamiento.
- Las 44 fotos usadas tienen licencias 39 CC BY y 5 CC0. Se conserva la atribución en el manifiesto. Las fotos originales del compañero aún requieren reconstruir sus fuentes y licencias.

## Entrenamiento

Se inicia desde el YOLO26n piloto ya entrenado para las siete clases. El ajuste posterior usa AdamW, tasa inicial 0,0005, imagen 512 px, lote 8, mosaico 0,5, sin MixUp ni Copy Paste, hasta 15 épocas con parada temprana. [Ultralytics recomienda suavizar los aumentos para conjuntos pequeños](https://docs.ultralytics.com/guides/yolo26-training-recipe/#when-to-adjust-yolo26-hyperparameters); los parámetros y el historial exactos quedan en `training_runs/yolo26n_semisupervised_v3/args.yaml` y `results.csv`.

Los scripts reproducibles son `python prepare_semisupervised.py`, `python prepare_training_v2.py` y `python train_second_yolo.py`, en ese orden y en una carpeta limpia. Los dos primeros se niegan a sobrescribir particiones existentes para conservar la prueba. La comparación final se guarda en `training_runs/yolo26n_semisupervised_v3/external_holdout_comparison.json`.

## Umbral de inspección

El umbral inicial de V2 bajó de 45 % a **30 %** para priorizar la detección temprana en la pantalla de inspección. Se eligió con las **64 fotos externas de desarrollo**, sin tocar las 32 reservadas: a 45 % apareció la clase esperada en 41/64 fotos y hubo 8 cajas de otras clases; a 30 %, apareció en 48/64 con 12 cajas de otras clases. A 25 % se obtuvieron los mismos conteos que a 30 %. El reporte está en `training_runs/confidence_development.json` y el control de la pantalla permite ajustar el umbral por inspección. Estas cajas adicionales no son necesariamente falsos positivos, porque no hay anotación exhaustiva de todas las especies en cada foto.

## Regla de despliegue

El entrenamiento terminó por parada temprana tras 13 épocas; el mejor peso corresponde a la época 7. En la validación agrupada de Roboflow, el nuevo YOLO26n obtuvo mAP50 **0,605** y mAP50-95 **0,383**, frente a **0,494** y **0,305** del piloto anterior. Esa validación **no** es una comparación válida frente a V2, que probablemente vio sus fotos originales.

| Prueba externa reservada (32 fotos, confianza 25 %, 512 px) | V2 | YOLO26n ajustado |
| --- | ---: | ---: |
| Fotos con la clase esperada detectada | **25/32** | 6/32 |
| Cajas de otras clases | 1 | 1 |
| Mediana de tiempo por foto en esta PC | 96,6 ms | 90,0 ms |

El YOLO26n ajustado omitió todas las fotos externas de *Chloridea virescens* adulto (0/6) y *Spodoptera eridania* larva (0/6); V2 detectó 6/6 y 3/6 respectivamente. No hubo fotos externas de *Prodiplosis longifila* larva. En 24 fotos no revisadas de la planta de espárrago, V2 produjo 4 cajas en 2 fotos y YOLO26 produjo 14 cajas en 1; **no se puede llamar falsos positivos a esas cajas sin revisar las imágenes**. Estos resultados muestran que mejorar la validación interna no garantizó generalización a fotos nuevas. La falta de imágenes de campo y la dependencia de pseudoetiquetas son explicaciones plausibles, aún no demostradas.

La reducción del umbral V2 a 30 % también se validó en las 32 fotos externas reservadas, después de elegirlo en desarrollo: apareció la clase esperada en **24/32** fotos frente a **21/32** al 45 %, con 4 cajas de otras clases en ambos umbrales, a 640 px. Esta es la mejora operativa que sí se incorporó al flujo de inspección. La comparación de modelos anterior usa 25 %, 512 px; por eso sus conteos no deben mezclarse con los de esta prueba de umbral.

El peso V2 sigue como detector predeterminado hasta que un conjunto nuevo de **fotos de espárrago en campo peruano**, con cajas y clases revisadas por el equipo, permita comparar mAP por clase, falsos positivos y FPS en el dispositivo real. El YOLO26 ajustado se puede seleccionar **solo para comparar fotografías**, no para la cámara; el panel de evidencia informa exactamente qué midió la prueba externa.

Las capturas confirmadas en el MVP pueden exportarse en formato YOLO con manifiesto de modelo, sector y fecha de revisión. Esa exportación facilita el siguiente ciclo de anotación, pero requiere auditoría de un especialista antes de entrenar.

Para la siguiente prueba, recolectar fotos y video de varios sectores, días, distancias y condiciones de luz de **espárrago peruano**, incluyendo plantas sin las siete plagas objetivo y otras especies que puedan confundirse. Separar por sesión o parcela antes de cualquier aumento, reservar una prueba que no se use para escoger umbrales y revisar todas las cajas y ausencias de plaga. Comparar ambos pesos a la misma resolución y confianza, con resultados por clase, casos omitidos, alertas erróneas y FPS del equipo que se usará en la demostración.
