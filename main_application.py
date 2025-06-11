"""
Main Application - Crânios
Orquestrador principal do sistema de automação
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import uuid
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Imports dos serviços
from ai_processor_service import AIProcessor
from proposal_generator_service import ProposalGenerator
from contract_manager_service import ContractManager
from task_manager_service import TaskManager
from financial_manager_service import FinancialManager
from drive_integration_service import DriveKnowledgeBase
from evolution_api_service import EvolutionAPIService
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LeadData:
    """Estrutura de dados do lead"""
    phone: str
    name: str = ""
    business_type: str = ""
    company_size: str = ""
    main_challenge: str = ""
    lead_source: str = ""
    qualification_score: int = 0
    status: str = "new"

@dataclass
class ConversationContext:
    """Contexto da conversa"""
    conversation_id: str
    phone: str
    current_step: str = "initial"
    collected_data: Dict = None
    lead_data: LeadData = None
    
    def __post_init__(self):
        if self.collected_data is None:
            self.collected_data = {}
        if self.lead_data is None:
            self.lead_data = LeadData(phone=self.phone)

class CraniosOrchestrator:
    """Orquestrador principal do sistema Crânios"""
    
    def __init__(self):
        self.setup_environment()
        self.initialize_services()
        self.active_conversations: Dict[str, ConversationContext] = {}
        
    def setup_environment(self):
        """Configuração das variáveis de ambiente"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.evolution_api_url = os.getenv("EVOLUTION_API_URL")
        self.evolution_api_key = os.getenv("EVOLUTION_API_KEY")
        self.arcee_api_key = os.getenv("ARCEE_API_KEY")
        self.google_drive_credentials = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        
        if not all([self.supabase_url, self.supabase_key, self.evolution_api_url]):
            raise ValueError("Variáveis de ambiente obrigatórias não configuradas")
    
    def initialize_services(self):
        """Inicialização de todos os serviços"""
        try:
            # Supabase client
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            
            # Inicialização dos serviços
            self.ai_processor = AIProcessor(self.arcee_api_key, self.supabase)
            self.proposal_generator = ProposalGenerator(self.supabase)
            self.contract_manager = ContractManager(self.supabase)
            self.task_manager = TaskManager(self.supabase)
            self.financial_manager = FinancialManager(self.supabase)
            self.drive_knowledge = DriveKnowledgeBase()
            self.evolution_api = EvolutionAPIService(self.evolution_api_url, self.evolution_api_key)
            
            logger.info("Todos os serviços inicializados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro na inicialização dos serviços: {e}")
            raise
    
    async def process_whatsapp_message(self, webhook_data: Dict) -> Dict:
        """Processa mensagem recebida do WhatsApp"""
        try:
            # Extrai dados da mensagem
            phone = webhook_data.get('phone', '').replace('+', '')
            message = webhook_data.get('message', '')
            
            if not phone or not message:
                logger.warning("Mensagem inválida recebida")
                return {"status": "error", "message": "Dados inválidos"}
            
            # Busca ou cria contexto da conversa
            context = await self.get_or_create_conversation_context(phone)
            
            # Processa a mensagem baseado no step atual
            response = await self.process_conversation_step(context, message)
            
            # Salva contexto atualizado
            await self.save_conversation_context(context)
            
            # Envia resposta via WhatsApp
            await self.evolution_api.send_message(phone, response)
            
            return {"status": "success", "response": response}
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do WhatsApp: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_or_create_conversation_context(self, phone: str) -> ConversationContext:
        """Busca ou cria contexto da conversa"""
        try:
            # Busca conversa existente
            result = self.supabase.table('conversations').select('*').eq('phone', phone).execute()
            
            if result.data:
                conversation_data = result.data[0]
                context = ConversationContext(
                    conversation_id=conversation_data['id'],
                    phone=phone,
                    current_step=conversation_data.get('status', 'initial'),
                    collected_data=conversation_data.get('context', {}),
                    lead_data=LeadData(
                        phone=phone,
                        name=conversation_data.get('name', ''),
                        business_type=conversation_data.get('business_type', ''),
                        company_size=conversation_data.get('company_size', ''),
                        main_challenge=conversation_data.get('main_challenge', ''),
                        lead_source=conversation_data.get('lead_source', '')
                    )
                )
            else:
                # Cria nova conversa
                conversation_id = str(uuid.uuid4())
                context = ConversationContext(
                    conversation_id=conversation_id,
                    phone=phone
                )
                
                # Salva no banco
                self.supabase.table('conversations').insert({
                    'id': conversation_id,
                    'phone': phone,
                    'status': 'initial',
                    'context': {},
                    'created_at': datetime.now().isoformat()
                }).execute()
            
            return context
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar contexto: {e}")
            raise
    
    async def process_conversation_step(self, context: ConversationContext, message: str) -> str:
        """Processa o step atual da conversa"""
        try:
            if context.current_step == "initial":
                return await self.handle_initial_contact(context, message)
            elif context.current_step == "lead_source":
                return await self.handle_lead_source(context, message)
            elif context.current_step == "business_type":
                return await self.handle_business_type(context, message)
            elif context.current_step == "company_size":
                return await self.handle_company_size(context, message)
            elif context.current_step == "main_challenge":
                return await self.handle_main_challenge(context, message)
            elif context.current_step == "qualification_complete":
                return await self.handle_qualified_lead(context, message)
            else:
                return await self.handle_general_conversation(context, message)
                
        except Exception as e:
            logger.error(f"Erro ao processar step da conversa: {e}")
            return "Desculpe, ocorreu um erro. Pode repetir sua mensagem?"
    
    async def handle_initial_contact(self, context: ConversationContext, message: str) -> str:
        """Maneja o primeiro contato"""
        # Extrai nome da mensagem se possível
        if any(word in message.lower() for word in ['meu nome é', 'sou', 'me chamo']):
            name = self.extract_name_from_message(message)
            context.lead_data.name = name
        
        context.current_step = "lead_source"
        
        greeting = f"Olá{' ' + context.lead_data.name if context.lead_data.name else ''}! 👋\n\n"
        greeting += "Sou a Ana, assistente virtual da Crânios. Como prefere que te chame?\n\n"
        greeting += "Antes de mais nada, como você nos conheceu?\n\n"
        greeting += "1️⃣ Lívia Team\n"
        greeting += "2️⃣ Indicação de um cliente\n"
        greeting += "3️⃣ Redes sociais\n"
        greeting += "4️⃣ Pesquisa no Google\n"
        greeting += "5️⃣ Outro\n\n"
        greeting += "Digite o número da opção ou me conte como soube da gente! 😊"
        
        return greeting
    
    async def handle_lead_source(self, context: ConversationContext, message: str) -> str:
        """Maneja a origem do lead"""
        lead_sources = {
            "1": "Lívia Team",
            "2": "Indicação de cliente",
            "3": "Redes sociais",
            "4": "Pesquisa no Google",
            "5": "Outro"
        }
        
        source = lead_sources.get(message.strip(), message.strip())
        context.lead_data.lead_source = source
        context.current_step = "business_type"
        
        response = f"Perfeito! 🎯\n\n"
        response += "Para eu te ajudar melhor, qual sua área de atuação?\n\n"
        response += "1️⃣ Saúde (médico, dentista, clínica)\n"
        response += "2️⃣ Comércio (loja, pet shop, restaurante)\n"
        response += "3️⃣ Serviços (advogado, corretor, consultor)\n"
        response += "4️⃣ Imobiliária\n"
        response += "5️⃣ Outro\n\n"
        response += "Digite o número ou me conte sua área! 📋"
        
        return response
    
    async def handle_business_type(self, context: ConversationContext, message: str) -> str:
        """Maneja o tipo de negócio"""
        business_types = {
            "1": "Saúde",
            "2": "Comércio", 
            "3": "Serviços",
            "4": "Imobiliária",
            "5": "Outro"
        }
        
        business_type = business_types.get(message.strip(), message.strip())
        context.lead_data.business_type = business_type
        context.current_step = "company_size"
        
        response = f"Excelente! 👍\n\n"
        response += "Para dimensionar melhor a solução:\n\n"
        response += "1️⃣ Trabalho sozinho(a)\n"
        response += "2️⃣ Tenho 2-5 funcionários\n"
        response += "3️⃣ Tenho 6-15 funcionários\n"
        response += "4️⃣ Tenho mais de 15 funcionários\n\n"
        response += "Qual se encaixa melhor? 🏢"
        
        return response
    
    async def handle_company_size(self, context: ConversationContext, message: str) -> str:
        """Maneja o tamanho da empresa"""
        company_sizes = {
            "1": "Solo",
            "2": "2-5 funcionários",
            "3": "6-15 funcionários", 
            "4": "15+ funcionários"
        }
        
        company_size = company_sizes.get(message.strip(), message.strip())
        context.lead_data.company_size = company_size
        context.current_step = "main_challenge"
        
        response = f"Perfeito! 📊\n\n"
        response += "E qual seu maior desafio hoje?\n\n"
        response += "1️⃣ Muito tempo perdido com tarefas repetitivas\n"
        response += "2️⃣ Atendimento ao cliente demorado/limitado\n"
        response += "3️⃣ Perda de clientes por falta de follow-up\n"
        response += "4️⃣ Controle financeiro/administrativo\n"
        response += "5️⃣ Captação de novos clientes\n\n"
        response += "Qual é sua maior dor? 🎯"
        
        return response
    
    async def handle_main_challenge(self, context: ConversationContext, message: str) -> str:
        """Maneja o principal desafio e finaliza qualificação"""
        challenges = {
            "1": "Tarefas repetitivas",
            "2": "Atendimento limitado",
            "3": "Falta de follow-up",
            "4": "Controle financeiro",
            "5": "Captação de clientes"
        }
        
        challenge = challenges.get(message.strip(), message.strip())
        context.lead_data.main_challenge = challenge
        context.current_step = "qualification_complete"
        
        # Calcula score de qualificação
        context.lead_data.qualification_score = self.calculate_qualification_score(context.lead_data)
        
        # Salva lead qualificado
        await self.save_qualified_lead(context.lead_data)
        
        # Busca conhecimento específico do Drive
        knowledge = await self.drive_knowledge.get_knowledge_for_business(context.lead_data.business_type)
        
        # Gera resposta personalizada com IA
        response = await self.ai_processor.generate_personalized_response(
            context.lead_data, 
            challenge,
            knowledge
        )
        
        return response
    
    async def handle_qualified_lead(self, context: ConversationContext, message: str) -> str:
        """Maneja lead qualificado - pode gerar proposta"""
        # Analisa intenção da mensagem
        if any(word in message.lower() for word in ['proposta', 'orçamento', 'preço', 'valor', 'investimento']):
            # Gera proposta automaticamente
            proposal = await self.proposal_generator.generate_proposal(context.lead_data)
            
            # Agenda follow-up
            await self.schedule_follow_up(context.lead_data.phone, 24)  # 24 horas
            
            return proposal
        else:
            # Usa IA para resposta personalizada
            knowledge = await self.drive_knowledge.get_knowledge_for_business(context.lead_data.business_type)
            response = await self.ai_processor.process_message(
                message, 
                context.collected_data, 
                context.lead_data.business_type,
                knowledge
            )
            return response
    
    async def handle_general_conversation(self, context: ConversationContext, message: str) -> str:
        """Maneja conversa geral com IA"""
        knowledge = await self.drive_knowledge.get_knowledge_for_business(context.lead_data.business_type)
        response = await self.ai_processor.process_message(
            message, 
            context.collected_data, 
            context.lead_data.business_type,
            knowledge
        )
        return response
    
    def extract_name_from_message(self, message: str) -> str:
        """Extrai nome da mensagem"""
        # Implementação simples - pode ser melhorada
        words = message.split()
        for i, word in enumerate(words):
            if word.lower() in ['nome', 'sou', 'chamo']:
                if i + 1 < len(words):
                    return words[i + 1].title()
        return ""
    
    def calculate_qualification_score(self, lead_data: LeadData) -> int:
        """Calcula score de qualificação do lead"""
        score = 0
        
        # Score por tipo de negócio
        business_scores = {
            "Saúde": 90,
            "Imobiliária": 85,
            "Serviços": 80,
            "Comércio": 75
        }
        score += business_scores.get(lead_data.business_type, 60)
        
        # Score por tamanho da empresa
        size_scores = {
            "15+ funcionários": 30,
            "6-15 funcionários": 25,
            "2-5 funcionários": 20,
            "Solo": 15
        }
        score += size_scores.get(lead_data.company_size, 10)
        
        # Score por desafio
        challenge_scores = {
            "Atendimento limitado": 25,
            "Falta de follow-up": 20,
            "Tarefas repetitivas": 20,
            "Captação de clientes": 15,
            "Controle financeiro": 15
        }
        score += challenge_scores.get(lead_data.main_challenge, 10)
        
        return min(score, 100)  # Máximo 100
    
    async def save_qualified_lead(self, lead_data: LeadData) -> None:
        """Salva lead qualificado no banco"""
        try:
            self.supabase.table('leads').insert({
                'id': str(uuid.uuid4()),
                'name': lead_data.name,
                'phone': lead_data.phone,
                'business_type': lead_data.business_type,
                'company_size': lead_data.company_size,
                'main_challenge': lead_data.main_challenge,
                'lead_source': lead_data.lead_source,
                'qualification_score': lead_data.qualification_score,
                'status': 'qualified',
                'created_at': datetime.now().isoformat()
            }).execute()
            
            logger.info(f"Lead qualificado salvo: {lead_data.phone}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar lead: {e}")
    
    async def save_conversation_context(self, context: ConversationContext) -> None:
        """Salva contexto da conversa"""
        try:
            self.supabase.table('conversations').update({
                'name': context.lead_data.name,
                'business_type': context.lead_data.business_type,
                'company_size': context.lead_data.company_size,
                'main_challenge': context.lead_data.main_challenge,
                'lead_source': context.lead_data.lead_source,
                'status': context.current_step,
                'context': context.collected_data,
                'updated_at': datetime.now().isoformat()
            }).eq('id', context.conversation_id).execute()
            
        except Exception as e:
            logger.error(f"Erro ao salvar contexto: {e}")
    
    async def schedule_follow_up(self, phone: str, hours: int) -> None:
        """Agenda follow-up automático"""
        # Implementar com celery ou similar para jobs assíncronos
        pass
    
    async def process_payment_webhook(self, payment_data: Dict) -> Dict:
        """Processa webhook de pagamento"""
        try:
            # Processa pagamento
            result = await self.financial_manager.process_payment(payment_data)
            
            if result['status'] == 'approved':
                # Cria contrato
                contract = await self.contract_manager.create_contract(payment_data['proposal_id'])
                
                # Cria tarefas de implementação
                await self.task_manager.create_implementation_tasks(
                    payment_data['client_id'],
                    payment_data['service_type']
                )
                
                # Notifica cliente
                await self.evolution_api.send_message(
                    payment_data['phone'],
                    f"🎉 Pagamento confirmado! Seu contrato foi enviado para assinatura. "
                    f"Link: {contract['signing_url']}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao processar pagamento: {e}")
            return {"status": "error", "message": str(e)}

