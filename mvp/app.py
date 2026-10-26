"""MVP de inspección de plagas de espárrago con YOLO y consulta SIGIA."""

from __future__ import annotations

import base64
import io
import json
import math
import sqlite3
import threading
import time
import uuid
import zipfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

import general_classifier
from senasa import MAPEO_PLAGAS, SIGIA_URL, consultar_sigia, extraer_productos

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "esparragos_yolov8n_v2.pt"
CANDIDATE_PATH = ROOT / "models" / "esparragos_yolo26n_semisupervisado.pt"
COMPARISON_PATH = ROOT / "training_runs" / "yolo26n_semisupervised_v3" / "external_holdout_comparison.json"
DATA_DIR = ROOT / "data"
IMAGE_DIR = DATA_DIR / "hallazgos"
PDF_DIR = DATA_DIR / "senasa"
DB_PATH = DATA_DIR / "hallazgos.sqlite3"
CLASS_NAMES = [
    "Chloridea virescens adulto", "Chloridea virescens larva",
    "Chrysodeixis includens adulto", "Chrysodeixis includens larva",
    "prodiplosis longifila larva", "spodoptera eridania adulto",
    "spodoptera eridania larva",
]
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_SIDE = 1600

_models: dict[str, object] = {}
_model_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def get_model(key: str = "baseline"):
    paths = {"baseline": MODEL_PATH, "candidate": CANDIDATE_PATH}
    if key not in paths:
        raise ValueError("Modelo no reconocido.")
    if key not in _models:
        from ultralytics import YOLO

        if not paths[key].is_file():
            raise FileNotFoundError(f"Falta el modelo: {paths[key]}")
        _models[key] = YOLO(str(paths[key]))
    return _models[key]


@contextmanager
def db_connection():
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db():
    with db_connection() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS hallazgos (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                sector TEXT NOT NULL,
                lat REAL,
                lon REAL,
                observations TEXT NOT NULL,
                detections_json TEXT NOT NULL,
                image_name TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in con.execute("PRAGMA table_info(hallazgos)")}
        if "status" not in columns:
            con.execute("ALTER TABLE hallazgos ADD COLUMN status TEXT NOT NULL DEFAULT 'pendiente'")
        if "reviewed_at" not in columns:
            con.execute("ALTER TABLE hallazgos ADD COLUMN reviewed_at TEXT")
        if "model_name" not in columns:
            con.execute("ALTER TABLE hallazgos ADD COLUMN model_name TEXT NOT NULL DEFAULT 'desconocido'")


