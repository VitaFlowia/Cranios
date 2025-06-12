"""
Financial Manager Service - Crânios
Gerenciador automático de financeiro e pagamentos (via Stripe + Supabase)
"""

import os
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Any
from supabase import create_client, Client
import aiohttp

from contract_manager_service import ContractManager
from task_manager_service import TaskManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.evolution_api_url = os.getenv("EVOLUTION_API_URL")
        self.evolution_api_key = os.getenv("EVOLUTION_API_KEY")

    async def create_checkout_session(self, client_data: Dict, proposal_data: Dict) -> Dict[str, Any]:
        """Cria uma sessão de pagamento no Stripe e salva no Supabase com status 'pending'"""
        try:
            headers = {
                "Authorization": f"Bearer {self.stripe_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "success_url": f"https://cranios.pro/success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"https://cranios.pro/cancel",
                "payment_method_types": ["card", "pix", "boleto"],
                "mode": "payment",
                "customer_email": client_data.get("email"),
                "line_items": [
                    {
                        "price_data": {
                            "currency": "brl",
                            "product_data": {
                                "name": proposal_data.get("title", "Proposta Crânios")
                            },
                            "unit_amount": int(proposal_data["price"] * 100)
                        },
                        "quantity": 1
                    }
                ],
                "metadata": {
                    "client_id": client_data["id"],
                    "phone": client_data["phone"],
                    "proposal_id": proposal_data["id"]
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.stripe.com/v1/checkout/sessions", headers=headers, json=payload) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"Erro ao criar sessão Stripe: {error}")
                        return {"success": False, "error": error}

                    session_data = await response.json()

                    self.supabase.table("payment_sessions").insert({
                        "id": session_data["id"],
                        "client_id": client_data["id"],
                        "proposal_id": proposal_data["id"],
                        "status": "pending",
                        "amount": proposal_data["price"],
                        "created_at": datetime.now().isoformat()
                    }).execute()

                    return {"success": True, "checkout_url": session_data["url"]}

        except Exception as e:
            logger.error(f"Erro ao criar sessão de pagamento: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_payment_webhook(self, event_data: Dict) -> Dict[str, Any]:
        """Processa o Webhook do Stripe quando um pagamento for concluído"""
        try:
            event_type = event_data.get("type")
            session = event_data.get("data", {}).get("object", {})

            if event_type == "checkout.session.completed":
                session_id = session.get("id")
                client_id = session["metadata"]["client_id"]
                phone = session["metadata"]["phone"]
                proposal_id = session["metadata"]["proposal_id"]

                self.supabase.table("payment_sessions").update({
                    "status": "completed",
                    "updated_at": datetime.now().isoformat()
                }).eq("id", session_id).execute()

                await self._send_payment_confirmation(phone, session.get("amount_total") / 100)

                contract_manager = ContractManager(self.supabase)
                task_manager = TaskManager(self.supabase)

                await contract_manager.create_contract(proposal_id)
                await task_manager.create_implementation_tasks(client_id, "default")

                return {"success": True}

            return {"success": False, "message": "Evento ignorado"}

        except Exception as e:
            logger.error(f"Erro no webhook do Stripe: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _send_payment_confirmation(self, phone: str, amount: float):
        """Envia mensagem de confirmação de pagamento via WhatsApp"""
        try:
            msg = (
                f"🎉 *Pagamento confirmado!*\n\n"
                f"Recebemos R$ {amount:.2f} com sucesso. Obrigado por escolher a Crânios! 🙌\n\n"
                f"Nosso time já está iniciando a próxima etapa do seu projeto. 🚀"
            )

            await self._send_whatsapp_message(phone, msg)

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de confirmação: {str(e)}")

    async def send_pending_followups(self):
        """Envia lembretes para sessões de pagamento pendentes"""
        try:
            result = self.supabase.table("payment_sessions").select("*").eq("status", "pending").execute()
            sessions = result.data or []

            for session in sessions:
                phone = self._get_client_phone(session["client_id"])
                amount = session["amount"]
                url = f"https://buy.stripe.com/test_abc1234567890{session['id']}"

                msg = (
                    f"👋 Olá! Vimos que você iniciou o processo de pagamento, mas ainda não finalizou.\n\n"
                    f"💰 *Valor:* R$ {amount:.2f}\n"
                    f"🔗 *Link para finalizar:* {url}\n\n"
                    f"Qualquer dúvida, estamos à disposição para ajudar! 😊"
                )

                await self._send_whatsapp_message(phone, msg)

        except Exception as e:
            logger.error(f"Erro ao enviar lembretes de pagamento: {str(e)}")

    def _get_client_phone(self, client_id: str) -> str:
        result = self.supabase.table("leads").select("phone").eq("id", client_id).execute()
        if result.data:
            return result.data[0]["phone"]
        return ""

    async def _send_whatsapp_message(self, phone: str, msg: str):
        try:
            headers = {
                "Content-Type": "application/json",
                "apikey": self.evolution_api_key
            }
            payload = {
                "number": phone,
                "text": msg
            }

            async with aiohttp.ClientSession() as session:
                await session.post(f"{self.evolution_api_url}/message/sendText", json=payload, headers=headers)
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {str(e)}")


