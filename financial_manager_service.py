"""
Financial Manager Service - Crânios
Gerenciador automático de financeiro e pagamentos
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import logging
from supabase import create_client, Client
import uuid
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialManager:
    def __init__(self):
        # Configurações
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.evolution_api_url = os.getenv('EVOLUTION_API_URL')
        self.evolution_api_key = os.getenv('EVOLUTION_API_KEY')
        self.pix_api_url = os.getenv('PIX_API_URL')
        self.pix_api_key = os.getenv('PIX_API_KEY')
        
        # Inicializar cliente
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    async def create_receivable(self, contract_data: Dict) -> Dict[str, Any]:
        """Cria conta a receber baseada no contrato"""
        try:
            # Calcular parcelas se for parcelado
            total_amount = float(contract_data['total_value'])
            implementation_fee = float(contract_data.get('implementation_fee', 0))
            monthly_fee = float(contract_data.get('monthly_fee', 0))
            
            receivables = []
            
            # Taxa de implementação (à vista)
            if implementation_fee > 0:
                implementation_receivable = {
                    "id": str(uuid.uuid4()),
                    "client_id": contract_data['client_id'],
                    "type": "receivable",
                    "description": f"Taxa de Implementação - {contract_data['client_name']}",
                    "amount": implementation_fee,
                    "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
                    "status": "pending",
                    "category": "implementation",
                    "created_at": datetime.now().isoformat()
                }
                
                # Gerar link PIX
                pix_data = await self._generate_pix_payment(implementation_receivable)
                if pix_data:
                    implementation_receivable["pix_link"] = pix_data["pix_url"]
                    implementation_receivable["pix_code"] = pix_data["pix_code"]
                
                result = self.supabase.table('financial_transactions').insert(implementation_receivable).execute()
                if result.data:
                    receivables.append(result.data[0])
                    # Enviar cobrança por WhatsApp
                    await self._send_payment_reminder(implementation_receivable, is_new=True)
            
            # Mensalidades recorrentes
            if monthly_fee > 0:
                contract_months = contract_data.get('contract_months', 12)
                
                for month in range(contract_months):
                    due_date = datetime.now() + timedelta(days=30 * (month + 1))
                    
                    monthly_receivable = {
                        "id": str(uuid.uuid4()),
                        "client_id": contract_data['client_id'],
                        "type": "receivable",
                        "description": f"Mensalidade {month + 1}/{contract_months} - {contract_data['client_name']}",
                        "amount": monthly_fee,
                        "due_date": due_date.date().isoformat(),
                        "status": "pending",
                        "category": "monthly",
                        "installment_number": month + 1,
                        "total_installments": contract_months,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    result = self.supabase.table('financial_transactions').insert(monthly_receivable).execute()
                    if result.data:
                        receivables.append(result.data[0])
            
            return {
                "success": True,
                "receivables_created": len(receivables),
                "receivables": receivables
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar contas a receber: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _generate_pix_payment(self, transaction_data: Dict) -> Optional[Dict[str, Any]]:
        """Gera pagamento PIX"""
        try:
            # Configuração do PIX (ajustar conforme sua API)
            pix_payload = {
                "value": float(transaction_data['amount']),
                "description": transaction_data['description'],
                "external_id": transaction_data['id'],
                "expires_in": 7 * 24 * 60 * 60  # 7 dias em segundos
            }
            
            headers = {
                "Authorization": f"Bearer {self.pix_api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.pix_api_url}/charges",
                    json=pix_payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "pix_url": data.get('qr_code_url'),
                            "pix_code": data.get('qr_code'),
                            "charge_id": data.get('id')
                        }
                    else:
                        logger.error(f"Erro ao gerar PIX: {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"Erro na geração PIX: {str(e)}")
            return None
    
    async def _send_payment_reminder(self, transaction: Dict, is_new: bool = False):
        """Envia lembrete de pagamento via WhatsApp"""
        try:
            # Buscar dados do cliente
            client_result = self.supabase.table('leads').select('*').eq('id', transaction['client_id']).execute()
            
            if not client_result.data:
                logger.error(f"Cliente não encontrado: {transaction['client_id']}")
                return
            
            client = client_result.data[0]
            phone = client.get('phone')
            
            if not phone:
                logger.error(f"Telefone não encontrado para cliente: {client['name']}")
                return
            
            # Formatar valor
            amount = f"R$ {float(transaction['amount']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            due_date = datetime.fromisoformat(transaction['due_date']).strftime('%d/%m/%Y')
            
            if is_new:
                message = f"🔥 *Olá {client['name']}!*\n\n"
                message += f"Sua cobrança está pronta! 💰\n\n"
                message += f"📄 *Descrição:* {transaction['description']}\n"
                message += f"💵 *Valor:* {amount}\n"
                message += f"📅 *Vencimento:* {due_date}\n\n"
                
                if transaction.get('pix_link'):
                    message += f"🔗 *Link do PIX:* {transaction['pix_link']}\n\n"
                
                if transaction.get('pix_code'):
                    message += f"📱 *Código PIX Copia e Cola:*\n`{transaction['pix_code']}`\n\n"
                
                message += "✅ Pagamento confirmado automaticamente!\n"
                message += "📞 Dúvidas? Só chamar!\n\n"
                message += "_Crânios - Automação Inteligente_ 🧠"
            else:
                # Lembrete de vencimento
                message = f"⚠️ *Lembrete de Pagamento*\n\n"
                message += f"Olá {client['name']}, sua cobrança vence em breve:\n\n"
                message += f"📄 {transaction['description']}\n"
                message += f"💵 *Valor:* {amount}\n"
                message += f"📅 *Vencimento:* {due_date}\n\n"
                
                if transaction.get('pix_link'):
                    message += f"🔗 *Link do PIX:* {transaction['pix_link']}\n\n"
                
                message += "Efetue o pagamento para manter seus serviços ativos! ✅"
            
            await self._send_whatsapp_message(phone, message)
            
        except Exception as e:
            logger.error(f"Erro ao enviar lembrete: {str(e)}")
    
    async def _send_whatsapp_message(self, phone: str, message: str):
        """Envia mensagem via WhatsApp"""
        try:
            url = f"{self.evolution_api_url}/message/sendText"
            headers = {
                "Content-Type": "application/json",
                "apikey": self.evolution_api_key
            }
            
            payload = {
                "number": phone,
                "text": message
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        logger.info(f"Mensagem enviada para {phone}")
                    else:
                        logger.error(f"Erro ao enviar mensagem: {response.status}")
        
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {str(e)}")
    
    async def process_payment_webhook(self, webhook_data: Dict) -> Dict[str, Any]:
        """Processa webhook de pagamento confirmado"""
        try:
            # Extrair dados do webhook (ajustar conforme sua API PIX)
            charge_id = webhook_data.get('charge_id')
            transaction_id = webhook_data.get('external_id')
            status = webhook_data.get('status')
            paid_amount = webhook_data.get('amount')
            
            if status != 'paid':
                return {"success": False, "message": "Payment not confirmed"}
            
            # Atualizar transação no banco
            update_data = {
                "status": "paid",
                "paid_at": datetime.now().isoformat(),
                "paid_amount": paid_amount,
                "charge_id": charge_id,
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table('financial_transactions').update(update_data).eq('id', transaction_id).execute()
            
            if result.data:
                transaction = result.data[0]
                
                # Notificar cliente sobre pagamento confirmado
                await self._send_payment_confirmation(transaction)
                
                # Se for taxa de implementação, criar tarefas automaticamente
                if transaction['category'] == 'implementation':
                    await self._trigger_implementation_tasks(transaction)
                
                # Atualizar métricas financeiras
                await self._update_financial_metrics()
                
                return {
                    "success": True,
                    "transaction": transaction
                }
            
            return {"success": False, "error": "Transaction not found"}
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _send_payment_confirmation(self, transaction: Dict):
        """Envia confirmação de pagamento"""
        try:
            # Buscar dados do cliente
            client_result = self.supabase.table('leads').select('*').eq('id', transaction['client_id']).execute()
            
            if client_result.data:
                client = client_result.data[0]
                phone = client.get('phone')
                
                if phone:
                    amount = f"R$ {float(transaction['amount']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    message = f"✅ *Pagamento Confirmado!*\n\n"
                    message += f"Olá {client['name']}, recebemos seu pagamento! 🎉\n\n"
                    message += f"📄 *Descrição:* {transaction['description']}\n"
                    message += f"💵 *Valor:* {amount}\n"
                    message += f"📅 *Data:* {datetime.now().strftime('%d/%m/%Y às %H:%M')}\n\n"
                    
                    if transaction['category'] == 'implementation':
                        message += "🚀 *Próximos passos:*\n"
                        message += "• Nossa equipe já foi notificada\n"
                        message += "• Implementação iniciará em até 24h\n"
                        message += "• Você receberá atualizações do progresso\n\n"
                    
                    message += "Obrigado por confiar na Crânios! 🧠✨"
                    
                    await self._send_whatsapp_message(phone, message)
        
        except Exception as e:
            logger.error(f"Erro ao enviar confirmação: {str(e)}")
    
    async def _trigger_implementation_tasks(self, transaction: Dict):
        """Dispara criação de tarefas após pagamento da implementação"""
        try:
            # Importar TaskManager (evitar import circular)
            from task_manager import TaskManager
            
            task_manager = TaskManager()
            
            # Buscar dados do contrato
            proposal_result = self.supabase.table('proposals').select('*').eq('lead_id', transaction['client_id']).execute()
            
            if proposal_result.data:
                proposal = proposal_result.data[0]
                service_type = proposal.get('service_type', 'default')
                
                contract_data = {
                    'client_name': proposal.get('client_name'),
                    'service_type': service_type
                }
                
                # Criar tarefas de implementação
                await task_manager.create_implementation_tasks(
                    transaction['client_id'],
                    service_type,
                    contract_data
                )
                
                logger.info(f"Tarefas de implementação criadas para cliente {transaction['client_id']}")
        
        except Exception as e:
            logger.error(f"Erro ao disparar tarefas: {str(e)}")
    
    async def check_overdue_payments(self) -> Dict[str, Any]:
        """Verifica pagamentos em atraso"""
        try:
            current_date = datetime.now().date().isoformat()
            
            # Buscar pagamentos vencidos
            result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'pending').lt('due_date', current_date).execute()
            
            overdue_payments = result.data if result.data else []
            
            notifications_sent = 0
            
            for payment in overdue_payments:
                # Calcular dias de atraso
                due_date = datetime.fromisoformat(payment['due_date'])
                days_overdue = (datetime.now().date() - due_date.date()).days
                
                # Enviar notificação baseada nos dias de atraso
                if days_overdue in [1, 3, 7, 15, 30]:  # Notificar em dias específicos
                    await self._send_overdue_notification(payment, days_overdue)
                    notifications_sent += 1
                
                # Marcar como vencido se ainda não estiver
                if payment['status'] != 'overdue':
                    self.supabase.table('financial_transactions').update({
                        'status': 'overdue',
                        'updated_at': datetime.now().isoformat()
                    }).eq('id', payment['id']).execute()
            
            return {
                "success": True,
                "overdue_count": len(overdue_payments),
                "notifications_sent": notifications_sent,
                "overdue_payments": overdue_payments
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar pagamentos vencidos: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _send_overdue_notification(self, payment: Dict, days_overdue: int):
        """Envia notificação de pagamento vencido"""
        try:
            # Buscar dados do cliente
            client_result = self.supabase.table('leads').select('*').eq('id', payment['client_id']).execute()
            
            if not client_result.data:
                return
            
            client = client_result.data[0]
            phone = client.get('phone')
            
            if not phone:
                return
            
            amount = f"R$ {float(payment['amount']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Mensagem personalizada baseada nos dias de atraso
            if days_overdue == 1:
                message = f"📅 *Lembrete Gentil*\n\n"
                message += f"Olá {client['name']}, sua cobrança venceu ontem:\n\n"
            elif days_overdue <= 7:
                message = f"⚠️ *Pagamento em Atraso*\n\n"
                message += f"Olá {client['name']}, sua cobrança está {days_overdue} dias em atraso:\n\n"
            elif days_overdue <= 15:
                message = f"🚨 *URGENTE - Pagamento Atrasado*\n\n"
                message += f"Olá {client['name']}, sua cobrança está {days_overdue} dias em atraso:\n\n"
            else:
                message = f"🔴 *ATENÇÃO - Suspensão de Serviços*\n\n"
                message += f"Olá {client['name']}, sua cobrança está {days_overdue} dias em atraso.\n"
                message += f"Seus serviços podem ser suspensos:\n\n"
            
            message += f"📄 *Descrição:* {payment['description']}\n"
            message += f"💵 *Valor:* {amount}\n"
            message += f"📅 *Venceu em:* {datetime.fromisoformat(payment['due_date']).strftime('%d/%m/%Y')}\n\n"
            
            if payment.get('pix_link'):
                message += f"🔗 *Link do PIX:* {payment['pix_link']}\n\n"
            
            if days_overdue >= 15:
                message += "⚠️ *Para evitar a suspensão, quite hoje mesmo!*\n\n"
            
            message += "📞 Dúvidas? Entre em contato conosco!"
            
            await self._send_whatsapp_message(phone, message)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de atraso: {str(e)}")
    
    async def _update_financial_metrics(self):
        """Atualiza métricas financeiras em tempo real"""
        try:
            # Calcular receita do mês
            current_month = datetime.now().strftime('%Y-%m')
            
            result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'paid').gte('paid_at', f'{current_month}-01').execute()
            
            monthly_revenue = sum(float(t['amount']) for t in result.data) if result.data else 0
            
            # Calcular contas a receber
            pending_result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'pending').execute()
            
            pending_amount = sum(float(t['amount']) for t in pending_result.data) if pending_result.data else 0
            
            # Salvar métricas (criar tabela se necessário)
            metrics = {
                "id": str(uuid.uuid4()),
                "month": current_month,
                "monthly_revenue": monthly_revenue,
                "pending_receivables": pending_amount,
                "updated_at": datetime.now().isoformat()
            }
            
            # Upsert nas métricas
            self.supabase.table('financial_metrics').upsert(metrics, on_conflict='month').execute()
            
            logger.info(f"Métricas atualizadas: Receita mensal: R$ {monthly_revenue:.2f}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar métricas: {str(e)}")
    
    async def generate_financial_report(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Gera relatório financeiro"""
        try:
            if not start_date:
                start_date = datetime.now().replace(day=1).date().isoformat()
            
            if not end_date:
                end_date = datetime.now().date().isoformat()
            
            # Receitas no período
            revenue_result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'paid').gte('paid_at', start_date).lte('paid_at', end_date).execute()
            
            revenues = revenue_result.data if revenue_result.data else []
            total_revenue = sum(float(r['amount']) for r in revenues)
            
            # Contas a receber
            pending_result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'pending').execute()
            
            pending_receivables = pending_result.data if pending_result.data else []
            total_pending = sum(float(p['amount']) for p in pending_receivables)
            
            # Pagamentos vencidos
            overdue_result = self.supabase.table('financial_transactions').select('*').eq('type', 'receivable').eq('status', 'overdue').execute()
            
            overdue_payments = overdue_result.data if overdue_result.data else []
            total_overdue = sum(float(o['amount']) for o in overdue_payments)
            
            # Receitas por categoria
            revenue_by_category = {}
            for revenue in revenues:
                category = revenue.get('category', 'other')
                if category not in revenue_by_category:
                    revenue_by_category[category] = 0
                revenue_by_category[category] += float(revenue['amount'])
            
            report = {
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "revenue": {
                    "total": total_revenue,
                    "count": len(revenues),
                    "by_category": revenue_by_category
                },
                "receivables": {
                    "pending_total": total_pending,
                    "pending_count": len(pending_receivables),
                    "overdue_total": total_overdue,
                    "overdue_count": len(overdue_payments)
                },
                "summary": {
                    "total_expected": total_revenue + total_pending + total_overdue,
                    "collection_rate": (total_revenue / (total_revenue + total_overdue) * 100) if (total_revenue + total_overdue) > 0 else 0
                }
            }
            
            return {
                "success": True,
                "report": report
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório financeiro: {str(e)}")
            return {"success": False, "error": str(e)}

# Função para executar verificações periódicas
async def run_financial_checks():
    """Executa verificações financeiras periódicas"""
    financial_manager = FinancialManager()
    
    while True:
        try:
            # Verificar pagamentos vencidos (executa diariamente às 9h)
            current_hour = datetime.now().hour
            if current_hour == 9:
                await financial_manager.check_overdue_payments()
                logger.info("Verificação de pagamentos vencidos executada")
            
            # Atualizar métricas (executa a cada hora)
            await financial_manager._update_financial_metrics()
            
            # Aguardar 1 hora
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Erro na verificação financeira: {str(e)}")
            await asyncio.sleep(300)  # Aguardar 5 minutos em caso de erro

if __name__ == "__main__":
    # Para testar o sistema
    import asyncio
    
    async def test_financial_manager():
        fm = FinancialManager()
        
        # Teste de criação de conta a receber
        contract_data = {
            "client_id": "123",
            "client_name": "Teste Cliente",
            "total_value": 5000,
            "implementation_fee": 2000,
            "monthly_fee": 500,
            "contract_months": 12
        }
        
        result = await fm.create_receivable(contract_data)
        print(f"Contas criadas: {result}")
        
        # Teste de relatório
        report = await fm.generate_financial_report()
        print(f"Relatório: {report}")
    
    # asyncio.run(test_financial_manager())
