# Evaluación IP102 balanceado, 27 de octubre de 2026

El entrenamiento de ResNet-152 terminó en Google Colab con una GPU Tesla T4 (2 épocas de cabeza y 4 de ajuste de la última capa). Las métricas comparan ambos pesos sobre las mismas 22 619 imágenes de prueba, con imágenes de 256 × 256 píxeles. El conjunto de entrenamiento contiene 68 996 imágenes, de las cuales 32 191 son sintéticas.

| Modelo | F1 macro | Balanced accuracy | Exactitud |
| --- | ---: | ---: | ---: |
| Base de Alonso | 0,626965 | 0,637353 | 0,695964 |
| Candidato balanceado | 0,617411 | 0,635847 | 0,692383 |

El candidato reduce el F1 macro en 0,009554, la balanced accuracy en 0,001506 y la exactitud en 0,003581. El recall mejora en 41 clases, empeora en 52 y permanece igual en 9. Entre los descensos con más de 100 imágenes de prueba están *wheat sawfly* (−0,1275; 102 imágenes), *white backed plant hopper* (−0,0858; 268), *black cutworm* (−0,0817; 257) y *Trialeurodes vaporariorum* (−0,0769; 208). Estas cifras no demuestran por sí solas la causa de la caída. La proporción de imágenes sintéticas (46,7 % del entrenamiento) merece una prueba controlada con una proporción menor y el mismo conjunto de validación y prueba.

**Decisión:** conservar el modelo base en el sitio. El candidato no supera el criterio de F1 macro acordado y tampoco mejora las otras dos métricas globales. El informe completo, con recall y tamaño de cada clase, está en `comparison.json`.

Auditoría posterior del ZIP de Alonso: las 7 508 imágenes de validación y las 22 619 de prueba son reales; las 32 191 sintéticas están solo en entrenamiento. Una comparación SHA-256 de todas las imágenes encontró dos duplicados exactos entre entrenamiento y prueba (`train/56/40410.jpg` = `test/56/40432.jpg`; `train/92/65553.jpg` = `test/92/66152.jpg`). Son 2 de 22 619 imágenes de prueba y no explican por sí solos la diferencia global, pero deben excluirse del entrenamiento en la próxima evaluación para mantener la separación de conjuntos.

Verificación de artefactos: dataset SHA-256 `1728e1d3989b4f2a0bf5994567680a35fc5472968ec745ab35ba9307e9c1fcc5`; checkpoint original de Alonso SHA-256 `a3cd065ff991c294db0f69e1f1535da85d152e565ad516bc6b7bc6114bee2312`; peso candidato generado en Colab SHA-256 `5246f5010a81ffd1ea1c59096341f8bb90138c1985b77220d2b3277dd2f63b8f` (234 103 448 bytes). El peso candidato permanece en la sesión de Colab y no se instaló en producción.
