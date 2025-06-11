18-dashboard

"""
Sistema de Dashboard Executivo - Completo
Dashboard em tempo real com métricas de negócio
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
from supabase import create_client
from sqlalchemy import text

# Configuração do Supabase
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class DashboardManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.supabase = supabase
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
    async def broadcast_metrics(self, data: dict):
        """Envia métricas para todos os clientes conectados"""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except:
                pass
                
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Coleta métricas em tempo real"""
        try:
            now = datetime.now()
            today = now.date()
            this_month = now.replace(day=1).date()
            last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1).date()
            
            # Métricas de conversas
            conversations_today = self.supabase.table('conversations').select('*', count='exact').gte('created_at', today.isoformat()).execute()
            conversations_month = self.supabase.table('conversations').select('*', count='exact').gte('created_at', this_month.isoformat()).execute()
            
            # Métricas de leads
            leads_today = self.supabase.table('leads').select('*', count='exact').gte('created_at', today.isoformat()).execute()
            leads_month = self.supabase.table('leads').select('*', count='exact').gte('created_at', this_month.isoformat()).execute()
            
            # Métricas de propostas
            proposals_sent_today = self.supabase.table('proposals').select('*', count='exact').gte('sent_at', today.isoformat()).execute()
            proposals_signed_today = self.supabase.table('proposals').select('*', count='exact').gte('signed_at', today.isoformat()).execute()
            
            # Métricas financeiras
            revenue_month = self.supabase.table('financial_transactions').select('amount.sum()').eq('type', 'receivable').eq('status', 'paid').gte('paid_at', this_month.isoformat()).execute()
            revenue_last_month = self.supabase.table('financial_transactions').select('amount.sum()').eq('type', 'receivable').eq('status', 'paid').gte('paid_at', last_month.isoformat()).lt('paid_at', this_month.isoformat()).execute()
            
            # Cálculo de taxa de conversão
            conversion_rate = 0
            if conversations_month.count > 0:
                conversion_rate = (leads_month.count / conversations_month.count) * 100
                
            # Cálculo de crescimento de receita
            revenue_growth = 0
            current_revenue = revenue_month.data[0].get('sum', 0) if revenue_month.data else 0
            last_revenue = revenue_last_month.data[0].get('sum', 0) if revenue_last_month.data else 0
            
            if last_revenue > 0:
                revenue_growth = ((current_revenue - last_revenue) / last_revenue) * 100
            
            # Tarefas pendentes
            pending_tasks = self.supabase.table('tasks').select('*', count='exact').eq('status', 'pending').execute()
            overdue_tasks = self.supabase.table('tasks').select('*', count='exact').eq('status', 'pending').lt('due_date', now.isoformat()).execute()
            
            # Leads por status
            leads_by_status = self.supabase.table('leads').select('status', count='exact').execute()
            
            # Top 5 leads mais recentes
            recent_leads = self.supabase.table('leads').select('*').order('created_at', desc=True).limit(5).execute()
            
            # Contratos pendentes
            pending_contracts = self.supabase.table('contracts').select('*', count='exact').eq('status', 'pending').execute()
            
            # Pipeline de vendas
            pipeline_data = await self.get_sales_pipeline()
            
            # Métricas de performance por agente (se aplicável)
            agent_performance = await self.get_agent_performance()
            
            return {
                'timestamp': now.isoformat(),
                'conversations': {
                    'today': conversations_today.count,
                    'month': conversations_month.count
                },
                'leads': {
                    'today': leads_today.count,
                    'month': leads_month.count,
                    'by_status': leads_by_status.data,
                    'recent': recent_leads.data
                },
                'proposals': {
                    'sent_today': proposals_sent_today.count,
                    'signed_today': proposals_signed_today.count
                },
                'revenue': {
                    'current_month': current_revenue,
                    'last_month': last_revenue,
                    'growth_percentage': revenue_growth
                },
                'tasks': {
                    'pending': pending_tasks.count,
                    'overdue': overdue_tasks.count
                },
                'contracts': {
                    'pending': pending_contracts.count
                },
                'conversion_rate': conversion_rate,
                'pipeline': pipeline_data,
                'agent_performance': agent_performance
            }
            
        except Exception as e:
            print(f"Erro ao coletar métricas: {e}")
            return {}
    
    async def get_sales_pipeline(self) -> Dict[str, Any]:
        """Obtém dados do pipeline de vendas"""
        try:
            # Propostas por status
            pipeline_stages = [
                'draft', 'sent', 'viewed', 'negotiating', 'signed', 'rejected'
            ]
            
            pipeline_data = {}
            total_value = 0
            
            for stage in pipeline_stages:
                result = self.supabase.table('proposals').select('total_value.sum()', count='exact').eq('status', stage).execute()
                pipeline_data[stage] = {
                    'count': result.count,
                    'value': result.data[0].get('sum', 0) if result.data else 0
                }
                total_value += pipeline_data[stage]['value']
            
            pipeline_data['total_value'] = total_value
            return pipeline_data
            
        except Exception as e:
            print(f"Erro ao obter pipeline: {e}")
            return {}
    
    async def get_agent_performance(self) -> Dict[str, Any]:
        """Obtém performance dos agentes/responsáveis"""
        try:
            # Tarefas por responsável
            tasks_by_agent = self.supabase.table('tasks').select('assigned_to', count='exact').execute()
            
            # Leads por responsável
            leads_by_agent = self.supabase.table('leads').select('assigned_to', count='exact').execute()
            
            # Tempo médio de resposta (simulado - você pode implementar baseado em logs)
            response_times = {}
            
            return {
                'tasks_by_agent': tasks_by_agent.data,
                'leads_by_agent': leads_by_agent.data,
                'avg_response_times': response_times
            }
            
        except Exception as e:
            print(f"Erro ao obter performance: {e}")
            return {}
    
    async def get_historical_data(self, days: int = 30) -> Dict[str, Any]:
        """Obtém dados históricos para gráficos"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Dados diários de conversas e leads
            daily_data = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.date().isoformat()
                next_date_str = (current_date + timedelta(days=1)).date().isoformat()
                
                conversations = self.supabase.table('conversations').select('*', count='exact').gte('created_at', date_str).lt('created_at', next_date_str).execute()
                leads = self.supabase.table('leads').select('*', count='exact').gte('created_at', date_str).lt('created_at', next_date_str).execute()
                
                daily_data.append({
                    'date': date_str,
                    'conversations': conversations.count,
                    'leads': leads.count
                })
                
                current_date += timedelta(days=1)
            
            return {'daily_data': daily_data}
            
        except Exception as e:
            print(f"Erro ao obter dados históricos: {e}")
            return {}
    
    async def get_alerts(self) -> List[Dict[str, Any]]:
        """Obtém alertas do sistema"""
        alerts = []
        
        try:
            now = datetime.now()
            
            # Alertas de tarefas atrasadas
            overdue_tasks = self.supabase.table('tasks').select('*').eq('status', 'pending').lt('due_date', now.isoformat()).execute()
            
            if overdue_tasks.count > 0:
                alerts.append({
                    'type': 'warning',
                    'title': 'Tarefas Atrasadas',
                    'message': f'{overdue_tasks.count} tarefas estão atrasadas',
                    'count': overdue_tasks.count
                })
            
            # Alertas de propostas não visualizadas há mais de 3 dias
            three_days_ago = now - timedelta(days=3)
            old_proposals = self.supabase.table('proposals').select('*').eq('status', 'sent').lt('sent_at', three_days_ago.isoformat()).execute()
            
            if old_proposals.count > 0:
                alerts.append({
                    'type': 'info',
                    'title': 'Propostas Pendentes',
                    'message': f'{old_proposals.count} propostas enviadas há mais de 3 dias sem resposta',
                    'count': old_proposals.count
                })
            
            # Alertas de contratos pendentes há mais de 5 dias
            five_days_ago = now - timedelta(days=5)
            old_contracts = self.supabase.table('contracts').select('*').eq('status', 'pending').lt('created_at', five_days_ago.isoformat()).execute()
            
            if old_contracts.count > 0:
                alerts.append({
                    'type': 'error',
                    'title': 'Contratos Pendentes',
                    'message': f'{old_contracts.count} contratos pendentes há mais de 5 dias',
                    'count': old_contracts.count
                })
            
            # Alerta de baixa conversão (menos de 10%)
            month_start = now.replace(day=1)
            conversations_month = self.supabase.table('conversations').select('*', count='exact').gte('created_at', month_start.isoformat()).execute()
            leads_month = self.supabase.table('leads').select('*', count='exact').gte('created_at', month_start.isoformat()).execute()
            
            if conversations_month.count > 0:
                conversion_rate = (leads_month.count / conversations_month.count) * 100
                if conversion_rate < 10:
                    alerts.append({
                        'type': 'warning',
                        'title': 'Taxa de Conversão Baixa',
                        'message': f'Taxa de conversão este mês: {conversion_rate:.1f}%',
                        'count': conversion_rate
                    })
            
            return alerts
            
        except Exception as e:
            print(f"Erro ao obter alertas: {e}")
            return []

# Instância global do dashboard
dashboard_manager = DashboardManager()

# Função para atualização periódica das métricas
async def periodic_metrics_update():
    """Atualiza métricas a cada 30 segundos"""
    while True:
        try:
            metrics = await dashboard_manager.get_real_time_metrics()
            alerts = await dashboard_manager.get_alerts()
            
            data = {
                'type': 'metrics_update',
                'metrics': metrics,
                'alerts': alerts
            }
            
            await dashboard_manager.broadcast_metrics(data)
            await asyncio.sleep(30)  # Atualiza a cada 30 segundos
            
        except Exception as e:
            print(f"Erro na atualização periódica: {e}")
            await asyncio.sleep(30)