def read_image(raw: bytes) -> Image.Image:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("La imagen debe pesar entre 1 byte y 10 MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("El archivo no es una imagen válida.") from exc
    if image.width < 32 or image.height < 32:
        raise ValueError("La imagen es demasiado pequeña.")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    return image


def predict_image(image: Image.Image, confidence: float, model_key: str = "baseline"):
    start = time.perf_counter()
    with _model_lock:
        result = get_model(model_key).predict(image, conf=confidence, imgsz=640, verbose=False)[0]
    detections = []
    for box in result.boxes:
        class_id = int(box.cls.item())
        detections.append({
            "class_id": class_id,
            "class_name": result.names[class_id],
            "confidence": round(float(box.conf.item()), 4),
            "xyxy": [round(float(v), 1) for v in box.xyxy[0].tolist()],
        })
    return {
        "width": image.width,
        "height": image.height,
        "detections": detections,
        "counts": dict(Counter(d["class_name"] for d in detections)),
        "inference_ms": round((time.perf_counter() - start) * 1000),
        "model": (MODEL_PATH if model_key == "baseline" else CANDIDATE_PATH).name,
    }


def create_app():
    app = Flask(__name__)
    # JSON data URLs inflate JPEG bytes by about one third.
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    init_db()

    @app.get("/")
    def portal():
        return render_template("portal.html", classifier_available=general_classifier.available(),
                               classifier_variant=general_classifier.MODEL_VARIANT)

    @app.get("/esparrago")
    def index():
        return render_template("index.html", sigia_url=SIGIA_URL, class_names=CLASS_NAMES,
                               candidate_available=CANDIDATE_PATH.is_file())

    @app.get("/general")
    def general():
        return render_template("general.html", classifier_available=general_classifier.available(),
                               image_size=general_classifier.IMAGE_SIZE,
                               classifier_variant=general_classifier.MODEL_VARIANT)

    @app.post("/api/classify")
    def classify():
        if not general_classifier.available():
            return jsonify(error="El clasificador general no está instalado en este servidor."), 503
        file = request.files.get("image")
        if file is None:
            return jsonify(error="Selecciona una fotografía de una plaga."), 400
        try:
            image = read_image(file.read(MAX_IMAGE_BYTES + 1))
            return jsonify(general_classifier.classify_image(image))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            app.logger.exception("Error durante la clasificación general")
            return jsonify(error="No se pudo clasificar la fotografía."), 500

    @app.get("/api/model-comparison")
    def model_comparison():
        if not COMPARISON_PATH.is_file():
            return jsonify(error="La comparación aún no está disponible."), 404
        report = json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))
        return jsonify({"evaluation": report["evaluation"],
                        "baseline": {key: report["baseline"][key] for key in ("hit_count", "total", "other_class_boxes", "median_inference_ms", "by_class")},
                        "candidate": {key: report["candidate"][key] for key in ("hit_count", "total", "other_class_boxes", "median_inference_ms", "by_class")}})

    @app.post("/api/detect")
    def detect():
        file = request.files.get("image")
        if file is None:
            return jsonify(error="Selecciona una imagen o activa la cámara."), 400
        try:
            confidence = float(request.form.get("confidence", "0.30"))
            if not 0.1 <= confidence <= 0.95:
                raise ValueError("La confianza debe estar entre 0.10 y 0.95.")
            model_key = request.form.get("model", "baseline")
            if model_key not in {"baseline", "candidate"}:
                raise ValueError("Modelo no reconocido.")
            if model_key == "candidate" and not CANDIDATE_PATH.is_file():
                raise ValueError("El modelo experimental aún no está disponible.")
            image = read_image(file.read(MAX_IMAGE_BYTES + 1))
            return jsonify(predict_image(image, confidence, model_key))
        except (TypeError, ValueError) as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            app.logger.exception("Error durante la inferencia")
            return jsonify(error="No se pudo procesar la imagen."), 500

    @app.post("/api/hallazgos")
    def save_finding():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(error="El hallazgo debe enviarse como objeto JSON."), 400
        sector = str(body.get("sector", "")).strip()[:100]
        status = body.get("status", "pendiente")
        model_name = body.get("model", "desconocido")
        if not sector:
            return jsonify(error="Indica el sector del cultivo."), 400
        if status not in {"confirmado", "pendiente", "falso_positivo"}:
            return jsonify(error="Estado de revisión no válido."), 400
        if model_name not in {"desconocido", MODEL_PATH.name, CANDIDATE_PATH.name}:
            return jsonify(error="Modelo del hallazgo no válido."), 400
        detections = body.get("detections")
        if not isinstance(detections, list) or len(detections) > 100:
            return jsonify(error="Lista de detecciones no válida."), 400
        if status == "confirmado" and (not body.get("reviewed") or not detections):
            return jsonify(error="Para confirmar, revisa la imagen, las clases y las cajas."), 400
        data_url = body.get("image", "")
        if not isinstance(data_url, str) or "," not in data_url:
            return jsonify(error="Falta la captura del hallazgo."), 400
        try:
            raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
            image = read_image(raw)
            lat = body.get("lat")
            lon = body.get("lon")
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
            if lat is not None and not -90 <= lat <= 90:
                raise ValueError()
            if lon is not None and not -180 <= lon <= 180:
                raise ValueError()
            cleaned = []
            for detection in detections:
                name = detection["class_name"]
                xyxy = detection["xyxy"]
                conf = float(detection["confidence"])
                if name not in CLASS_NAMES or not isinstance(xyxy, list) or len(xyxy) != 4 or not math.isfinite(conf) or not 0 <= conf <= 1:
                    raise ValueError()
                coords = [float(n) for n in xyxy]
                if not all(math.isfinite(n) for n in coords):
                    raise ValueError()
                cleaned.append({"class_name": name, "confidence": conf, "xyxy": coords,
                                "manual": detection.get("manual") is True})
            if any(not (0 <= d["xyxy"][0] < d["xyxy"][2] <= image.width and
                        0 <= d["xyxy"][1] < d["xyxy"][3] <= image.height)
                   for d in cleaned):
                raise ValueError()
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnidentifiedImageError, OSError):
            return jsonify(error="Los datos del hallazgo no son válidos."), 400
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        finding_id = uuid.uuid4().hex
        image_name = finding_id + ".jpg"
        image.save(IMAGE_DIR / image_name, "JPEG", quality=88)
        created_at = datetime.now(timezone.utc).isoformat()
        with db_connection() as con:
            con.execute(
                "INSERT INTO hallazgos (id,created_at,sector,lat,lon,observations,detections_json,image_name,status,reviewed_at,model_name) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (finding_id, created_at, sector, lat, lon,
                 str(body.get("observations", ""))[:500], json.dumps(cleaned), image_name, status,
                 created_at if status == "confirmado" else None, model_name),
            )
        return jsonify(id=finding_id, created_at=created_at), 201

    @app.get("/api/hallazgos")
    def list_findings():
        with db_connection() as con:
            rows = con.execute("SELECT * FROM hallazgos ORDER BY created_at DESC LIMIT 100").fetchall()
        return jsonify([{
            "id": row["id"], "created_at": row["created_at"],
            "sector": row["sector"], "lat": row["lat"], "lon": row["lon"],
            "status": row["status"], "reviewed_at": row["reviewed_at"], "model": row["model_name"],
            "observations": row["observations"],
            "detections": json.loads(row["detections_json"]),
            "image_url": f"/api/hallazgos/{row['id']}/imagen",
        } for row in rows])

    @app.get("/api/hallazgos/<finding_id>/imagen")
    def finding_image(finding_id):
        with db_connection() as con:
            row = con.execute("SELECT image_name FROM hallazgos WHERE id=?", (finding_id,)).fetchone()
        if row is None:
            abort(404)
        return send_file(IMAGE_DIR / row["image_name"], mimetype="image/jpeg")

    @app.get("/api/dataset/export")
    def export_confirmed():
        """Exporta ejemplos revisados; aún requieren curación y split independiente."""
        with db_connection() as con:
            rows = con.execute("SELECT * FROM hallazgos WHERE status='confirmado' AND reviewed_at IS NOT NULL ORDER BY created_at").fetchall()
        if not rows:
            return jsonify(error="No hay hallazgos confirmados para exportar."), 404
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("classes.txt", "\n".join(CLASS_NAMES) + "\n")
            z.writestr("README.txt", "Ejemplos confirmados por el supervisor. Revisar etiquetas y separar train/val/test por imagen original o sesión antes de entrenar.\n")
            manifest = []
            for row in rows:
                image_path = IMAGE_DIR / row["image_name"]
                with Image.open(image_path) as image:
                    width, height = image.size
                labels = []
                for detection in json.loads(row["detections_json"]):
                    x1, y1, x2, y2 = detection["xyxy"]
                    labels.append(f"{CLASS_NAMES.index(detection['class_name'])} {(x1+x2)/(2*width):.6f} {(y1+y2)/(2*height):.6f} {(x2-x1)/width:.6f} {(y2-y1)/height:.6f}")
                z.write(image_path, f"images/{row['id']}.jpg")
                z.writestr(f"labels/{row['id']}.txt", "\n".join(labels) + "\n")
                manifest.append({"id": row["id"], "created_at": row["created_at"],
                                 "reviewed_at": row["reviewed_at"], "sector": row["sector"],
                                 "model": row["model_name"], "detection_count": len(labels)})
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.seek(0)
        return send_file(archive, mimetype="application/zip", as_attachment=True,
                         download_name="hallazgos_confirmados_yolo.zip")

    @app.post("/api/senasa/consultas")
    def start_senasa_lookup():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(error="La consulta debe enviarse como objeto JSON."), 400
        name = body.get("class_name")
        if name not in MAPEO_PLAGAS:
            return jsonify(error="Clase no reconocida para SIGIA."), 400
        job_id = uuid.uuid4().hex
        with _jobs_lock:
            _jobs[job_id] = {"status": "running", "class_name": name}

        def worker():
            try:
                PDF_DIR.mkdir(parents=True, exist_ok=True)
                result = consultar_sigia(name, PDF_DIR / job_id)
                pages = len(PdfReader(str(result)).pages)
                products = extraer_productos(result)
                with _jobs_lock:
                    _jobs[job_id] = {"status": "success", "class_name": name,
                                     "pdf": str(result), "source": SIGIA_URL,
                                     "pages": pages, "crop": "Espárrago",
                                     "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                     "product_count": len(products), "products": products}
            except Exception as exc:
                app.logger.exception("Falló consulta a SIGIA")
                with _jobs_lock:
                    _jobs[job_id] = {"status": "error", "class_name": name,
                                     "message": str(exc)[:300], "source": SIGIA_URL}

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(job_id=job_id, status="running", source=SIGIA_URL), 202

    @app.get("/api/senasa/consultas/<job_id>")
    def senasa_status(job_id):
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            abort(404)
        result = {key: value for key, value in job.items() if key not in {"pdf", "products"}}
        if job["status"] == "success":
            result["pdf_url"] = f"/api/senasa/consultas/{job_id}/pdf"
        return jsonify(result)

    @app.get("/api/senasa/consultas/<job_id>/pdf")
    def senasa_pdf(job_id):
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None or job["status"] != "success":
            abort(404)
        return send_file(job["pdf"], mimetype="application/pdf", as_attachment=False)

    @app.get("/api/senasa/consultas/<job_id>/productos")
    def senasa_products(job_id):
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None or job["status"] != "success":
            abort(404)
        return jsonify(job["products"])

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
