22-Sistema de Notificações 

# notification_system.py
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from supabase import create_client
import os

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    NEW_LEAD = "new_lead"
    PROPOSAL_SENT = "proposal_sent"
    CONTRACT_SIGNED = "contract_signed"
    PAYMENT_RECEIVED = "payment_received"
    TASK_OVERDUE = "task_overdue"
    SYSTEM_ALERT = "system_alert"
    CLIENT_MESSAGE = "client_message"

@dataclass
class Notification:
    id: str
    type: NotificationType
    title: str
    message: str
    data: Dict
    created_at: datetime
    read: bool = False
    priority: str = "normal"  # low, normal, high, urgent

class NotificationSystem:
    def __init__(self):
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        self.webhook_urls = {
            "discord": os.getenv("DISCORD_WEBHOOK_URL"),
            "slack": os.getenv("SLACK_WEBHOOK_URL"),
            "telegram": os.getenv("TELEGRAM_BOT_TOKEN")
        }
        
    async def send_notification(self, notification: Notification):
        """Envia notificação através de múltiplos canais"""
        try:
            # Salva no banco de dados
            await self._save_to_database(notification)
            
            # Envia via WebSocket para dashboard
            await self._send_to_dashboard(notification)
            
            # Envia para canais externos se for alta prioridade
            if notification.priority in ["high", "urgent"]:
                await self._send_to_external_channels(notification)
                
            logger.info(f"Notificação enviada: {notification.title}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            
    async def _save_to_database(self, notification: Notification):
        """Salva notificação no banco de dados"""
        try:
            self.supabase.table("notifications").insert({
                "id": notification.id,
                "type": notification.type.value,
                "title": notification.title,
                "message": notification.message,
                "data": notification.data,
                "priority": notification.priority,
                "read": notification.read,
                "created_at": notification.created_at.isoformat()
            }).execute()
            
        except Exception as e:
            logger.error(f"Erro ao salvar notificação no banco: {e}")
            
    async def _send_to_dashboard(self, notification: Notification):
        """Envia notificação para o dashboard via WebSocket"""
        try:
            from websocket_manager import dashboard_manager
            
            await dashboard_manager.broadcast({
                "type": "notification",
                "notification": {
                    "id": notification.id,
                    "type": notification.type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data,
                    "priority": notification.priority,
                    "created_at": notification.created_at.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao enviar para dashboard: {e}")
            
    async def _send_to_external_channels(self, notification: Notification):
        """Envia notificação para canais externos"""
        tasks = []
        
        if self.webhook_urls["discord"]:
            tasks.append(self._send_to_discord(notification))
            
        if self.webhook_urls["slack"]:
            tasks.append(self._send_to_slack(notification))
            
        if self.webhook_urls["telegram"]:
            tasks.append(self._send_to_telegram(notification))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _send_to_discord(self, notification: Notification):
        """Envia notificação para Discord"""
        try:
            color = {
                "low": 0x95a5a6,
                "normal": 0x3498db,
                "high": 0xf39c12,
                "urgent": 0xe74c3c
            }.get(notification.priority, 0x3498db)
            
            payload = {
                "embeds": [{
                    "title": notification.title,
                    "description": notification.message,
                    "color": color,
                    "timestamp": notification.created_at.isoformat(),
                    "footer": {
                        "text": f"Crânios - {notification.type.value}"
                    }
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_urls["discord"], 
                    json=payload
                ) as response:
                    if response.status != 204:
                        logger.warning(f"Discord webhook retornou: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erro ao enviar para Discord: {e}")
            
    async def _send_to_slack(self, notification: Notification):
        """Envia notificação para Slack"""
        try:
            color = {
                "low": "#95a5a6",
                "normal": "#3498db", 
                "high": "#f39c12",
                "urgent": "#e74c3c"
            }.get(notification.priority, "#3498db")
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "footer": f"Crânios - {notification.type.value}",
                    "ts": int(notification.created_at.timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_urls["slack"],
                    json=payload
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Slack webhook retornou: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erro ao enviar para Slack: {e}")
            
    async def _send_to_telegram(self, notification: Notification):
        """Envia notificação para Telegram"""
        try:
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if not chat_id:
                return
                
            text = f"🔔 *{notification.title}*\n\n{notification.message}"
            
            url = f"https://api.telegram.org/bot{self.webhook_urls['telegram']}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.warning(f"Telegram API retornou: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erro ao enviar para Telegram: {e}")
            
    async def get_notifications(self, limit: int = 50, unread_only: bool = False):
        """Busca notificações do banco de dados"""
        try:
            query = self.supabase.table("notifications").select("*")
            
            if unread_only:
                query = query.eq("read", False)
                
            result = query.order("created_at", desc=True).limit(limit).execute()
            
            return [
                Notification(
                    id=item["id"],
                    type=NotificationType(item["type"]),
                    title=item["title"],
                    message=item["message"],
                    data=item["data"] or {},
                    created_at=datetime.fromisoformat(item["created_at"]),
                    read=item["read"],
                    priority=item["priority"]
                )
                for item in result.data
            ]
            
        except Exception as e:
            logger.error(f"Erro ao buscar notificações: {e}")
            return []
            
    async def mark_as_read(self, notification_id: str):
        """Marca notificação como lida"""
        try:
            self.supabase.table("notifications")\
                .update({"read": True})\
                .eq("id", notification_id)\
                .execute()
                
        except Exception as e:
            logger.error(f"Erro ao marcar notificação como lida: {e}")
            
    async def mark_all_as_read(self):
        """Marca todas as notificações como lidas"""
        try:
            self.supabase.table("notifications")\
                .update({"read": True})\
                .eq("read", False)\
                .execute()
                
        except Exception as e:
            logger.error(f"Erro ao marcar todas as notificações como lidas: {e}")

# Funções de conveniência para diferentes tipos de notificação
class NotificationFactory:
    @staticmethod
    def new_lead(lead_data: Dict) -> Notification:
        return Notification(
            id=f"lead_{lead_data['id']}",
            type=NotificationType.NEW_LEAD,
            title="Novo Lead Capturado!",
            message=f"Lead: {lead_data['name']} - {lead_data['business_type']}",
            data=lead_data,
            created_at=datetime.now(),
            priority="high"
        )
        
    @staticmethod
    def proposal_sent(proposal_data: Dict) -> Notification:
        return Notification(
            id=f"proposal_{proposal_data['id']}",
            type=NotificationType.PROPOSAL_SENT,
            title="Proposta Enviada",
            message=f"Proposta de R$ {proposal_data['total_value']:,.2f} enviada",
            data=proposal_data,
            created_at=datetime.now(),
            priority="normal"
        )
        
    @staticmethod
    def contract_signed(contract_data: Dict) -> Notification:
        return Notification(
            id=f"contract_{contract_data['id']}",
            type=NotificationType.CONTRACT_SIGNED,
            title="🎉 Contrato Assinado!",
            message=f"Cliente assinou contrato - Valor: R$ {contract_data.get('value', 0):,.2f}",
            data=contract_data,
            created_at=datetime.now(),
            priority="urgent"
        )
        
    @staticmethod
    def payment_received(payment_data: Dict) -> Notification:
        return Notification(
            id=f"payment_{payment_data['id']}",
            type=NotificationType.PAYMENT_RECEIVED,
            title="💰 Pagamento Recebido",
            message=f"Pagamento de R$ {payment_data['amount']:,.2f} confirmado",
            data=payment_data,
            created_at=datetime.now(),
            priority="high"
        )
        
    @staticmethod
    def task_overdue(task_data: Dict) -> Notification:
        return Notification(
            id=f"overdue_{task_data['id']}",
            type=NotificationType.TASK_OVERDUE,
            title="⚠️ Tarefa Atrasada",
            message=f"Tarefa '{task_data['title']}' está atrasada",
            data=task_data,
            created_at=datetime.now(),
            priority="high"
        )

# Instância global do sistema de notificações
notification_system = NotificationSystem()