# Fotografías candidatas para el detector de plagas de espárrago

Esta exportación contiene **96 fotografías de las especies y etapas que usa el
modelo del proyecto**, obtenidas de observaciones de investigación de
iNaturalist. Solo se aceptaron fotos con licencia CC0 o CC BY y lado mínimo de
400 píxeles. `manifest.csv` conserva el enlace a cada observación, autor,
atribución, licencia, taxón, etapa y hash de la imagen.

| Clase | Fotos |
| --- | ---: |
| Chloridea virescens adulto | 18 |
| Chloridea virescens larva | 18 |
| Chrysodeixis includens adulto | 18 |
| Chrysodeixis includens larva | 6 |
| Prodiplosis longifila larva | 0 |
| Spodoptera eridania adulto | 18 |
| Spodoptera eridania larva | 18 |

**Uso en el proyecto:** son fotos de referencia y candidatas a revisión, no
un dataset YOLO listo para entrenar. La observación confirma una identificación
comunitaria de especie y etapa, pero no la posición de cada insecto en la foto.
Además, el hospedero espárrago no está verificado en estas observaciones; en
las láminas se ven otros cultivos y plantas. Las fotos de campo del equipo en
espárrago peruano deben ser la base de la prueba independiente.

`review/proposed_labels/` contiene recuadros sugeridos por el modelo V2 para
acelerar el trabajo de etiquetado. **No son etiquetas verificadas**. Por
ejemplo, el modelo sugirió cinco cajas de *Prodiplosis* en fotos de otras
clases: no se deben incorporar sin inspección. `review/sheet_class_*` permite
revisar visualmente fotos y propuestas.

Antes de reentrenar: comprobar especie y etapa, descartar fotos fuera de foco o
sin insecto identificable, corregir todas las cajas y clases, documentar el
contexto de cultivo, y separar imágenes originales por fuente entre
entrenamiento, validación y prueba **antes** de aplicar aumentos. La versión
pública del [Roboflow del compañero](https://universe.roboflow.com/alonmiorro-gmail-com/my-first-project-1rsof/dataset/1)
incluye 99 imágenes originales y cajas para *Prodiplosis*, pero su exportación
requiere inicio de sesión. Esa versión tiene nueve clases y una división de
100 % entrenamiento; hay que normalizarla a las siete clases del modelo y
crear una prueba independiente sin copias aumentadas.

Fuente: [API de iNaturalist](https://www.inaturalist.org/api).
La referencia a SENASA/SIGIA del MVP sirve para contexto fitosanitario y
consulta de información pública, no como prueba de que estas imágenes sean de
espárrago ni como validación de la identificación visual.
