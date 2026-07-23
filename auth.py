"""
auth.py — Contas de usuario e controle de acesso por assinatura (Kiwify).

Armazena os usuarios em SQLite (arquivo local, criado automaticamente).
No Render, o disco e efemero por padrao — se quiser que as contas
sobrevivam a redeploys, adicione um "Persistent Disk" no servico e
aponte AUTH_DB_PATH para um caminho dentro dele (ex: /var/data/auth.db).
"""
import os
import sqlite3
import secrets
import time
from contextlib import contextmanager
from functools import wraps

import jwt
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("AUTH_DB_PATH", "auth.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_EXP_SECONDS = 60 * 60 * 24 * 30  # 30 dias

if not JWT_SECRET:
    # Gera um segredo aleatorio se ninguem configurou um (funciona, mas os
    # tokens emitidos ficam invalidos a cada restart do processo). Para
    # producao, defina JWT_SECRET como variavel de ambiente no Render.
    JWT_SECRET = secrets.token_hex(32)
    print("AVISO: JWT_SECRET nao definido. Usando valor aleatorio (tokens "
          "existentes serao invalidados a cada reinicio). Defina JWT_SECRET "
          "no ambiente do Render para producao.")


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                email                 TEXT UNIQUE NOT NULL,
                nome                  TEXT,
                password_hash         TEXT,
                subscription_status   TEXT NOT NULL DEFAULT 'inactive',
                kiwify_order_id       TEXT,
                kiwify_product_id     TEXT,
                created_at            INTEGER NOT NULL,
                updated_at            INTEGER NOT NULL
            )
        """)


# ---------------------------------------------------------------- usuarios --

def get_user_by_email(email):
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None


def upsert_user_from_purchase(email, nome=None, order_id=None, product_id=None, status="active"):
    """Cria o usuario (sem senha ainda) ou atualiza o status de assinatura dele.
    Chamado pelo webhook da Kiwify."""
    email = email.lower().strip()
    now = int(time.time())
    with _db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE users
                SET subscription_status = ?, kiwify_order_id = ?, kiwify_product_id = ?,
                    nome = COALESCE(?, nome), updated_at = ?
                WHERE email = ?
            """, (status, order_id, product_id, nome, now, email))
        else:
            conn.execute("""
                INSERT INTO users (email, nome, password_hash, subscription_status,
                                    kiwify_order_id, kiwify_product_id, created_at, updated_at)
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
            """, (email, nome, status, order_id, product_id, now, now))


def set_subscription_status(email, status):
    """Usado pelo webhook em cancelamento/atraso/renovacao/reembolso/chargeback."""
    with _db() as conn:
        conn.execute(
            "UPDATE users SET subscription_status = ?, updated_at = ? WHERE email = ?",
            (status, int(time.time()), email.lower().strip()),
        )


def definir_senha(email, senha):
    """Usado no primeiro acesso do cliente (depois da compra aprovada)."""
    email = email.lower().strip()
    user = get_user_by_email(email)
    if not user:
        return False, "E-mail nao encontrado. Verifique se a compra foi aprovada."
    with _db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ?",
            (generate_password_hash(senha), int(time.time()), email),
        )
    return True, None


def autenticar(email, senha):
    user = get_user_by_email(email)
    if not user or not user["password_hash"]:
        return None
    if not check_password_hash(user["password_hash"], senha):
        return None
    return user


# --------------------------------------------------------------------- jwt --

def gerar_token(user):
    payload = {
        "sub": user["email"],
        "exp": int(time.time()) + JWT_EXP_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decodificar_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def _extrair_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# --------------------------------------------------------------- decorators --

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extrair_token()
        email = _decodificar_token(token) if token else None
        if not email:
            return jsonify({"ok": False, "erro": "Nao autenticado. Faca login novamente."}), 401
        user = get_user_by_email(email)
        if not user:
            return jsonify({"ok": False, "erro": "Usuario nao encontrado."}), 401
        g.usuario = user
        return fn(*args, **kwargs)
    return wrapper


def subscription_required(fn):
    """Exige login E assinatura ativa (bloqueia inactive/canceled/late/refunded)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extrair_token()
        email = _decodificar_token(token) if token else None
        if not email:
            return jsonify({"ok": False, "erro": "Nao autenticado. Faca login novamente."}), 401
        user = get_user_by_email(email)
        if not user:
            return jsonify({"ok": False, "erro": "Usuario nao encontrado."}), 401
        if user["subscription_status"] != "active":
            return jsonify({
                "ok": False,
                "erro": "Assinatura inativa. Renove seu plano para continuar usando o LotofacilPro.",
                "subscription_status": user["subscription_status"],
            }), 402  # Payment Required
        g.usuario = user
        return fn(*args, **kwargs)
    return wrapper