# FastAPI Application
app = FastAPI(title="Crânios Automation System", version="1.0.0")
orchestrator = CraniosOrchestrator()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook para mensagens do WhatsApp"""
    try:
        data = await request.json()
        
        # Processa mensagem em background
        background_tasks.add_task(orchestrator.process_whatsapp_message, data)
        
        return JSONResponse({"status": "received"})
        
    except Exception as e:
        logger.error(f"Erro no webhook WhatsApp: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/payment")
async def payment_webhook(request: Request):
    """Webhook para pagamentos"""
    try:
        data = await request.json()
        result = await orchestrator.process_payment_webhook(data)
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Erro no webhook pagamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

from apscheduler.schedulers.background import BackgroundScheduler
import time

def follow_up_pending_payments():
    try:
        payments = orchestrator.supabase.table("payments").select("*").eq("status", "pending").execute()
        for payment in payments.data:
            created_time = datetime.fromisoformat(payment["created_at"])
            if (datetime.now() - created_time).total_seconds() > 3600:  # 1 hora
                phone = payment["phone"]
                url = payment["checkout_url"]
                msg = f"Olá! 🌟 Notamos que você iniciou um pagamento na Crânios mas não finalizou. Caso precise, seu link está aqui: {url}"
                orchestrator.evolution_api.send_message(phone, msg)
    except Exception as e:
        logger.error(f"Erro no follow-up: {e}")

# Inicia o agendador
scheduler = BackgroundScheduler()
scheduler.add_job(follow_up_pending_payments, "interval", minutes=60)
scheduler.start()
