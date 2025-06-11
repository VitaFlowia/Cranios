16-celery_tasks/follow_up_tasks.py

"""
Tarefas Celery para Follow-up automático
Gerencia follow-ups de leads, propostas e contratos
"""
import os
import asyncio
from datetime import datetime, timedelta
from celery import current_app
from celery.utils.log import get_task_logger
from supabase import create_client
from evolution_api import EvolutionAPIService
from ai_processor import AIProcessor

logger = get_task_logger(__name__)

# Inicialização dos serviços
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
evolution_api = EvolutionAPIService(
    os.getenv("EVOLUTION_API_URL"), 
    os.getenv("EVOLUTION_API_KEY")
)
ai_processor = AIProcessor(os.getenv("ARCEE_API_KEY"), supabase)

@current_app.task(bind=True, max_retries=3)
def process_scheduled_follow_ups(self):
    """Processa todos os follow-ups agendados"""
    try:
        logger.info("🔄 Iniciando processamento de follow-ups...")
        
        # Busca follow-ups agendados para agora
        now = datetime.now()
        
        # Follow-ups de leads qualificados sem proposta (24h)
        leads_result = supabase.table('leads').select('*').eq('status', 'qualified').lt('created_at', (now - timedelta(hours=24)).isoformat()).execute()
        
        for lead in leads_result.data:
            # Verifica se já tem proposta
            proposal_result = supabase.table('proposals').select('*').eq('lead_id', lead['id']).execute()
            
            if not proposal_result.data:
                # Agenda follow-up de proposta
                schedule_proposal_follow_up.delay(lead['id'])
        
        # Follow-ups de propostas não visualizadas (48h)
        proposals_result = supabase.table('proposals').select('*').eq('status', 'sent').is_('viewed_at', 'null').lt('sent_at', (now - timedelta(hours=48)).isoformat()).execute()
        
        for proposal in proposals_result.data:
            schedule_proposal_reminder.delay(proposal['id'])
        
        # Follow-ups de contratos não assinados (72h)
        contracts_result = supabase.table('contracts').select('*').eq('status', 'pending').lt('created_at', (now - timedelta(hours=72)).isoformat()).execute()
        
        for contract in contracts_result.data:
            schedule_contract_reminder.delay(contract['id'])
        
        logger.info("✅ Follow-ups processados com sucesso")
        return {"status": "success", "processed": len(leads_result.data) + len(proposals_result.data) + len(contracts_result.data)}
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de follow-ups: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def schedule_proposal_follow_up(self, lead_id):
    """Envia follow-up para leads qualificados sem proposta"""
    try:
        logger.info(f"📧 Enviando follow-up de proposta para lead {lead_id}")
        
        # Busca dados do lead
        lead_result = supabase.table('leads').select('*').eq('id', lead_id).single().execute()
        lead = lead_result.data
        
        if not lead:
            logger.warning(f"Lead {lead_id} não encontrado")
            return {"status": "lead_not_found"}
        
        # Gera mensagem personalizada com IA
        context = {
            "type": "proposal_follow_up",
            "lead_name": lead['name'],
            "business_type": lead['business_type'],
            "company_size": lead['company_size'],
            "qualification_score": lead['qualification_score']
        }
        
        message = asyncio.run(ai_processor.generate_follow_up_message(context))
        
        # Envia mensagem via WhatsApp
        evolution_api.send_message(lead['phone'], message)
        
        # Registra o follow-up
        supabase.table('conversations').update({
            'updated_at': datetime.now().isoformat(),
            'context': {
                **lead.get('context', {}),
                'last_follow_up': 'proposal_reminder',
                'follow_up_count': lead.get('context', {}).get('follow_up_count', 0) + 1
            }
        }).eq('phone', lead['phone']).execute()
        
        logger.info(f"✅ Follow-up de proposta enviado para {lead['name']}")
        return {"status": "success", "lead_id": lead_id}
        
    except Exception as e:
        logger.error(f"❌ Erro no follow-up de proposta: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def schedule_proposal_reminder(self, proposal_id):
    """Envia lembrete sobre proposta não visualizada"""
    try:
        logger.info(f"📋 Enviando lembrete de proposta {proposal_id}")
        
        # Busca dados da proposta e lead
        proposal_result = supabase.table('proposals').select('*, leads(*)').eq('id', proposal_id).single().execute()
        proposal = proposal_result.data
        
        if not proposal:
            logger.warning(f"Proposta {proposal_id} não encontrada")
            return {"status": "proposal_not_found"}
        
        lead = proposal['leads']
        
        # Gera mensagem personalizada
        context = {
            "type": "proposal_reminder",
            "lead_name": lead['name'],
            "proposal_value": proposal['total_value'],
            "days_since_sent": (datetime.now() - datetime.fromisoformat(proposal['sent_at'])).days
        }
        
        message = asyncio.run(ai_processor.generate_follow_up_message(context))
        
        # Envia mensagem
        evolution_api.send_message(lead['phone'], message)
        
        # Atualiza status da proposta
        supabase.table('proposals').update({
            'status': 'reminded'
        }).eq('id', proposal_id).execute()
        
        logger.info(f"✅ Lembrete de proposta enviado para {lead['name']}")
        return {"status": "success", "proposal_id": proposal_id}
        
    except Exception as e:
        logger.error(f"❌ Erro no lembrete de proposta: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def schedule_contract_reminder(self, contract_id):
    """Envia lembrete sobre contrato não assinado"""
    try:
        logger.info(f"📝 Enviando lembrete de contrato {contract_id}")
        
        # Busca dados do contrato, proposta e lead
        contract_result = supabase.table('contracts').select('*, proposals(*, leads(*))').eq('id', contract_id).single().execute()
        contract = contract_result.data
        
        if not contract:
            logger.warning(f"Contrato {contract_id} não encontrado")
            return {"status": "contract_not_found"}
        
        proposal = contract['proposals']
        lead = proposal['leads']
        
        # Gera mensagem personalizada
        context = {
            "type": "contract_reminder",
            "lead_name": lead['name'],
            "contract_url": contract['contract_url'],
            "days_since_sent": (datetime.now() - datetime.fromisoformat(contract['created_at'])).days
        }
        
        message = asyncio.run(ai_processor.generate_follow_up_message(context))
        
        # Envia mensagem
        evolution_api.send_message(lead['phone'], message)
        
        # Atualiza status do contrato
        supabase.table('contracts').update({
            'status': 'reminded'
        }).eq('id', contract_id).execute()
        
        logger.info(f"✅ Lembrete de contrato enviado para {lead['name']}")
        return {"status": "success", "contract_id": contract_id}
        
    except Exception as e:
        logger.error(f"❌ Erro no lembrete de contrato: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def schedule_client_satisfaction_survey(self, client_id):
    """Envia pesquisa de satisfação para clientes ativos"""
    try:
        logger.info(f"📊 Enviando pesquisa de satisfação para cliente {client_id}")
        
        # Busca dados do cliente
        client_result = supabase.table('leads').select('*').eq('id', client_id).single().execute()
        client = client_result.data
        
        if not client:
            logger.warning(f"Cliente {client_id} não encontrado")
            return {"status": "client_not_found"}
        
        # Gera mensagem de pesquisa de satisfação
        context = {
            "type": "satisfaction_survey",
            "client_name": client['name'],
            "business_type": client['business_type']
        }
        
        message = asyncio.run(ai_processor.generate_follow_up_message(context))
        
        # Envia mensagem
        evolution_api.send_message(client['phone'], message)
        
        logger.info(f"✅ Pesquisa de satisfação enviada para {client['name']}")
        return {"status": "success", "client_id": client_id}
        
    except Exception as e:
        logger.error(f"❌ Erro na pesquisa de satisfação: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def schedule_upsell_opportunity(self, client_id):
    """Identifica e envia oportunidades de upsell"""
    try:
        logger.info(f"🚀 Processando oportunidade de upsell para cliente {client_id}")
        
        # Busca dados do cliente e histórico
        client_result = supabase.table('leads').select('*').eq('id', client_id).single().execute()
        client = client_result.data
        
        if not client:
            logger.warning(f"Cliente {client_id} não encontrado")
            return {"status": "client_not_found"}
        
        # Analisa oportunidades de upsell com IA
        context = {
            "type": "upsell_analysis",
            "client_name": client['name'],
            "business_type": client['business_type'],
            "company_size": client['company_size'],
            "current_services": client.get('context', {}).get('services', [])
        }
        
        upsell_analysis = asyncio.run(ai_processor.analyze_upsell_opportunity(context))
        
        if upsell_analysis.get('has_opportunity'):
            message = asyncio.run(ai_processor.generate_follow_up_message({
                **context,
                "type": "upsell_offer",
                "recommended_service": upsell_analysis['recommended_service']
            }))
            
            # Envia mensagem de upsell
            evolution_api.send_message(client['phone'], message)
            
            logger.info(f"✅ Oportunidade de upsell enviada para {client['name']}")
            return {"status": "success", "upsell_sent": True, "service": upsell_analysis['recommended_service']}
        else:
            logger.info(f"ℹ️ Nenhuma oportunidade de upsell identificada para {client['name']}")
            return {"status": "success", "upsell_sent": False}
        
    except Exception as e:
        logger.error(f"❌ Erro na análise de upsell: {str(e)}")
        raise self.retry(countdown=300, exc=e)

@current_app.task(bind=True, max_retries=3)
def process_abandoned_conversations(self):
    """Reativa conversas abandonadas há mais de 7 dias"""
    try:
        logger.info("🔄 Processando conversas abandonadas...")
        
        cutoff_date = datetime.now() - timedelta(days=7)
        
        # Busca conversas abandonadas
        conversations_result = supabase.table('conversations').select('*').eq('status', 'active').lt('updated_at', cutoff_date.isoformat()).execute()
        
        reactivated = 0
        for conversation in conversations_result.data:
            context = {
                "type": "reactivation",
                "name": conversation.get('name', 'Futuro cliente'),
                "business_type": conversation.get('business_type'),
                "days_inactive": (datetime.now() - datetime.fromisoformat(conversation['updated_at'])).days
            }
            
            message = asyncio.run(ai_processor.generate_follow_up_message(context))
            
            # Envia mensagem de reativação
            evolution_api.send_message(conversation['phone'], message)
            
            # Atualiza status da conversa
            supabase.table('conversations').update({
                'status': 'reactivation_sent',
                'updated_at': datetime.now().isoformat()
            }).eq('id', conversation['id']).execute()
            
            reactivated += 1
        
        logger.info(f"✅ {reactivated} conversas reativadas")
        return {"status": "success", "reactivated": reactivated}
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de conversas abandonadas: {str(e)}")
        raise self.retry(countdown=300, exc=e)