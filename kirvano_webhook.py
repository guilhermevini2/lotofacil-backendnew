"""
kirvano_webhook.py — Recebe eventos da Kirvano e atualiza o acesso do cliente.

Formato do payload da Kirvano (confirmado pela documentacao oficial em
help.kirvano.com, abril/2026) -- estrutura FLAT, sem envelope como a Kiwify:

{
    "event": "SALE_APPROVED",
    "event_description": "Compra aprovada",
    "sale_id": "...",
    "type": "ONE_TIME" | "RECURRING",
    "status": "APPROVED",
    "customer": {"name": "...", "document": "...", "email": "...", "phone_number": "..."},
    "plan": {"name": "...", "charge_frequency": "...", "next_charge_date": "..."},  # so em RECURRING
    "products": [...],
    ...
}

IMPORTANTE sobre autenticacao: a documentacao da Kirvano confirma que existe
um campo "Token" opcional configurado no painel, mas nao especifica em qual
lugar exato da requisicao ele chega (header ou corpo). Por seguranca,
verificamos em varios lugares plausiveis (query string, headers comuns e
corpo). Depois do primeiro teste real, confira nos logs do Render onde o
token realmente chegou e me avise se precisar ajustar.

Configuracao no painel da Kirvano (Integracoes > Webhooks > Criar Webhook):
  URL do Webhook: https://SEU-BACKEND.onrender.com/api/webhooks/kirvano?token=SEU_TOKEN_SECRETO
  Token: SEU_TOKEN_SECRETO (mesmo valor usado na URL, se o campo pedir)
  Eventos: Compra aprovada, Compra recusada, Reembolso, Chargeback,
           Assinatura cancelada, Assinatura atrasada, Assinatura renovada
"""
import os
from flask import Blueprint, request, jsonify

import auth

kirvano_bp = Blueprint("kirvano_webhook", __name__)

WEBHOOK_TOKEN = os.environ.get("KIRVANO_WEBHOOK_TOKEN", "")

# Eventos que LIBERAM acesso
EVENTOS_ATIVAR = {"SALE_APPROVED", "SUBSCRIPTION_RENEWED"}
# Eventos que REVOGAM acesso
EVENTOS_DESATIVAR = {"SALE_REFUNDED", "SALE_CHARGEBACK", "SUBSCRIPTION_CANCELED"}
# Atraso: mantemos como status separado
EVENTOS_ATRASO = {"SUBSCRIPTION_EXPIRED"}
# Eventos que nao mudam status nenhum
EVENTOS_IGNORAR = {
    "SALE_REFUSED", "ABANDONED_CART",
    "BANK_SLIP_GENERATED", "BANK_SLIP_EXPIRED",
    "PIX_GENERATED", "PIX_EXPIRED",
}


def _token_valido():
    if not WEBHOOK_TOKEN:
        print("AVISO: KIRVANO_WEBHOOK_TOKEN nao configurado -- endpoint SEM protecao.")
        return True
    candidatos = [
        request.args.get("token", ""),
        request.headers.get("X-Kirvano-Token", ""),
        request.headers.get("X-Webhook-Token", ""),
        request.headers.get("Authorization", "").replace("Bearer ", ""),
    ]
    body = request.get_json(silent=True) or {}
    candidatos.append(body.get("token", ""))
    return WEBHOOK_TOKEN in candidatos


@kirvano_bp.route("/api/webhooks/kirvano", methods=["POST"])
def receber_webhook_kirvano():
    if not _token_valido():
        return jsonify({"ok": False, "erro": "token invalido"}), 401

    payload = request.get_json(silent=True) or {}
    evento = payload.get("event", "")
    customer = payload.get("customer") or {}
    email = customer.get("email")
    nome = customer.get("name")
    sale_id = payload.get("sale_id")
    products = payload.get("products") or []
    product_id = products[0].get("id") if products else None

    print(f"[kirvano webhook] evento={evento} email={email} sale_id={sale_id}")

    if not email:
        print(f"[kirvano webhook] AVISO: sem e-mail no payload. Corpo bruto: {payload}")
        return jsonify({"ok": False, "erro": "email nao encontrado no payload"}), 400

    if evento in EVENTOS_ATIVAR:
        auth.upsert_user_from_purchase(email, nome=nome, order_id=sale_id,
                                        product_id=product_id, status="active")
    elif evento in EVENTOS_DESATIVAR:
        auth.set_subscription_status(email, "inactive")
    elif evento in EVENTOS_ATRASO:
        auth.set_subscription_status(email, "late")
    elif evento in EVENTOS_IGNORAR:
        pass
    else:
        print(f"[kirvano webhook] evento nao mapeado: {evento!r} -- ignorado.")

    return jsonify({"ok": True})
