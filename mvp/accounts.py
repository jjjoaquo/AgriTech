"""Cuentas, planes y vistas privadas del MVP AgriTech."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone

import click
from flask import abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


PLANS = {
    "gratis": {"name": "Explorar", "limit": 10},
    "pro": {"name": "Campo Pro", "limit": 200},
    "cooperativa": {"name": "Cooperativa", "limit": 1000},
}
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DUMMY_HASH = generate_password_hash("dummy-password-that-is-never-used")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_tables(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('agricultor','superadmin')),
        plan TEXT NOT NULL CHECK(plan IN ('gratis','pro','cooperativa')),
        active INTEGER NOT NULL DEFAULT 1,
        failed_logins INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        setup_token_hash TEXT,
        setup_expires TEXT,
        created_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS plan_requests (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        plan TEXT NOT NULL CHECK(plan IN ('pro','cooperativa')),
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pendiente' CHECK(status IN ('pendiente','aprobado','rechazado')),
        created_at TEXT NOT NULL,
        decided_at TEXT
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_plan_requests_user ON plan_requests(user_id, created_at)")


class Accounts:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def current_user(self):
        if not hasattr(g, "agri_user"):
            user_id = session.get("user_id")
            if user_id:
                with self.db_connection() as con:
                    row = con.execute("SELECT id,name,email,role,plan FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
                g.agri_user = dict(row) if row else None
                if row is None:
                    session.clear()
            else:
                g.agri_user = None
        return g.agri_user

    @staticmethod
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    def require_csrf(self):
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(str(supplied), str(expected)):
            abort(400, description="Solicitud no válida. Recarga la página e inténtalo de nuevo.")

    def require_page_user(self):
        user = self.current_user()
        if user is None:
            return None, redirect(url_for("login", next=request.path))
        return user, None

    def require_api_user(self):
        user = self.current_user()
        if user is None:
            return None, (jsonify(error="Inicia sesión para acceder a tus datos."), 401)
        return user, None

    def usage(self, con, user_id: str) -> int:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return con.execute(
            "SELECT COUNT(*) FROM hallazgos WHERE owner_id=? AND substr(created_at,1,7)=?",
            (user_id, month),
        ).fetchone()[0]

    def install(self, app):
        @app.context_processor
        def template_accounts():
            return {"agri_user": self.current_user(), "csrf_token": self.csrf_token, "plans": PLANS}

        @app.after_request
        def private_headers(response):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            # Previene clickjacking: la aplicación no debe incrustarse en iframes externos.
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
            # Limitar el acceso a recursos de fotos privadas desde sitios externos.
            if request.path.startswith("/api/hallazgos/") and request.path.endswith("/imagen"):
                response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
            # Mantener cámara y geolocalización propias, deshabilitar APIs no usadas.
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(self), geolocation=(self), microphone=(), payment=(), usb=()",
            )
            # HSTS solo en producción: nunca imponer HTTPS en el entorno local de pruebas.
            if os.environ.get("AGRI_ENV") == "production":
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
            if request.path.startswith(("/dashboard", "/admin", "/api/hallazgos", "/api/dataset", "/api/cultivo")):
                response.headers["Cache-Control"] = "private, no-store"
            return response

        @app.get("/registro")
        def register_page():
            if self.current_user():
                return redirect(url_for("dashboard"))
            return render_template("auth.html", mode="registro")

        @app.post("/registro")
        def register():
            self.require_csrf()
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not 2 <= len(name) <= 100 or not _EMAIL.fullmatch(email) or len(email) > 254:
                flash("Revisa el nombre y el correo electrónico.", "error")
                return redirect(url_for("register_page"))
            if not 12 <= len(password) <= 128:
                flash("La contraseña debe tener entre 12 y 128 caracteres.", "error")
                return redirect(url_for("register_page"))
            user_id = secrets.token_hex(16)
            try:
                with self.db_connection() as con:
                    con.execute(
                        "INSERT INTO users(id,name,email,password_hash,role,plan,created_at) VALUES(?,?,?,?,?,?,?)",
                        (user_id, name, email, generate_password_hash(password), "agricultor", "gratis", utc_now()),
                    )
            except sqlite3.IntegrityError:
                flash("No se pudo crear la cuenta con ese correo. Si ya tienes una, inicia sesión.", "error")
                return redirect(url_for("register_page"))
            session.clear()
            session["user_id"] = user_id
            session.permanent = True
            flash("Cuenta creada. Tus nuevas inspecciones serán privadas.", "success")
            return redirect(url_for("dashboard"))

        @app.get("/login")
        def login_page():
            if self.current_user():
                return redirect(url_for("dashboard"))
            return render_template("auth.html", mode="login")

        @app.post("/login")
        def login():
            self.require_csrf()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            with self.db_connection() as con:
                row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                locked = bool(row and row["locked_until"] and row["locked_until"] > utc_now())
                valid = check_password_hash(row["password_hash"] if row and row["password_hash"] else _DUMMY_HASH, password)
                if not row or not row["active"] or locked or not valid:
                    if row and not locked:
                        count = int(row["failed_logins"]) + 1
                        until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat() if count >= 5 else None
                        con.execute("UPDATE users SET failed_logins=?,locked_until=? WHERE id=?", (count, until, row["id"]))
                    flash("No se pudo iniciar sesión. Revisa tus datos o espera 15 minutos.", "error")
                    return redirect(url_for("login_page"))
                con.execute("UPDATE users SET failed_logins=0,locked_until=NULL WHERE id=?", (row["id"],))
            session.clear()
            session["user_id"] = row["id"]
            session.permanent = True
            next_path = request.form.get("next", "")
            # Evitar open redirects: algunos navegadores interpretan /\\destino como //destino.
            decoded_next = unquote(next_path)
            safe_local_path = (
                decoded_next.startswith("/")
                and not decoded_next.startswith("//")
                and "\\" not in decoded_next
                and not any(ord(character) < 32 or ord(character) == 127 for character in decoded_next)
            )
            return redirect(next_path if safe_local_path else url_for("dashboard"))

        @app.post("/logout")
        def logout():
            self.require_csrf()
            session.clear()
            return redirect(url_for("portal"))

        @app.get("/planes")
        def plans_page():
            return render_template("plans.html")

        @app.post("/planes/solicitar")
        def request_plan():
            user, response = self.require_page_user()
            if response:
                return response
            self.require_csrf()
            plan = request.form.get("plan", "")
            note = request.form.get("note", "").strip()[:500]
            if plan not in ("pro", "cooperativa"):
                abort(400)
            with self.db_connection() as con:
                pending = con.execute("SELECT 1 FROM plan_requests WHERE user_id=? AND plan=? AND status='pendiente'", (user["id"], plan)).fetchone()
                if not pending:
                    con.execute("INSERT INTO plan_requests(id,user_id,plan,note,created_at) VALUES(?,?,?,?,?)",
                                (secrets.token_hex(16), user["id"], plan, note, utc_now()))
            flash("Solicitud registrada. El equipo revisará tu plan; aún no se ha realizado ningún cobro.", "success")
            return redirect(url_for("dashboard"))

        @app.get("/dashboard")
        def dashboard():
            user, response = self.require_page_user()
            if response:
                return response
            if user["role"] == "superadmin":
                return redirect(url_for("admin_dashboard"))
            with self.db_connection() as con:
                rows = con.execute("SELECT id,created_at,sector,status,detections_json FROM hallazgos WHERE owner_id=? ORDER BY created_at DESC LIMIT 100", (user["id"],)).fetchall()
                status_rows = con.execute("SELECT status,COUNT(*) n FROM hallazgos WHERE owner_id=? GROUP BY status", (user["id"],)).fetchall()
                usage = self.usage(con, user["id"])
                requests = con.execute("SELECT plan,status,created_at FROM plan_requests WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
            from collections import Counter
            import json
            counts = Counter(d["class_name"] for row in rows for d in json.loads(row["detections_json"]))
            return render_template("dashboard.html", usage=usage, limit=PLANS[user["plan"]]["limit"],
                                   total=sum(row["n"] for row in status_rows), statuses={row["status"]: row["n"] for row in status_rows},
                                   top_classes=counts.most_common(5), findings=rows[:8], plan_requests=requests)

        @app.get("/admin")
        def admin_dashboard():
            user, response = self.require_page_user()
            if response:
                return response
            if user["role"] != "superadmin":
                abort(403)
            with self.db_connection() as con:
                users = con.execute("SELECT u.id,u.name,u.email,u.role,u.plan,u.created_at,COUNT(h.id) findings FROM users u LEFT JOIN hallazgos h ON h.owner_id=u.id WHERE u.active=1 GROUP BY u.id ORDER BY u.created_at DESC").fetchall()
                requests = con.execute("SELECT r.id,r.plan,r.note,r.status,r.created_at,u.name,u.email FROM plan_requests r JOIN users u ON u.id=r.user_id ORDER BY r.created_at DESC LIMIT 50").fetchall()
                legacy = con.execute("SELECT COUNT(*) FROM hallazgos WHERE owner_id IS NULL").fetchone()[0]
            return render_template("admin.html", users=users, plan_requests=requests, legacy_count=legacy)

        @app.post("/admin/planes/<request_id>")
        def decide_plan(request_id):
            user, response = self.require_page_user()
            if response:
                return response
            if user["role"] != "superadmin":
                abort(403)
            self.require_csrf()
            decision = request.form.get("decision")
            if decision not in ("aprobado", "rechazado"):
                abort(400)
            with self.db_connection() as con:
                row = con.execute("SELECT user_id,plan FROM plan_requests WHERE id=? AND status='pendiente'", (request_id,)).fetchone()
                if row is None:
                    abort(404)
                con.execute("UPDATE plan_requests SET status=?,decided_at=? WHERE id=?", (decision, utc_now(), request_id))
                if decision == "aprobado":
                    con.execute("UPDATE users SET plan=? WHERE id=? AND role='agricultor'", (row["plan"], row["user_id"]))
            flash("Solicitud actualizada. No se ha procesado un pago.", "success")
            return redirect(url_for("admin_dashboard"))

        @app.get("/admin/activar/<token>")
        def admin_activate_page(token):
            row = self._valid_setup_token(token)
            if not row:
                abort(404)
            return render_template("auth.html", mode="activar", setup_token=token)

        @app.post("/admin/activar/<token>")
        def admin_activate(token):
            self.require_csrf()
            row = self._valid_setup_token(token)
            if not row:
                abort(404)
            password = request.form.get("password", "")
            if not 12 <= len(password) <= 128:
                flash("La contraseña debe tener entre 12 y 128 caracteres.", "error")
                return redirect(url_for("admin_activate_page", token=token))
            with self.db_connection() as con:
                con.execute("UPDATE users SET password_hash=?,active=1,setup_token_hash=NULL,setup_expires=NULL WHERE id=?",
                            (generate_password_hash(password), row["id"]))
            session.clear()
            session["user_id"] = row["id"]
            session.permanent = True
            return redirect(url_for("admin_dashboard"))

        @app.cli.command("bootstrap-admin")
        @click.argument("email")
        def bootstrap_admin(email):
            """Emite un enlace de activación de un solo uso para el primer superadmin."""
            email = email.strip().lower()
            if not _EMAIL.fullmatch(email):
                raise click.ClickException("Correo no válido")
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            expiry = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            with self.db_connection() as con:
                if con.execute("SELECT 1 FROM users WHERE role='superadmin' AND active=1").fetchone():
                    raise click.ClickException("Ya existe un superadmin activo")
                row = con.execute("SELECT id FROM users WHERE role='superadmin' AND active=0").fetchone()
                if row:
                    con.execute("UPDATE users SET email=?,setup_token_hash=?,setup_expires=? WHERE id=?", (email, digest, expiry, row["id"]))
                else:
                    con.execute("INSERT INTO users(id,name,email,password_hash,role,plan,active,setup_token_hash,setup_expires,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (secrets.token_hex(16), "Superadmin AgriTech", email, "", "superadmin", "cooperativa", 0, digest, expiry, utc_now()))
            click.echo(f"Enlace de activación (24 horas, un uso): https://esparragos.comextech.es/admin/activar/{token}")

    def _valid_setup_token(self, token):
        if len(token) > 128:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db_connection() as con:
            row = con.execute("SELECT id,setup_expires FROM users WHERE setup_token_hash=? AND role='superadmin' AND active=0", (digest,)).fetchone()
        return row if row and row["setup_expires"] and row["setup_expires"] > utc_now() else None
