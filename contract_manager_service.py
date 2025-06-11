"""
Contract Manager Service - Crânios
Gerenciador automático de contratos e assinaturas digitais
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import logging
from supabase import create_client, Client
from jinja2 import Template
from dataclasses import dataclass
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContractData:
    client_name: str
    client_email: str
    client_phone: str
    client_document: str
    business_type: str
    service_description: str
    setup_fee: float
    monthly_fee: float
    contract_duration: int
    implementation_deadline: str
    special_conditions: List[str]
    payment_terms: str

class ContractManager:
    def __init__(self):
        # Configurações
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.autentique_token = os.getenv('AUTENTIQUE_API_TOKEN')
        self.evolution_api_url = os.getenv('EVOLUTION_API_URL')
        self.evolution_api_key = os.getenv('EVOLUTION_API_KEY')
        
        # URLs da API Autentique
        self.autentique_base_url = "https://api.autentique.com.br/v2"
        
        # Inicializar clientes
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Templates de contrato por tipo de serviço
        self.contract_templates = self._load_contract_templates()
    
    async def create_contract_from_proposal(self, proposal_id: str, client_data: Dict) -> Dict[str, Any]:
        """Cria contrato automaticamente após confirmação de pagamento"""
        try:
            # Buscar dados da proposta
            proposal = await self._get_proposal_data(proposal_id)
            if not proposal:
                raise ValueError("Proposta não encontrada")
            
            # Preparar dados do contrato
            contract_data = self._prepare_contract_data(proposal, client_data)
            
            # Gerar documento no Autentique
            autentique_response = await self._create_autentique_document(contract_data)
            
            if not autentique_response.get('success'):
                raise ValueError("Erro ao criar documento no Autentique")
            
            # Salvar contrato no banco
            contract_id = await self._save_contract_record(
                proposal_id, 
                autentique_response['document_id'],
                autentique_response['signing_url']
            )
            
            # Enviar por WhatsApp
            await self._send_contract_whatsapp(
                client_data['phone'], 
                client_data['name'],
                autentique_response['signing_url']
            )
            
            # Criar tarefas de implementação
            await self._create_implementation_tasks(contract_id, proposal['business_type'])
            
            return {
                "success": True,
                "contract_id": contract_id,
                "autentique_id": autentique_response['document_id'],
                "signing_url": autentique_response['signing_url'],
                "message": f"Contrato criado e enviado para {client_data['name']}"
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar contrato: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_proposal_data(self, proposal_id: str) -> Optional[Dict]:
        """Busca dados da proposta no Supabase"""
        try:
            result = self.supabase.table('proposals').select('*').eq('id', proposal_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar proposta: {str(e)}")
            return None
    
    def _prepare_contract_data(self, proposal: Dict, client_data: Dict) -> ContractData:
        """Prepara dados estruturados do contrato"""
        
        # Mapear descrições de serviço por tipo de negócio
        service_descriptions = {
            "saude": "Desenvolvimento e implementação de sistema de automação para área da saúde, incluindo agendamento automático, confirmação de consultas, prontuário digital e gestão administrativa.",
            "comercio": "Desenvolvimento e implementação de sistema de automação para comércio, incluindo atendimento via WhatsApp, catálogo digital, recuperação de carrinho abandonado e controle de estoque.",
            "servicos": "Desenvolvimento e implementação de sistema de automação para profissionais liberais, incluindo captação de leads, qualificação automática, agendamento e gestão de clientes.",
            "imobiliaria": "Desenvolvimento e implementação de sistema de automação para imobiliária, incluindo captação de leads, agendamento de visitas, contratos digitais e gestão de propriedades."
        }
        
        business_type = proposal['proposal_data']['business_type']
        
        return ContractData(
            client_name=client_data['name'],
            client_email=client_data.get('email', ''),
            client_phone=client_data['phone'],
            client_document=client_data.get('document', ''),
            business_type=business_type,
            service_description=service_descriptions.get(business_type, "Sistema de automação personalizado"),
            setup_fee=float(proposal['implementation_fee']),
            monthly_fee=float(proposal['monthly_fee']),
            contract_duration=12,
            implementation_deadline=(datetime.now() + timedelta(days=30)).strftime('%d/%m/%Y'),
            special_conditions=proposal['proposal_data'].get('special_conditions', []),
            payment_terms="Mensalidade cobrada via PIX até o dia 10 de cada mês"
        )
    
    async def _create_autentique_document(self, contract_data: ContractData) -> Dict[str, Any]:
        """Cria documento no Autentique"""
        try:
            # Carregar template HTML do contrato
            template_html = self._get_contract_template(contract_data.business_type)
            
            # Renderizar template com dados
            template = Template(template_html)
            contract_html = template.render(
                client_name=contract_data.client_name,
                client_email=contract_data.client_email,
                client_phone=contract_data.client_phone,
                client_document=contract_data.client_document,
                service_description=contract_data.service_description,
                setup_fee=f"R$ {contract_data.setup_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
                monthly_fee=f"R$ {contract_data.monthly_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
                contract_duration=contract_data.contract_duration,
                implementation_deadline=contract_data.implementation_deadline,
                payment_terms=contract_data.payment_terms,
                current_date=datetime.now().strftime('%d/%m/%Y'),
                contract_id=str(uuid.uuid4())[:8].upper()
            )
            
            # Dados para criação no Autentique
            document_data = {
                "document": {
                    "name": f"Contrato de Prestação de Serviços - {contract_data.client_name}",
                },
                "parties": [
                    {
                        "email": contract_data.client_email,
                        "name": contract_data.client_name,
                        "qualifier": "signer"
                    },
                    {
                        "email": "contrato@cranios.pro",
                        "name": "Crânios - Automações com IA",
                        "qualifier": "signer"
                    }
                ],
                "file": {
                    "name": f"contrato_{contract_data.client_name.replace(' ', '_').lower()}.html",
                    "content": contract_html
                }
            }
            
            # Fazer requisição para Autentique
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.autentique_base_url}/documents",
                    json=document_data,
                    headers={
                        "Authorization": f"Bearer {self.autentique_token}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    
                    if response.status == 201:
                        result = await response.json()
                        
                        return {
                            "success": True,
                            "document_id": result['data']['id'],
                            "signing_url": result['data']['signing_url'],
                            "document_url": result['data']['file']['url']
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro Autentique: {response.status} - {error_text}")
                        return {"success": False, "error": error_text}
        
        except Exception as e:
            logger.error(f"Erro ao criar documento Autentique: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _save_contract_record(self, proposal_id: str, autentique_id: str, signing_url: str) -> str:
        """Salva registro do contrato no Supabase"""
        try:
            contract_data = {
                "id": str(uuid.uuid4()),
                "proposal_id": proposal_id,
                "autentique_id": autentique_id,
                "contract_url": signing_url,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table('contracts').insert(contract_data).execute()
            
            if result.data:
                return result.data[0]['id']
            else:
                raise ValueError("Erro ao salvar contrato no banco")
                
        except Exception as e:
            logger.error(f"Erro ao salvar contrato: {str(e)}")
            raise
    
    async def _send_contract_whatsapp(self, phone: str, name: str, signing_url: str):
        """Envia contrato via WhatsApp"""
        try:
            message = f"""🎉 *Parabéns {name}!*

