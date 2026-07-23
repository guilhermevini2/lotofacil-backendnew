"""
kiwify_webhook.py — Recebe eventos da Kiwify e atualiza o acesso do cliente.

IMPORTANTE: os nomes de campo abaixo (Customer.email, order_status, Subscription.status
etc.) seguem o formato classico documentado/usado pela maioria das integracoes Kiwify.
Antes de ir para producao, teste com uma compra de teste (ou o botao "Testar Webhook"
no painel da Kiwify) e confira nos logs do Render (prints abaixo) se os campos batem
com o que sua conta realmente envia -- a Kiwify já mudou esse formato entre versoes
de conta/produto no passado.

Configuracao na Kiwify (Apps > Webhooks > Criar Webhook):
  URL: https://SEU-BACKEND.onrender.com/api/webhooks/kiwify?token=SEU_TOKEN_SECRETO
  Eventos: Compra aprovada, Compra reembolsada, Chargeback,
           Assinatura Cancelada, Assinatura Atrasada, Assinatura Renovada

O "SEU_TOKEN_SECRETO" e definido por voce nas duas pontas: no campo "token" ao
criar o webhook na Kiwify, e na variavel de ambiente KIWIFY_WEBHOOK_TOKEN no Render.
"""
import os
from flask import Blueprint, request, jsonify

import auth

kiwify_bp = Blueprint("kiwify_webhook", __name__)

WEBHOOK_TOKEN = os.environ.get("KIWIFY_WEBHOOK_TOKEN", "")

# Eventos que LIBERAM acesso
EVENTOS_ATIVAR = {"compra_aprovada", "subscription_renewed"}
# Eventos que REVOGAM acesso
EVENTOS_DESATIVAR = {"compra_reembolsada", "chargeback", "subscription_canceled"}
# Atraso: mantemos como status separado (voce decide se bloqueia ou da carencia)
EVENTOS_ATRASO = {"subscription_late"}


def _extrair_evento(payload, query_event):
    """A Kiwify identifica o evento de formas diferentes dependendo da conta/versao:
    as vezes via query string (?event=compra_aprovada), as vezes um campo no corpo
    (webhook_event_type / event), as vezes implicito por order_status. Tentamos todas."""
    if query_event:
        return query_event
    for campo in ("webhook_event_type", "event", "type"):
        if payload.get(campo):
            return payload[campo]
    # Fallback: infere pelo order_status quando nenhum campo de evento existe
    status = (payload.get("order_status") or "").lower()
    if status in ("paid", "approved"):
        return "compra_aprovada"
    if status in ("refunded",):
        return "compra_reembolsada"
    if status in ("chargedback", "chargeback"):
        return "chargeback"
    return None


def _extrair_email(payload):
    customer = payload.get("Customer") or payload.get("customer") or {}
    return customer.get("email") or payload.get("customer_email")


def _extrair_nome(payload):
    customer = payload.get("Customer") or payload.get("customer") or {}
    return customer.get("full_name") or customer.get("name")


@kiwify_bp.route("/api/webhooks/kiwify", methods=["POST"])
def receber_webhook_kiwify():
    # 1) Verifica o token secreto (protege contra chamadas falsas a esse endpoint)
    token_recebido = request.args.get("token", "")
    if not WEBHOOK_TOKEN:
        print("AVISO: KIWIFY_WEBHOOK_TOKEN nao configurado no ambiente -- "
              "o endpoint do webhook esta SEM protecao. Configure essa variavel no Render.")
    elif token_recebido != WEBHOOK_TOKEN:
        return jsonify({"ok": False, "erro": "token invalido"}), 401

    payload = request.get_json(silent=True) or {}
    evento = _extrair_evento(payload, request.args.get("event"))
    email = _extrair_email(payload)
    nome = _extrair_nome(payload)
    order_id = payload.get("order_id") or payload.get("id")
    product_id = (payload.get("Product") or payload.get("product") or {}).get("product_id")

    print(f"[kiwify webhook] evento={evento} email={email} order_id={order_id}")

    if not email:
        # Loga o payload cru pra voce conseguir ajustar _extrair_email/_extrair_evento
        # caso o formato da sua conta seja diferente do esperado.
        print(f"[kiwify webhook] AVISO: nao encontrei e-mail no payload. Corpo bruto: {payload}")
        return jsonify({"ok": False, "erro": "email nao encontrado no payload"}), 400

    if evento in EVENTOS_ATIVAR:
        auth.upsert_user_from_purchase(email, nome=nome, order_id=order_id,
                                        product_id=product_id, status="active")
    elif evento in EVENTOS_DESATIVAR:
        auth.set_subscription_status(email, "inactive")
    elif evento in EVENTOS_ATRASO:
        auth.set_subscription_status(email, "late")
    else:
        print(f"[kiwify webhook] evento nao mapeado: {evento!r} -- ignorado (nenhuma acao tomada).")

    return jsonify({"ok": True})


@kiwify_bp.route("/api/auth/definir-senha", methods=["POST"])
def definir_senha_route():
    """Primeiro acesso do cliente: ele informa o e-mail usado na compra + a senha
    que quer criar. So funciona se o e-mail ja existe na base (ou seja, se a
    Kiwify ja mandou o webhook de compra aprovada pra esse e-mail)."""
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip()
    senha = dados.get("senha") or ""
    if not email or not senha or len(senha) < 6:
        return jsonify({"ok": False, "erro": "Informe e-mail e uma senha com pelo menos 6 caracteres."}), 400

    ok, erro = auth.definir_senha(email, senha)
    if not ok:
        return jsonify({"ok": False, "erro": erro}), 404
    return jsonify({"ok": True})


@kiwify_bp.route("/api/auth/login", methods=["POST"])
def login_route():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip()
    senha = dados.get("senha") or ""
    user = auth.autenticar(email, senha)
    if not user:
        return jsonify({"ok": False, "erro": "E-mail ou senha invalidos."}), 401
    if user["subscription_status"] != "active":
        return jsonify({
            "ok": False,
            "erro": "Sua assinatura nao esta ativa.",
            "subscription_status": user["subscription_status"],
        }), 402
    token = auth.gerar_token(user)
    return jsonify({"ok": True, "token": token, "email": user["email"], "nome": user["nome"]})


@kiwify_bp.route("/api/auth/me")
@auth.login_required
def me_route():
    from flask import g
    return jsonify({
        "ok": True,
        "email": g.usuario["email"],
        "nome": g.usuario["nome"],
        "subscription_status": g.usuario["subscription_status"],
    })
