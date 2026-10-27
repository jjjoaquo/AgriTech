# Trazabilidad de Jira y GitHub

Proyecto Jira: [SCRUM](https://michaelmontoyarocca.atlassian.net/jira/software/projects/SCRUM/boards/1/backlog). Repositorio: [AgriTech](https://github.com/jjjoaquo/AgriTech).

## Convención para trabajo nuevo

Cada rama, commit y PR debe empezar por la clave de la historia y usar su título de Jira. Ejemplo:

```text
SCRUM-11 HU2 – Identificar plaga con YOLOv8
```

El cuerpo del commit o la descripción del PR debe explicar el cambio y la prueba realizada. Si un cambio cubre varias historias, se conserva una clave principal en el título y se citan las demás en el cuerpo. Cada integrante hace sus propios commits con su propia identidad; no se cambian los autores ni los SHA de los commits publicados para simular una distribución distinta.

## Trabajo anterior: correspondencia documentada

Los títulos originales anteriores a esta convención se mantienen por integridad del historial. Estas correspondencias describen contenido observado en el repositorio; no indican que una historia esté terminada ni cambian su autor.

| Commit | Autor registrado | Relación con Jira |
| --- | --- | --- |
| `2671ee2` Integrar MVP de espárrago | Michelle Montoya Rocca | SCRUM-11 identificación con YOLO; SCRUM-13 traducción; flujo base del portal |
| `a586d68` Desarrollo de nuevo modelo | Alonso | SCRUM-24 entrenamiento; SCRUM-25 comparación de métricas (trabajo de modelo, pendiente de validar el alcance exacto de ambos criterios) |
| `6ce752e` Subida de archivos | joaquincallupe | Aporte al repositorio; revisar archivo por archivo antes de vincularlo a una historia funcional |
| `9fdbde3` MEJORAS.md | joaquincallupe | Propuestas de mejora; no equivale a implementación de una historia |
| `bfdf7d8`, `3f34a2e`, `b551067`, `def19fa`, `296d276`, `7aa3fc7`, `990efa7`, `88a5604` | faviojimenezsifuentes-a11y | UX responsive, navegación guiada, accesibilidad, estados y documentación; relacionado con la épica web y con SCRUM-19 donde corresponda |
| `36f8db3` Portal multicultivo y ResNet | Michelle Montoya Rocca | Ampliación de alcance multicultivo; crear o vincular historia específica antes de cerrar trabajo en Jira |
| `47b1d01`, `519a7e6`, `51176d3` | Michelle Montoya Rocca | Auditoría de duplicados IP102; evidencia para SCRUM-25 y futuras historias de calidad de datos |

## Historias añadidas por la retroalimentación docente

- SCRUM-83: vinculación Jira y GitHub.
- SCRUM-84: registro e inicio de sesión de agricultores.
- SCRUM-85: roles y superadministración.
- SCRUM-86: inspecciones asociadas a agricultor y parcela.
- SCRUM-87: dashboard del agricultor.
- SCRUM-88: visualización 3D de parcelas y focos.
- SCRUM-89: página de planes y suscripciones.
- SCRUM-90: límites de uso según el plan.

Las historias de producto pendientes deben permanecer en **To Do** hasta que haya implementación y evidencia. La página de planes no implica cobrar: una pasarela de pago requiere una historia y pruebas separadas.

## Verificación de la integración

Después de instalar y autorizar GitHub for Atlassian para el repositorio, comprobar en SCRUM-83 que un commit nuevo con su clave aparece en la sección **Development**. La instalación de la app en Jira por sí sola no demuestra que el repositorio ya esté conectado.
