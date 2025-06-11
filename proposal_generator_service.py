"""
Proposal Generator Service - Crânios
Gerador automático de propostas personalizadas
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import logging
from supabase import create_client, Client
from jinja2 import Template
import pdfkit
from dataclasses import dataclass
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PricingRule:
    business_type: str
    company_size: str
    setup_fee: float
    monthly_fee: float
    implementation_days: int
    features: List[str]
    roi_percentage: int
    payback_months: int

@dataclass
class ProposalData:
    lead_id: str
    client_name: str
    business_type: str
    company_size: str
    main_challenge: str
    setup_fee: float
    monthly_fee: float
    total_first_year: float
    implementation_days: int
    features: List[str]
    roi_data: Dict
    case_studies: List[Dict]
    payment_link: str

class ProposalGenerator:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

        # Configurações
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        self.evolution_api_url = os.getenv('EVOLUTION_API_URL')
        self.evolution_api_key = os.getenv('EVOLUTION_API_KEY')
        
        # Inicializar clientes
             
        # Carregar regras de pricing
        self.pricing_rules = self._load_pricing_rules()
        
        # Templates
        self.proposal_template = self._load_proposal_template()
        self.whatsapp_template = self._load_whatsapp_template()
    
    def _load_pricing_rules(self) -> List[PricingRule]:
        """Carrega regras de precificação por segmento"""
        return [
            # Área da Saúde
            PricingRule(
                business_type="saude",
                company_size="sozinho",
                setup_fee=1997.00,
                monthly_fee=297.00,
                implementation_days=7,
                features=[
                    "Agendamento automático via WhatsApp",
                    "Confirmação de consultas 24h antes",
                    "Histórico digital do paciente",
                    "Receituário digital",
                    "Controle financeiro básico",
                    "Dashboard de métricas"
                ],
                roi_percentage=280,
                payback_months=3
            ),
            PricingRule(
                business_type="saude",
                company_size="pequena",
                setup_fee=2997.00,
                monthly_fee=497.00,
                implementation_days=10,
                features=[
                    "Agendamento automático multi-profissional",
                    "Confirmação e lembretes automatizados",
                    "Prontuário eletrônico completo",
                    "Receituário e atestados digitais",
                    "Controle de estoque medicamentos",
                    "Faturamento automático convênios",
                    "Relatórios gerenciais",
                    "App mobile personalizado"
                ],
                roi_percentage=320,
                payback_months=4
            ),
            
            # Comércio
            PricingRule(
                business_type="comercio",
                company_size="sozinho",
                setup_fee=1497.00,
                monthly_fee=247.00,
                implementation_days=5,
                features=[
                    "Atendimento WhatsApp 24/7",
                    "Catálogo digital automatizado",
                    "Recuperação carrinho abandonado",
                    "Follow-up pós-venda",
                    "Controle básico de estoque",
                    "Relatório de vendas"
                ],
                roi_percentage=240,
                payback_months=2
            ),
            PricingRule(
                business_type="comercio",
                company_size="pequena",
                setup_fee=2497.00,
                monthly_fee=397.00,
                implementation_days=8,
                features=[
                    "E-commerce completo automatizado",
                    "Atendimento multi-canal 24/7",
                    "Sistema de fidelidade automático",
                    "Promoções personalizadas",
                    "Controle completo de estoque",
                    "Integração com marketplaces",
                    "Relatórios avançados",
                    "App de vendas"
                ],
                roi_percentage=280,
                payback_months=3
            ),
            
            # Profissionais Liberais
            PricingRule(
                business_type="servicos",
                company_size="sozinho",
                setup_fee=1797.00,
                monthly_fee=297.00,
                implementation_days=6,
                features=[
                    "Captação automática de leads",
                    "Qualificação inteligente",
                    "Agendamento automático",
                    "Follow-up personalizado",
                    "Contratos digitais",
                    "Cobrança automatizada"
                ],
                roi_percentage=300,
                payback_months=3
            ),
            PricingRule(
                business_type="servicos",
                company_size="pequena",
                setup_fee=2797.00,
                monthly_fee=447.00,
                implementation_days=10,
                features=[
                    "Sistema completo de CRM",
                    "Captação multi-canal",
                    "Pipeline de vendas automatizado",
                    "Contratos e assinaturas digitais",
                    "Gestão financeira completa",
                    "Relatórios de performance",
                    "App mobile personalizado",
                    "Integração com ferramentas existentes"
                ],
                roi_percentage=350,
                payback_months=4
            ),
            
            # Imobiliárias
            PricingRule(
                business_type="imobiliaria",
                company_size="sozinho",
                setup_fee=2297.00,
                monthly_fee=397.00,
                implementation_days=8,
                features=[
                    "Captação automática de leads",
                    "Qualificação por perfil de imóvel",
                    "Agendamento de visitas",
                    "Follow-up pós-visita",
                    "Contratos automatizados",
                    "Portal do cliente"
                ],
                roi_percentage=280,
                payback_months=3
            ),
            PricingRule(
                business_type="imobiliaria",
                company_size="pequena",
                setup_fee=3497.00,
                monthly_fee=597.00,
                implementation_days=12,
                features=[
                    "Sistema completo de gestão imobiliária",
                    "Site com busca inteligente",
                    "App mobile para corretores",
                    "Automação completa de processos",
                    "Integração com portais",
                    "Dashboard de performance",
                    "Sistema de comissões",
                    "Relatórios gerenciais avançados"
                ],
                roi_percentage=320,
                payback_months=4
            )
        ]
    
    async def generate_proposal(self, lead_data: Dict) -> Dict[str, Any]:
        """Gera proposta personalizada para o lead"""
        try:
            # Buscar regra de pricing apropriada
            pricing_rule = self._get_pricing_rule(
                lead_data['business_type'], 
                lead_data['company_size']
            )
            
            if not pricing_rule:
                raise ValueError("Regra de pricing não encontrada")
            
            # Buscar cases específicos
            case_studies = self._get_case_studies(lead_data['business_type'])
            
            # Calcular ROI específico
            roi_data = self._calculate_roi(pricing_rule, lead_data)
            
            # Gerar link de pagamento Stripe
            payment_link = await self._create_stripe_payment_link(pricing_rule, lead_data)
            
            # Criar dados da proposta
            proposal_data = ProposalData(
                lead_id=lead_data.get('id', str(uuid.uuid4())),
                client_name=lead_data['name'],
                business_type=lead_data['business_type'],
                company_size=lead_data['company_size'],
                main_challenge=lead_data['main_challenge'],
                setup_fee=pricing_rule.setup_fee,
                monthly_fee=pricing_rule.monthly_fee,
                total_first_year=pricing_rule.setup_fee + (pricing_rule.monthly_fee * 12),
                implementation_days=pricing_rule.implementation_days,
                features=pricing_rule.features,
                roi_data=roi_data,
                case_studies=case_studies,
                payment_link=payment_link
            )
            
            # Gerar PDF da proposta
            pdf_content = self._generate_pdf_proposal(proposal_data)
            
            # Salvar proposta no banco
            proposal_id = await self._save_proposal(proposal_data, pdf_content)
            
            # Enviar por WhatsApp
            await self._send_proposal_whatsapp(lead_data['phone'], proposal_data)
            
            # Agendar follow-ups
            await self._schedule_follow_ups(proposal_id, lead_data['phone'])
            
            return {
                "success": True,
                "proposal_id": proposal_id,
                "payment_link": payment_link,
                "total_value": proposal_data.total_first_year,
                "message": f"Proposta enviada para {lead_data['name']}"
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar proposta: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_pricing_rule(self, business_type: str, company_size: str) -> Optional[PricingRule]:
        """Busca regra de pricing apropriada"""
        # Normalizar inputs
        business_type = business_type.lower()
        
        # Mapear tamanhos
        size_mapping = {
            "sozinho": "sozinho",
            "trabalho sozinho": "sozinho",
            "2-5 funcionários": "pequena",
            "pequena": "pequena",
            "6-15 funcionários": "media",
            "media": "media",
            "mais de 15": "grande",
            "grande": "grande"
        }
        
        mapped_size = size_mapping.get(company_size.lower(), "sozinho")
        
        # Buscar regra exata
        for rule in self.pricing_rules:
            if rule.business_type == business_type and rule.company_size == mapped_size:
                return rule
        
        # Fallback para tamanho "sozinho" se não encontrar
        for rule in self.pricing_rules:
            if rule.business_type == business_type and rule.company_size == "sozinho":
                return rule
        
        return None
    
    def _get_case_studies(self, business_type: str) -> List[Dict]:
        """Retorna cases de sucesso específicos"""
        cases = {
            "saude": [
                {
                    "client": "Dr. Ricardo Silva - Clínica Médica",
                    "challenge": "40% dos pacientes não compareciam às consultas",
                    "solution": "Sistema de confirmação automática + lembretes",
                    "result": "Redução de 65% no no-show, aumento de 35% na receita"
                },
                {
                    "client": "Dra. Ana Paula - Odontologia",
                    "challenge": "Muito tempo perdido com tarefas administrativas",
                    "solution": "Automação completa do atendimento e agendamento",
                    "result": "60% menos tempo administrativo, 40% mais consultas/dia"
                }
            ],
            "comercio": [
                {
                    "client": "Pet Shop Amigo Fiel",
                    "challenge": "Muitos clientes abandonavam carrinho online",
                    "solution": "Recuperação automática + atendimento personalizado",
                    "result": "35% aumento nas vendas, 50% recuperação carrinho abandonado"
                },
                {
                    "client": "Restaurante Sabor & Arte",
                    "challenge": "Pedidos perdidos por demora no atendimento",
                    "solution": "Cardápio digital + pedidos automatizados",
                    "result": "80% redução em pedidos perdidos, 25% aumento no ticket médio"
                }
            ],
            "servicos": [
                {
                    "client": "Advogado Dr. Marcos Costa",
                    "challenge": "Dificuldade para captar novos clientes",
                    "solution": "Sistema de captação + qualificação automática",
                    "result": "300% aumento em leads qualificados, 150% crescimento no faturamento"
                }
            ],
            "imobiliaria": [
                {
                    "client": "Imobiliária Lar Doce Lar",
                    "challenge": "Muitas visitas desmarcadas em cima da hora",
                    "solution": "Confirmação automática + remarketing para interessados",
                    "result": "70% redução em visitas desmarcadas, 45% aumento em fechamentos"
                }
            ]
        }
        
        return cases.get(business_type.lower(), [])
    
    def _calculate_roi(self, pricing_rule: PricingRule, lead_data: Dict) -> Dict:
        """Calcula ROI específico baseado no perfil do cliente"""
        
        # Estimativas de receita por segmento e tamanho
        revenue_estimates = {
            "saude": {
                "sozinho": 15000,
                "pequena": 35000,
                "media": 80000
            },
            "comercio": {
                "sozinho": 12000,
                "pequena": 28000,
                "media": 65000
            },
            "servicos": {
                "sozinho": 18000,
                "pequena": 42000,
                "media": 95000
            },
            "imobiliaria": {
                "sozinho": 20000,
                "pequena": 50000,
                "media": 120000
            }
        }
        
        size_mapping = {
            "sozinho": "sozinho",
            "2-5 funcionários": "pequena",
            "6-15 funcionários": "media"
        }
        
        mapped_size = size_mapping.get(lead_data.get('company_size', ''), "sozinho")
        base_revenue = revenue_estimates.get(lead_data['business_type'], {}).get(mapped_size, 15000)
        
        # Calcular impacto da automação
        monthly_increase = base_revenue * (pricing_rule.roi_percentage / 100) / 12
        total_investment = pricing_rule.setup_fee + (pricing_rule.monthly_fee * 12)
        
        return {
            "current_monthly_revenue": base_revenue,
            "projected_increase_monthly": monthly_increase,
            "projected_increase_percentage": pricing_rule.roi_percentage,
            "total_investment_year": total_investment,
            "net_profit_year": (monthly_increase * 12) - total_investment,
            "payback_months": pricing_rule.payback_months,
            "roi_percentage": int(((monthly_increase * 12) / total_investment) * 100)
        }
    
    async def _create_stripe_payment_link(self, pricing_rule: PricingRule, lead_data: Dict) -> str:
        """Cria link de pagamento no Stripe"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.stripe_api_key}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                # Criar produto
                product_data = {
                    'name': f'Automação Crânios - {lead_data["business_type"].title()}',
                    'description': f'Setup + 12 meses de automação para {lead_data["name"]}'
                }
                
                async with session.post('https://api.stripe.com/v1/products', 
                                      headers=headers, data=product_data) as response:
                    product = await response.json()
                    product_id = product['id']
                
                # Criar preço
                price_data = {
                    'unit_amount': int(pricing_rule.setup_fee * 100),  # Stripe usa centavos
                    'currency': 'brl',
                    'product': product_id
                }
                
                async with session.post('https://api.stripe.com/v1/prices', 
                                      headers=headers, data=price_data) as response:
                    price = await response.json()
                    price_id = price['id']
                
                # Criar payment link
                payment_link_data = {
                    'line_items[0][price]': price_id,
                    'line_items[0][quantity]': '1',
                    'metadata[client_name]': lead_data['name'],
                    'metadata[client_phone]': lead_data['phone'],
                    'metadata[business_type]': lead_data['business_type']
                }
                
                async with session.post('https://api.stripe.com/v1/payment_links', 
                                      headers=headers, data=payment_link_data) as response:
                    payment_link = await response.json()
                    return payment_link['url']
                    
        except Exception as e:
            logger.error(f"Erro ao criar link Stripe: {str(e)}")
            return "https://pay.stripe.com/exemplo"  # Fallback
    
    def _generate_pdf_proposal(self, proposal_data: ProposalData) -> bytes:
        """Gera PDF da proposta"""
        html_content = self.proposal_template.render(
            client_name=proposal_data.client_name,
            business_type=proposal_data.business_type.title(),
            setup_fee=f"R$ {proposal_data.setup_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
            monthly_fee=f"R$ {proposal_data.monthly_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
            total_first_year=f"R$ {proposal_data.total_first_year:,.2f}".replace(',', '.').replace('.', ',', 1),
            implementation_days=proposal_data.implementation_days,
            features=proposal_data.features,
            roi_data=proposal_data.roi_data,
            case_studies=proposal_data.case_studies,
            payment_link=proposal_data.payment_link,
            date=datetime.now().strftime("%d/%m/%Y")
        )
        
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None
        }
        
        try:
            pdf_content = pdfkit.from_string(html_content, False, options=options)
            return pdf_content
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {str(e)}")
            return b""  # Retorna bytes vazio em caso de erro
    
    async def _save_proposal(self, proposal_data: ProposalData, pdf_content: bytes) -> str:
        """Salva proposta no Supabase"""
        try:
            proposal_record = {
                'lead_id': proposal_data.lead_id,
                'proposal_data': {
                    'client_name': proposal_data.client_name,
                    'business_type': proposal_data.business_type,
                    'features': proposal_data.features,
                    'roi_data': proposal_data.roi_data,
                    'case_studies': proposal_data.case_studies
                },
                'setup_fee': proposal_data.setup_fee,
                'monthly_fee': proposal_data.monthly_fee,
                'total_value': proposal_data.total_first_year,
                'payment_link': proposal_data.payment_link,
                'status': 'sent',
                'sent_at': datetime.now().isoformat(),
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('proposals').insert(proposal_record).execute()
            
            # Upload PDF para storage (se necessário)
            if pdf_content:
                filename = f"proposta_{proposal_data.lead_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                self.supabase.storage.from_('proposals').upload(filename, pdf_content)
            
            return result.data[0]['id']
            
        except Exception as e:
            logger.error(f"Erro ao salvar proposta: {str(e)}")
            return ""
    
    async def _send_proposal_whatsapp(self, phone: str, proposal_data: ProposalData):
        """Envia proposta via WhatsApp"""
        try:
            message = self.whatsapp_template.render(
                client_name=proposal_data.client_name,
                setup_fee=f"R$ {proposal_data.setup_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
                monthly_fee=f"R$ {proposal_data.monthly_fee:,.2f}".replace(',', '.').replace('.', ',', 1),
                payment_link=proposal_data.payment_link,
                roi_percentage=proposal_data.roi_data['roi_percentage'],
                payback_months=proposal_data.roi_data['payback_months']
            )
            
            payload = {
                'number': phone,
                'textMessage': {
                    'text': message
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'apikey': self.evolution_api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.evolution_api_url}/message/sendText/cranios-instance",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        logger.info(f"Proposta enviada via WhatsApp para {phone}")
                    else:
                        logger.error(f"Erro ao enviar WhatsApp: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erro ao enviar proposta via WhatsApp: {str(e)}")
    
    async def _schedule_follow_ups(self, proposal_id: str, phone: str):
        """Agenda follow-ups automáticos"""
        follow_up_schedule = [
            {"days": 1, "message": "follow_up_1_day"},
            {"days": 3, "message": "follow_up_3_days"},
            {"days": 7, "message": "follow_up_1_week"},
            {"days": 14, "message": "follow_up_2_weeks"}
        ]
        
        # Aqui você integraria com N8N para agendar os follow-ups
        # Por enquanto, apenas logamos
        for follow_up in follow_up_schedule:
            logger.info(f"Follow-up agendado para {follow_up['days']} dias - {phone}")
    
    def _load_proposal_template(self) -> Template:
        """Carrega template HTML da proposta"""
        template_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Proposta Crânios - {{ client_name }}</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
                .content { padding: 30px; }
                .section { margin-bottom: 30px; }
                .features li { margin-bottom: 8px; }
                .roi-box { background: #f8f9fa; padding: 20px; border-left: 4px solid #667eea; margin: 20px 0; }
                .case-study { background: #f1f3f4; padding: 15px; margin: 10px 0; border-radius: 8px; }
                .payment-cta { background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 8px; margin: 30px 0; }
                .payment-cta a { color: white; text-decoration: none; font-size: 18px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧠 CRÂNIOS</h1>
                <h2>Proposta de Automação Inteligente</h2>
                <p>{{ client_name }} - {{ business_type }}</p>
                <p>{{ date }}</p>
            </div>
            
            <div class="content">
                <div class="section">
                    <h2>📊 Resumo do Investimento</h2>
                    <ul>
                        <li><strong>Setup Inicial:</strong> {{ setup_fee }}</li>
                        <li><strong>Mensalidade:</strong> {{ monthly_fee }}</li>
                        <li><strong>Total 1º Ano:</strong> {{ total_first_year }}</li>
                        <li><strong>Implementação:</strong> {{ implementation_days }} dias úteis</li>
                    </ul>
                </div>
                
                <div class="roi-box">
                    <h3>💰 Retorno do Investimento</h3>
                    <p><strong>ROI Projetado:</strong> {{ roi_data.roi_percentage }}% ao ano</p>
                    <p><strong>Payback:</strong> {{ roi_data.payback_months }} meses</p>
                    <p><strong>Lucro Líquido Ano 1:</strong> R$ {{ "{:,.2f}".format(roi_data.net_profit_year).replace(',', '.').replace('.', ',', 1) }}</p>
                </div>
                
                <div class="section">
                    <h2>🚀 Funcionalidades Incluídas</h2>
                    <ul class="features">
                    {% for feature in features %}
                        <li>{{ feature }}</li>
                    {% endfor %}
                    </ul>
                </div>
                
                <div class="section">
                    <h2>📈 Cases de Sucesso</h2>
                    {% for case in case_studies %}
                    <div class="case-study">
                        <h4>{{ case.client }}</h4>
                        <p><strong>Desafio:</strong> {{ case.challenge }}</p>
                        <p><strong>Solução:</strong> {{ case.solution }}</p>
                        <p><strong>Resultado:</strong> {{ case.result }}</p>
                    </div>
                    {% endfor %}
                </div>
                
                <div class="payment-cta">
                    <p>🎯 <strong>OFERTA LIMITADA - 20 VAGAS POR MÊS</strong></p>
                    <a href="{{ payment_link }}" target="_blank">COMEÇAR AGORA - CLIQUE AQUI</a>
                    <p style="font-size: 14px; margin-top: 10px;">Pagamento seguro via Stripe • Garantia de 30 dias</p>
                </div>
            </div>
        </body>
        </html>
        """
        return Template(template_html)
    
    def _load_whatsapp_template(self) -> Template:
        """Carrega template da mensagem do WhatsApp"""
        template_text = """
🧠 *CRÂNIOS - SUA PROPOSTA ESTÁ PRONTA!*

Olá {{ client_name }}! 

Preparei uma proposta *sob medida* para automatizar seu negócio:

💰 *INVESTIMENTO:*
• Setup: {{ setup_fee }}
• Mensalidade: {{ monthly_fee }}

📈 *SEU RETORNO:*
• ROI: {{ roi_percentage }}% ao ano
• Payback: {{ payback_months }} meses
• Praticamente se paga sozinho!

🎯 *ATENÇÃO:* Temos apenas *20 vagas por mês* para garantir implementação de qualidade.

👆 *CLIQUE AQUI PARA COMEÇAR:*
{{ payment_link }}

Alguma dúvida? Estou aqui para te ajudar! 😊

_Ana - Assistente Virtual Crânios_
        """
        return Template(template_text)

# Função principal para usar com webhooks N8N
async def generate_proposal_webhook(lead_data: Dict) -> Dict:
    """Função principal para gerar proposta via webhook"""
    generator = ProposalGenerator()
    return await generator.generate_proposal(lead_data)

if __name__ == "__main__":
    # Teste local
    import asyncio
    
    async def test():
        generator = ProposalGenerator()
        
        test_lead = {
            'id': 'test-123',
            'name': 'Dr. João Silva',
            'phone': '5579999999999',
            'business_type': 'saude',
            'company_size': 'sozinho',
            'main_challenge': 'Muitos no-shows'
        }
        
        result = await generator.generate_proposal(test_lead)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test())
