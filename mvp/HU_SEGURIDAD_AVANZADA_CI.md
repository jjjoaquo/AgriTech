# HU — Seguridad avanzada y CI de 8 etapas

**Historia:** Como integrante del equipo AgriTech, quiero ampliar las protecciones de la aplicación y el pipeline de integración continua para identificar vulnerabilidades y regresiones antes de integrar cambios a `main`.

## Cambios implementados

### 1. Protección HTTP adicional

- `Cross-Origin-Resource-Policy: same-origin` en la ruta `/api/hallazgos/<id>/imagen`: impide que otros orígenes carguen las imágenes privadas como recursos incrustados en navegadores compatibles. **No sustituye** la autorización de usuario mediante `owner_id`.
- `Permissions-Policy`: se mantienen cámara y geolocalización del propio sitio para el funcionamiento de AgriTech; se deshabilitan micrófono, pagos y USB.
- Se mantienen controles previos de CSRF, cookies, clickjacking, HSTS, autenticación y aislamiento de hallazgos.

### 2. Pruebas de seguridad ampliadas

Archivo `mvp/tests/test_seguridad_avanzada.py`:

1. Cinco contraseñas incorrectas activan el bloqueo temporal de cuenta y la contraseña correcta tampoco evita el bloqueo.
2. Los recursos privados incluyen `Cache-Control: no-store` y cabeceras defensivas.
3. En producción se exige `AGRI_SECRET_KEY` y la cookie tiene `Secure`, `HttpOnly` y `SameSite=Lax`.
4. Las solicitudes de más de 16 MiB reciben `413` si el usuario está autenticado con CSRF válido.
5. Las cabeceras `Permissions-Policy` y `Cross-Origin-Resource-Policy` están presentes.

Estas pruebas usan SQLite temporal y no acceden al modelo YOLO.

### 3. Pipeline de ocho trabajos

Archivo `.github/workflows/favio-ci-seguridad.yml`:

1. **Calidad y sintaxis** — Python, Flake8, JavaScript.
2. **Pruebas HU y UX**.
3. **Pruebas de seguridad** — sesiones, CSRF, permisos de fotos y nuevos escenarios de abuso.
4. **Integración Flask**.
5. **Playwright / Chromium**.
6. **Bandit** — análisis estático de archivos Python, bloquea alertas de severidad y confianza altas. Artefacto `favio-evidencia-sast`.
7. **pip-audit** — audita versiones de Flask, Pillow, pypdf, PyYAML y sus dependencias instaladas en un entorno virtual aislado; falla ante vulnerabilidades conocidas. Artefacto `favio-evidencia-dependencias`.
8. **Puerta de calidad** — requiere que los siete trabajos anteriores estén en estado `success`.

Se conservan los demás workflows de Alonso y Michelle sin modificaciones.

**Alcance de pip-audit:** esta etapa analiza las dependencias del entorno de servidor que se instalan para las pruebas, **no la totalidad** de las dependencias del proyecto de entrenamiento (por ejemplo, ultralytics y sus componentes). Como siguiente tarea, el equipo puede fijar un lockfile completo y ampliar el escaneo a toda la cadena de dependencias.

## Evidencia / validación pendiente

Las nuevas comprobaciones deben verificarse en la ejecución de GitHub Actions de esta rama y en su Pull Request. No declarar esta HU terminada sin comprobar las ocho etapas verdes. No hacer merge automático si aparecen hallazgos de Bandit o pip-audit: revisar vulnerabilidades reales y actualizar el código o las dependencias afectadas.

Enlaces recomendados de evidencia:
- Pull Request de esta rama hacia `jjjoaquo/AgriTech:main`.
- Ejecución `AgriTech | Favio | CI y Seguridad` en Actions.
- Artefactos `favio-evidencia-seguridad`, `favio-evidencia-sast`, `favio-evidencia-dependencias`.

**Criterios de aceptación:** protección cross-origin y política de permisos; cinco pruebas nuevas; trabajos Bandit y pip-audit; gate de ocho etapas, reportes descargables; CI exitoso; revisión del equipo antes del merge.
