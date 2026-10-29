# Mejoras UX/UI — Vigía Espárrago (AgriTech)

**Proyecto:** AgriTech — MVP de inspección fitosanitaria del espárrago  
**Autor de la contribución:** Favio Jiménez Sifuentes (`faviojimenezsifuentes-a11y`)  
**Repositorio original:** [jjjoaquo/AgriTech](https://github.com/jjjoaquo/AgriTech)  
**Repositorio de trabajo:** [faviojimenezsifuentes-a11y/AgriTech](https://github.com/faviojimenezsifuentes-a11y/AgriTech)  
**Rama:** `mejora-ux-mvp`  
**Pull Request:** [#5](https://github.com/jjjoaquo/AgriTech/pull/5)

## 1. Objetivo

Modernizar la **experiencia de usuario (UX) y la interfaz gráfica (UI)** del MVP Vigía Espárrago para facilitar su uso durante la inspección de cultivos, tanto en equipos de escritorio como en dispositivos móviles, sin alterar los modelos de detección.

## 2. Mejoras implementadas

### Interfaz y diseño visual
- Se consolidaron los estilos en una identidad visual coherente con el contexto agrícola: verde bosque, verde esmeralda, acentos suaves y superficies claras.
- Se mejoró la jerarquía tipográfica, los espaciados, bordes, sombras y estados visuales de botones y tarjetas.
- Se corrigió el problema en el estado vacío de la cámara: el texto **«Formatos de imagen compatibles · Máximo 10 MB»** heredaba reglas del icono y se mostraba desproporcionado.
- Se refinó el acabado visual «Premium 2.0» mediante estilos CSS, sin cambios de comportamiento.

### Navegación y flujo de trabajo
- Se organizaron las secciones en **Inspección, Resultados, Registrar, SENASA e Historial**.
- Se añadió un flujo visual de tres etapas: **Captura → Verifica → Registra**.
- Se mejoraron enlaces internos, foco de teclado y estados informativos.

### Captura y revisión de imágenes
- Se dio mayor protagonismo a la vista de fotografía/cámara, con controles agrupados y más claros.
- Se destacaron las acciones para **subir una fotografía** o **iniciar la cámara**.
- Se mejoró la presentación del estado vacío, del progreso del análisis y de mensajes de error o confirmación.
- La interfaz permite revisar detecciones y seleccionar recuadros mediante controles accesibles; se conservó la edición existente sobre el lienzo.

### Resultados e información de detección
- Se mejoró la lectura del número de detecciones, clases, niveles de confianza, alertas, velocidad observada y modelo utilizado.
- Se distinguieron visualmente las detecciones automáticas de las correcciones manuales.
- Los indicadores presentan los datos existentes del sistema, sin generar predicciones ni estadísticas ficticias.

### Registro, SENASA e historial
- Se reorganizó el formulario de hallazgos, con etiquetas claras, observaciones multilínea, validación del lote y mensajes cercanos al botón de guardado.
- Se mejoró la presentación de las consultas a SIGIA/SENASA y de las tablas desplazables.
- Se organizaron los elementos del historial con estados y detalles más fáciles de interpretar.

### Responsive y accesibilidad
- Se ajustó la interfaz para escritorio, tablet y celular, evitando desbordamientos horizontales.
- Se mejoraron tamaños de controles táctiles, legibilidad en dispositivos móviles, contraste y focos visibles.
- Se respetó la preferencia del usuario de reducir animaciones (`prefers-reduced-motion`).

## 3. Archivos involucrados

| Archivo | Cambios |
| --- | --- |
| `mvp/templates/index.html` | Estructura y semántica de la interfaz, navegación, controles y textos de ayuda. |
| `mvp/static/app.css` | Refactorización del diseño responsive, estados visuales y acabado Premium 2.0. |
| `mvp/static/app.js` | Interacciones de interfaz, accesibilidad y presentación de estados, manteniendo los contratos existentes. |

Este archivo Markdown documenta los cambios y no altera la aplicación.

## 4. Elementos que no se modificaron

El trabajo se limitó a la experiencia de usuario. **No se modificaron**:
- Pesos, arquitectura, entrenamiento ni datasets de YOLOv8 o YOLO26.
- Parámetros y lógica de inferencia.
- Endpoints y lógica del backend Flask.
- Base de datos, contratos API o procesamiento de imágenes.
- Integración funcional con SIGIA/SENASA.

## 5. Validación y límites

Según el reporte de la ejecución de Codex del rediseño principal (commit `7aa3fc7`):
- `python smoke_test.py`: aprobado; incluyó pruebas reales con los modelos disponibles, guardado y exportación.
- `node --check static/app.js` y `git diff --check`: aprobados.
- HTML e identificadores: comprobados.
- Verificaciones visuales en varios anchos entre 320 y 1920 px: sin desbordamiento horizontal reportado.
- Pruebas de interacción con cámara simulada, imágenes y respuestas controladas de SENASA: reportadas como correctas.
- Análisis automático con Axe 4.10.3: sin infracciones reportadas en las reglas evaluadas.

**Limitaciones:** no se probó una cámara física ni el servicio público real SIGIA en aquella ejecución. La prueba automática de accesibilidad no equivale a una auditoría WCAG completa. El refinamiento CSS posterior (commit `990efa7`) se publicó sin una nueva batería independiente de pruebas de navegador; se recomienda verificarlo visualmente antes de fusionar.

## 6. Historial de contribuciones destacadas

- [`7aa3fc7` — Consolidación del UX responsive y revisión](https://github.com/faviojimenezsifuentes-a11y/AgriTech/commit/7aa3fc731cd86af326b04fdd8cc5a30cc8b78c49)
- [`990efa7` — Refinamiento visual Premium 2.0](https://github.com/faviojimenezsifuentes-a11y/AgriTech/commit/990efa7f8601d9e9929e622e4e5af6a860c176d5)

## 7. Conclusión

El MVP cuenta con una interfaz más clara, moderna y adaptable para el flujo **capturar → revisar → registrar**, manteniendo las capacidades originales de análisis fitosanitario. La contribución está enfocada en **UX/UI** y no representa un cambio ni una mejora de rendimiento de los modelos YOLO.

> **Nota para integración:** revisar los cambios y ejecutar una prueba final del MVP antes de fusionar el [PR #5](https://github.com/jjjoaquo/AgriTech/pull/5) con `main`.