Seu contrato foi gerado automaticamente e está pronto para assinatura digital.

📋 *Para assinar:*
• Clique no link abaixo
• Confirme seus dados
• Assine digitalmente

🔗 *Link para assinatura:*
{signing_url}

⏰ *Importante:*
• Válido por 30 dias
• Após assinatura, iniciaremos a implementação
• Você receberá uma cópia por email

🚀 Em breve você terá sua automação funcionando!

Dúvidas? Responda esta mensagem."""

            payload = {
                "number": phone,
                "text": message
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.evolution_api_url}/message/sendText/Ana",
                    json=payload,
                    headers={
                        "apikey": self.evolution_api_key,
                        "Content-Type": "application/json"
                    }
                ) as response:
                    
                    if response.status == 200:
                        logger.info(f"Contrato enviado por WhatsApp para {phone}")
                    else:
                        logger.error(f"Erro ao enviar WhatsApp: {response.status}")
        
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {str(e)}")
    
    async def _create_implementation_tasks(self, contract_id: str, business_type: str):
        """Cria tarefas automáticas de implementação"""
        try:
            # Templates de tarefas por tipo de negócio
            task_templates = {
                "saude": [
                    {"title": "Configurar agendamento automático", "days": 3, "priority": "alta"},
                    {"title": "Implementar confirmação de consultas", "days": 5, "priority": "alta"},
                    {"title": "Configurar prontuário digital", "days": 10, "priority": "media"},
                    {"title": "Treinar equipe", "days": 15, "priority": "media"},
                    {"title": "Teste final e entrega", "days": 20, "priority": "alta"}
                ],
                "comercio": [
                    {"title": "Configurar catálogo digital", "days": 3, "priority": "alta"},
                    {"title": "Implementar carrinho de compras", "days": 7, "priority": "alta"},
                    {"title": "Configurar recuperação de carrinho", "days": 10, "priority": "media"},
                    {"title": "Integrar controle de estoque", "days": 15, "priority": "media"},
                    {"title": "Teste final e entrega", "days": 20, "priority": "alta"}
                ],
                "servicos": [
                    {"title": "Configurar captação de leads", "days": 3, "priority": "alta"},
                    {"title": "Implementar qualificação automática", "days": 7, "priority": "alta"},
                    {"title": "Configurar agendamento", "days": 10, "priority": "media"},
                    {"title": "Implementar CRM", "days": 15, "priority": "media"},
                    {"title": "Teste final e entrega", "days": 20, "priority": "alta"}
                ]
            }
            
            tasks = task_templates.get(business_type, task_templates["servicos"])
            
            for task in tasks:
                task_data = {
                    "id": str(uuid.uuid4()),
                    "title": task["title"],
                    "description": f"Implementação para cliente - Contrato {contract_id[:8]}",
                    "assigned_to": "implementacao",
                    "client_id": contract_id,
                    "task_type": "implementation",
                    "priority": task["priority"],
                    "status": "pending",
                    "due_date": (datetime.now() + timedelta(days=task["days"])).isoformat(),
                    "created_at": datetime.now().isoformat()
                }
                
                self.supabase.table('tasks').insert(task_data).execute()
            
            logger.info(f"Tarefas de implementação criadas para contrato {contract_id}")
            
        except Exception as e:
            logger.error(f"Erro ao criar tarefas: {str(e)}")
    
    def _get_contract_template(self, business_type: str) -> str:
        """Retorna template HTML do contrato"""
        
        base_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Contrato de Prestação de Serviços</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                .header { text-align: center; margin-bottom: 30px; }
                .section { margin-bottom: 20px; }
                .highlight { background-color: #f0f0f0; padding: 10px; border-left: 4px solid #007acc; }
                .signature { margin-top: 50px; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>CONTRATO DE PRESTAÇÃO DE SERVIÇOS</h1>
                <h2>Automação com Inteligência Artificial</h2>
                <p><strong>Contrato Nº:</strong> {{ contract_id }}</p>
                <p><strong>Data:</strong> {{ current_date }}</p>
            </div>

            <div class="section">
                <h3>1. PARTES CONTRATANTES</h3>
                <p><strong>CONTRATADA:</strong> Crânios - Soluções em Automação e IA<br>
                CNPJ: 00.000.000/0001-00<br>
                Endereço: Aracaju, SE<br>
                E-mail: contrato@cranios.pro</p>

                <p><strong>CONTRATANTE:</strong> {{ client_name }}<br>
                {% if client_document %}CPF/CNPJ: {{ client_document }}<br>{% endif %}
                Telefone: {{ client_phone }}<br>
                E-mail: {{ client_email }}</p>
            </div>

            <div class="section">
                <h3>2. OBJETO DO CONTRATO</h3>
                <p>{{ service_description }}</p>
            </div>

            <div class="section">
                <h3>3. VALORES E FORMA DE PAGAMENTO</h3>
                <table>
                    <tr>
                        <th>Descrição</th>
                        <th>Valor</th>
                    </tr>
                    <tr>
                        <td>Taxa de Implementação (única)</td>
                        <td>{{ setup_fee }}</td>
                    </tr>
                    <tr>
                        <td>Mensalidade</td>
                        <td>{{ monthly_fee }}</td>
                    </tr>
                </table>
                <div class="highlight">
                    <strong>Forma de Pagamento:</strong> {{ payment_terms }}
                </div>
            </div>

            <div class="section">
                <h3>4. PRAZO</h3>
                <p>• <strong>Implementação:</strong> até {{ implementation_deadline }}</p>
                <p>• <strong>Vigência:</strong> {{ contract_duration }} meses, renovável automaticamente</p>
            </div>

            <div class="section">
                <h3>5. RESPONSABILIDADES</h3>
                <h4>5.1 DA CONTRATADA:</h4>
                <ul>
                    <li>Desenvolver e implementar sistema de automação conforme especificado</li>
                    <li>Fornecer suporte técnico durante a vigência</li>
                    <li>Garantir funcionamento adequado das automações</li>
                    <li>Treinar equipe do contratante quando necessário</li>
                </ul>

                <h4>5.2 DO CONTRATANTE:</h4>
                <ul>
                    <li>Fornecer informações necessárias para implementação</li>
                    <li>Efetuar pagamentos nas datas acordadas</li>
                    <li>Colaborar durante processo de implementação</li>
                    <li>Comunicar problemas técnicos prontamente</li>
                </ul>
            </div>

            <div class="section">
                <h3>6. GARANTIAS</h3>
                <ul>
                    <li>Funcionalidade: 30 dias após implementação</li>
                    <li>Suporte técnico incluído na mensalidade</li>
                    <li>Atualizações de sistema sem custo adicional</li>
                </ul>
            </div>

            <div class="section">
                <h3>7. RESCISÃO</h3>
                <p>Este contrato pode ser rescindido por qualquer das partes mediante aviso prévio de 30 dias. 
                Em caso de inadimplência, o contrato pode ser rescindido imediatamente.</p>
            </div>

            <div class="signature">
                <p>Aracaju, {{ current_date }}</p>
                
                <br><br>
                <hr style="width: 300px; margin-left: 0;">
                <p><strong>Crânios - Automações com IA</strong><br>
                Contratada</p>

                <br><br>
                <hr style="width: 300px; margin-left: 0;">
                <p><strong>{{ client_name }}</strong><br>
                Contratante</p>
            </div>
        </body>
        </html>
        """
        
        return base_template
    
    def _load_contract_templates(self) -> Dict[str, str]:
        """Carrega templates específicos por tipo de negócio"""
        return {
            "saude": self._get_contract_template("saude"),
            "comercio": self._get_contract_template("comercio"), 
            "servicos": self._get_contract_template("servicos"),
            "imobiliaria": self._get_contract_template("imobiliaria")
        }
    
    async def check_contract_status(self, contract_id: str) -> Dict[str, Any]:
        """Verifica status de assinatura no Autentique"""
        try:
            # Buscar contrato no banco
            result = self.supabase.table('contracts').select('*').eq('id', contract_id).execute()
            
            if not result.data:
                return {"success": False, "error": "Contrato não encontrado"}
            
            contract = result.data[0]
            autentique_id = contract['autentique_id']
            
            # Consultar status no Autentique
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.autentique_base_url}/documents/{autentique_id}",
                    headers={"Authorization": f"Bearer {self.autentique_token}"}
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        status = data['data']['status']
                        
                        # Atualizar status no banco se mudou
                        if status != contract['status']:
                            self.supabase.table('contracts').update({
                                'status': status,
                                'signed_at': datetime.now().isoformat() if status == 'signed' else None
                            }).eq('id', contract_id).execute()
                        
                        return {
                            "success": True,
                            "status": status,
                            "signed": status == 'signed'
                        }
                    else:
                        return {"success": False, "error": "Erro ao consultar Autentique"}
            
        except Exception as e:
            logger.error(f"Erro ao verificar status: {str(e)}")
            return {"success": False, "error": str(e)}

