# Pipeline de Michelle: trazabilidad y experiencia visual

El workflow [Pruebas AgriTech - Michelle](../../.github/workflows/tests_michelle.yml) se ejecuta en `main`, en pull requests y manualmente. Sus dos trabajos independientes permiten distinguir la evidencia del commit de la validación del producto.

## Evidencia de GitHub y Jira

El trabajo **Evidencia de commit y Jira** guarda el SHA, autor, fecha ISO y título del commit en `trazabilidad-github.json` y `trazabilidad-github.md`. Exige un identificador `SCRUM-n` en los commits directos; un merge commit conserva la relación a través de su PR. El resultado aparece también en el resumen de GitHub Actions. Este trabajo no modifica Jira ni asigna fechas de finalización en nombre de una persona.

## Validación funcional y visual

El trabajo **Pruebas funcionales y UX visual** comprueba sintaxis JavaScript, ejecuta la suite unitaria, verifica las rutas públicas y los recursos visuales, y ejecuta el smoke test de integración. Conserva los resultados como artefacto descargable. La prueba visual abre las páginas desde Flask y comprueba que el video y las imágenes se sirven; las capturas de navegador del pipeline de Favio complementan esta evidencia.

## Relación con el burndown de Jira

La línea base del burndown es el trabajo comprometido al iniciar el sprint. Jira dibuja el avance a partir de cambios reales de estado y de alcance. Un commit o una prueba exitosa **no mueve por sí solo** la curva: la historia debe estar en el sprint correcto y pasar a `Done` tras la revisión, con una fecha coherente. Si las historias se cerraron después del intervalo planificado, no se deben alterar retrospectivamente las fechas para forzar una curva ideal. En Sprint Review se registra la diferencia entre línea base, alcance añadido y trabajo realmente terminado.

Para la sustentación individual, descargar los artefactos del run correspondiente y cotejar el identificador `SCRUM-n`, el SHA y la fecha con la historia en Jira y su reporte de burndown.
