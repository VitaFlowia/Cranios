# websocket_manager.py
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set
import websockets
from websockets.exceptions import ConnectionClosed
from supabase import create_client
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AlertType(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class Alert:
    type: AlertType
    title: str
    message: str
    timestamp: datetime

class DashboardWebSocketManager:
    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        self.metrics_cache = {}
        self.alerts: List[Alert] = []
        
    async def register(self, websocket):
        """Registra um novo cliente WebSocket"""
        self.clients.add(websocket)
        logger.info(f"Cliente conectado. Total: {len(self.clients)}")
        
        # Envia dados iniciais para o cliente
        initial_data = await self.get_dashboard_data()
        await self.send_to_client(websocket, initial_data)
        
    async def unregister(self, websocket):
        """Remove um cliente WebSocket"""
        self.clients.discard(websocket)
        logger.info(f"Cliente desconectado. Total: {len(self.clients)}")
        
    async def send_to_client(self, websocket, data):
        """Envia dados para um cliente específico"""
        try:
            await websocket.send(json.dumps(data))
        except ConnectionClosed:
            await self.unregister(websocket)
        except Exception as e:
            logger.error(f"Erro ao enviar dados para cliente: {e}")
            
    async def broadcast(self, data):
        """Envia dados para todos os clientes conectados"""
        if self.clients:
            await asyncio.gather(
                *[self.send_to_client(client, data) for client in self.clients],
                return_exceptions=True
            )
            
    async def get_dashboard_data(self):
        """Coleta todos os dados do dashboard"""
        try:
            metrics = await self.get_metrics()
            alerts = await self.get_alerts()
            
            return {
                "type": "metrics_update",
                "metrics": metrics,
                "alerts": [
                    {
                        "type": alert.type.value,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat()
                    } for alert in alerts
                ],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao coletar dados do dashboard: {e}")
            return {"type": "error", "message": "Erro interno do servidor"}
            
    async def get_metrics(self):
        """Coleta métricas do banco de dados"""
        try:
            today = datetime.now().date()
            
            # Conversas hoje
            conversations_today = self.supabase.table("conversations")\
                .select("id")\
                .gte("created_at", today.isoformat())\
                .execute()
                
            # Leads hoje
            leads_today = self.supabase.table("leads")\
                .select("id")\
                .gte("created_at", today.isoformat())\
                .execute()
                
            # Propostas enviadas hoje
            proposals_sent_today = self.supabase.table("proposals")\
                .select("id")\
                .gte("sent_at", today.isoformat())\
                .execute()
                
            # Contratos assinados hoje
            contracts_signed_today = self.supabase.table("contracts")\
                .select("id")\
                .gte("signed_at", today.isoformat())\
                .execute()
                
            # Taxa de conversão (este mês)
            first_day_month = today.replace(day=1)
            
            conversations_month = self.supabase.table("conversations")\
                .select("id")\
                .gte("created_at", first_day_month.isoformat())\
                .execute()
                
            leads_month = self.supabase.table("leads")\
                .select("id")\
                .gte("created_at", first_day_month.isoformat())\
                .execute()
                
            conversion_rate = (len(leads_month.data) / len(conversations_month.data) * 100) \
                if conversations_month.data else 0
                
            # Receita mensal
            revenue_data = await self.calculate_monthly_revenue()
            
            # Pipeline de vendas
            pipeline_data = await self.get_pipeline_data()
            
            return {
                "conversations": {
                    "today": len(conversations_today.data),
                    "month": len(conversations_month.data)
                },
                "leads": {
                    "today": len(leads_today.data),
                    "month": len(leads_month.data)
                },
                "conversion_rate": conversion_rate,
                "revenue": revenue_data,
                "proposals": {
                    "sent_today": len(proposals_sent_today.data),
                    "signed_today": len(contracts_signed_today.data)
                },
                "pipeline": pipeline_data
            }
            
        except Exception as e:
            logger.error(f"Erro ao coletar métricas: {e}")
            return {}
            
    async def calculate_monthly_revenue(self):
        """Calcula receita mensal atual e crescimento"""
        try:
            now = datetime.now()
            current_month_start = now.replace(day=1)
            
            # Mês anterior
            if now.month == 1:
                last_month_start = now.replace(year=now.year-1, month=12, day=1)
                last_month_end = now.replace(month=1, day=1) - timedelta(days=1)
            else:
                last_month_start = now.replace(month=now.month-1, day=1)
                # Último dia do mês anterior
                last_month_end = current_month_start - timedelta(days=1)
                
            # Receita do mês atual
            current_revenue = self.supabase.table("financial_transactions")\
                .select("amount")\
                .eq("type", "receivable")\
                .eq("status", "paid")\
                .gte("paid_at", current_month_start.isoformat())\
                .execute()
                
            # Receita do mês anterior
            last_revenue = self.supabase.table("financial_transactions")\
                .select("amount")\
                .eq("type", "receivable")\
                .eq("status", "paid")\
                .gte("paid_at", last_month_start.isoformat())\
                .lte("paid_at", last_month_end.isoformat())\
                .execute()
                
            current_total = sum(float(r["amount"]) for r in current_revenue.data)
            last_total = sum(float(r["amount"]) for r in last_revenue.data)
            
            growth_percentage = ((current_total - last_total) / last_total * 100) \
                if last_total > 0 else 0
                
            return {
                "current_month": current_total,
                "last_month": last_total,
                "growth_percentage": growth_percentage
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular receita: {e}")
            return {"current_month": 0, "last_month": 0, "growth_percentage": 0}
            
    async def get_pipeline_data(self):
        """Coleta dados do pipeline de vendas"""
        try:
            statuses = ["draft", "sent", "viewed", "negotiating", "signed"]
            pipeline_data = {}
            
            for status in statuses:
                count = self.supabase.table("proposals")\
                    .select("id, total_value")\
                    .eq("status", status)\
                    .execute()
                    
                pipeline_data[status] = {
                    "count": len(count.data),
                    "value": sum(float(item["total_value"]) for item in count.data if item["total_value"])
                }
                
            return pipeline_data
            
        except Exception as e:
            logger.error(f"Erro ao coletar dados do pipeline: {e}")
            return {}
            
    async def get_alerts(self):
        """Coleta alertas do sistema"""
        try:
            alerts = []
            
            # Verifica tarefas atrasadas
            overdue_tasks = self.supabase.table("tasks")\
                .select("id, title, due_date")\
                .eq("status", "pending")\
                .lt("due_date", datetime.now().isoformat())\
                .execute()
                
            if overdue_tasks.data:
                alerts.append(Alert(
                    type=AlertType.WARNING,
                    title="Tarefas Atrasadas",
                    message=f"{len(overdue_tasks.data)} tarefas estão atrasadas",
                    timestamp=datetime.now()
                ))
                
            # Verifica propostas não respondidas há mais de 3 dias
            three_days_ago = datetime.now() - timedelta(days=3)
            stale_proposals = self.supabase.table("proposals")\
                .select("id")\
                .eq("status", "sent")\
                .lt("sent_at", three_days_ago.isoformat())\
                .execute()
                
            if stale_proposals.data:
                alerts.append(Alert(
                    type=AlertType.INFO,
                    title="Follow-up Necessário",
                    message=f"{len(stale_proposals.data)} propostas precisam de follow-up",
                    timestamp=datetime.now()
                ))
                
            # Verifica pagamentos em atraso
            overdue_payments = self.supabase.table("financial_transactions")\
                .select("id, amount")\
                .eq("status", "pending")\
                .eq("type", "receivable")\
                .lt("due_date", datetime.now().date().isoformat())\
                .execute()
                
            if overdue_payments.data:
                total_overdue = sum(float(p["amount"]) for p in overdue_payments.data)
                alerts.append(Alert(
                    type=AlertType.ERROR,
                    title="Pagamentos em Atraso",
                    message=f"R$ {total_overdue:,.2f} em pagamentos atrasados",
                    timestamp=datetime.now()
                ))
                
            return alerts
            
        except Exception as e:
            logger.error(f"Erro ao coletar alertas: {e}")
            return []
            
    async def add_alert(self, alert_type: AlertType, title: str, message: str):
        """Adiciona um novo alerta e notifica clientes"""
        alert = Alert(
            type=alert_type,
            title=title,
            message=message,
            timestamp=datetime.now()
        )
        
        self.alerts.append(alert)
        
        # Mantém apenas os últimos 50 alertas
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]
            
        # Notifica todos os clientes conectados
        await self.broadcast({
            "type": "new_alert",
            "alert": {
                "type": alert.type.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
        })
        
    async def handle_client(self, websocket, path):
        """Manipula conexões de clientes WebSocket"""
        await self.register(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.handle_message(websocket, data)
        except ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Erro na conexão WebSocket: {e}")
        finally:
            await self.unregister(websocket)
            
    async def handle_message(self, websocket, data):
        """Processa mensagens recebidas dos clientes"""
        message_type = data.get("type")
        
        if message_type == "ping":
            await self.send_to_client(websocket, {"type": "pong"})
        elif message_type == "request_update":
            dashboard_data = await self.get_dashboard_data()
            await self.send_to_client(websocket, dashboard_data)
        elif message_type == "mark_alert_read":
            alert_id = data.get("alert_id")
            # Implementar lógica para marcar alerta como lido
            pass
            
    async def start_background_tasks(self):
        """Inicia tarefas em background"""
        asyncio.create_task(self.metrics_updater())
        asyncio.create_task(self.alert_checker())
        
    async def metrics_updater(self):
        """Atualiza métricas periodicamente"""
        while True:
            try:
                dashboard_data = await self.get_dashboard_data()
                await self.broadcast(dashboard_data)
                await asyncio.sleep(30)  # Atualiza a cada 30 segundos
            except Exception as e:
                logger.error(f"Erro ao atualizar métricas: {e}")
                await asyncio.sleep(60)
                
    async def alert_checker(self):
        """Verifica alertas periodicamente"""
        while True:
            try:
                await asyncio.sleep(300)  # Verifica a cada 5 minutos
                alerts = await self.get_alerts()
                
                # Verifica se há novos alertas
                current_alert_count = len(alerts)
                if hasattr(self, 'last_alert_count'):
                    if current_alert_count > self.last_alert_count:
                        await self.broadcast({
                            "type": "alerts_update",
                            "count": current_alert_count
                        })
                        
                self.last_alert_count = current_alert_count
                
            except Exception as e:
                logger.error(f"Erro ao verificar alertas: {e}")

# Instância global do manager
dashboard_manager = DashboardWebSocketManager()

async def websocket_handler(websocket, path):
    """Handler principal para conexões WebSocket"""
    await dashboard_manager.handle_client(websocket, path)

def start_websocket_server(host="localhost", port=8765):
    """Inicia o servidor WebSocket"""
    return websockets.serve(websocket_handler, host, port)