# Webhook para receber notificações do Autentique
async def handle_autentique_webhook(request_data: Dict) -> Dict[str, Any]:
    """Processa webhooks do Autentique quando contrato é assinado"""
    try:
        document_id = request_data.get('document_id')
        status = request_data.get('status')
        
        if status == 'signed':
            # Buscar contrato no banco
            supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))
            result = supabase.table('contracts').select('*').eq('autentique_id', document_id).execute()
            
            if result.data:
                contract = result.data[0]
                
                # Atualizar status
                supabase.table('contracts').update({
                    'status': 'signed',
                    'signed_at': datetime.now().isoformat()
                }).eq('id', contract['id']).execute()
                
                # Notificar por WhatsApp
                await _notify_contract_signed(contract)
                
                return {"success": True, "message": "Contrato assinado processado"}
        
        return {"success": True, "message": "Webhook processado"}
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}")
        return {"success": False, "error": str(e)}

async def _notify_contract_signed(contract: Dict):
    """Notifica assinatura do contrato"""
    try:
        # Buscar dados do cliente
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))
        proposal_result = supabase.table('proposals').select('*').eq('id', contract['proposal_id']).execute()
        
        if proposal_result.data:
            proposal = proposal_result.data[0]
            lead_result = supabase.table('leads').select('*').eq('id', proposal['lead_id']).execute()
            
            if lead_result.data:
                lead = lead_result.data[0]
                
                message = f"""🎉 *Contrato Assinado com Sucesso!*

Olá {lead['name']}!

Seu contrato foi assinado digitalmente e está tudo pronto para iniciarmos a implementação.

📋 *Próximos passos:*
• Nossa equipe entrará em contato em até 24h
• Agendaremos reunião de kickoff
• Início da implementação: imediato

🚀 *Cronograma de Implementação:*
• Semana 1-2: Configuração inicial
• Semana 2-3: Desenvolvimento das automações
• Semana 3-4: Testes e treinamento
• Semana 4: Entrega final

Estamos muito animados para trabalhar com vocês!

Dúvidas? Responda esta mensagem."""

                # Enviar WhatsApp
                payload = {
                    "number": lead['phone'],
                    "text": message
                }
                
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/Ana",
                        json=payload,
                        headers={
                            "apikey": os.getenv('EVOLUTION_API_KEY'),
                            "Content-Type": "application/json"
                        }
                    )
                
    except Exception as e:
        logger.error(f"Erro ao notificar assinatura: {str(e)}")

# Exemplo de uso
if __name__ == "__main__":
    import asyncio
    
    async def test_contract_creation():
        manager = ContractManager()
        
        # Dados de teste
        proposal_id = "test-proposal-id"
        client_data = {
            "name": "João Silva",
            "email": "joao@email.com",
            "phone": "5511999999999",
            "document": "123.456.789-00"
        }
        
        result = await manager.create_contract_from_proposal(proposal_id, client_data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # asyncio.run(test_contract_creation())
