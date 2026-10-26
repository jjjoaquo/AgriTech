# Despliegue del MVP

El MVP está publicado en **https://esparragos.comextech.es**. El DNS requiere un registro **A** con nombre `esparragos` y valor `76.13.8.33`. El sitio usa HTTPS con Let's Encrypt y se abre sin usuario ni contraseña.

En el VPS Ubuntu, la aplicación está en `/opt/esparragos`, escucha solo en `127.0.0.1:8016` mediante `esparragos.service` y se publica por Nginx. Los hallazgos y PDF se guardan en `/opt/esparragos/data`; **respaldar esa carpeta antes de reemplazar una versión**. El usuario de servicio es `www-data`. El proceso usa PyTorch para CPU que ya estaba instalado en el VPS, una sola instancia de Gunicorn y dos hilos. El paquete de producción se crea con `python deploy/build_bundle.py` y excluye datasets, ejecuciones de entrenamiento y datos de usuarios.

## Comprobaciones

```bash
systemctl status esparragos.service
journalctl -u esparragos.service -n 100 --no-pager
nginx -t
certbot certificates
```

Se comprobó desde el VPS una foto con V2 y con YOLO26n, la comparación de modelos y una consulta completa a SIGIA que devolvió un PDF y su tabla. En cinco solicitudes sucesivas sobre una foto de prueba, la primera carga del modelo tardó varios segundos y la mediana de las cinco solicitudes fue 178 ms; esta cifra depende de la carga del VPS y no equivale a FPS garantizados de cámara.

El historial, las imágenes y las ubicaciones que se registren en el MVP son accesibles para cualquier visitante del sitio público. Actualmente no hay hallazgos guardados. El certificado se renueva con Certbot. Si SIGIA cambia, revisar `senasa.py`: es una automatización del portal público, no una API oficial.

## Portal multicultivo y peso ResNet

La raíz del sitio ahora presenta dos módulos: `/general` clasifica fotografías entre 102 clases con ResNet‑152, y `/esparrago` conserva las cajas de YOLO, la cámara y la consulta SIGIA del cultivo de espárrago. El peso ResNet baseline lo proporcionó Alonso y se instala como `models/best_resnet152_baseline.safetensors` después de extraer solo el `model_state_dict` del checkpoint `.pth`; no se publica en GitHub. `deploy/build_bundle.py` incorpora el archivo convertido si está presente. El VPS dispone de `safetensors` en el entorno actual.

El clasificador usa 224 × 224 px como valor operativo porque el notebook recibido no define `IMG_SIZE`. La normalización sí coincide con el código de entrenamiento. Consulte [CLASIFICADOR_GENERAL.md](../CLASIFICADOR_GENERAL.md) para la investigación, los límites y las métricas disponibles. El clasificador no dibuja recuadros ni reemplaza a YOLO para espárrago. Una prueba de API confirma que carga y devuelve tres clases; no mide precisión agronómica.
