"""
AI Processor Service - Crânios
Processador Principal de IA para o Sistema de Automação
Integração com Arcee.ai, Supabase e processamento de mídia
"""

import os
import json
import logging
import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import aiohttp
import openai
from supabase import Client
import speech_recognition as sr
import pyttsx3
from PIL import Image
import cv2
import numpy as np
from io import BytesIO
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AIRequest:
    """Estrutura de requisição para IA"""
    message: str
    context: Dict = None
    business_type: str = ""
    lead_data: Dict = None
    media_type: str = "text"  # text, audio, image, video
    media_data: bytes = None
    conversation_history: List[Dict] = None

@dataclass
class AIResponse:
    """Estrutura de resposta da IA"""
    text_response: str
    audio_response: bytes = None
    confidence_score: float = 0.0
    intent: str = ""
    entities: Dict = None
    next_action: str = ""
    requires_human: bool = False

class AIProcessor:
    """Processador Principal de IA"""
    
    def __init__(self, arcee_api_key: str, supabase_client: Client):
        self.arcee_api_key = arcee_api_key
        self.supabase = supabase_client
        self.setup_ai_services()
        self.load_training_data()
        
    def setup_ai_services(self):
        """Configuração dos serviços de IA"""
        try:
            # Configuração Arcee.ai
            self.arcee_base_url = "https://api.arcee.ai/v1"
            self.arcee_headers = {
                "Authorization": f"Bearer {self.arcee_api_key}",
                "Content-Type": "application/json"
            }
            
            # Configuração Speech Recognition
            self.speech_recognizer = sr.Recognizer()
            
            # Configuração Text-to-Speech
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            
            # Configuração de vozes (se disponível)
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Procura por voz feminina em português
                for voice in voices:
                    if 'portuguese' in voice.name.lower() or 'brasil' in voice.name.lower():
                        if 'female' in voice.name.lower() or 'ana' in voice.name.lower():
                            self.tts_engine.setProperty('voice', voice.id)
                            break
            
            logger.info("Serviços de IA configurados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro na configuração dos serviços de IA: {e}")
            raise
    
    def load_training_data(self):
        """Carrega dados de treinamento da IA"""
        try:
            # Carrega script da Agente Ana 2.0
            self.ana_script = self.load_ana_script()
            
            # Carrega base de conhecimento por segmento
            self.knowledge_base = self.load_knowledge_base()
            
            # Carrega técnicas de persuasão
            self.persuasion_techniques = self.load_persuasion_techniques()
            
            logger.info("Dados de treinamento carregados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados de treinamento: {e}")
            raise
    
    def load_ana_script(self) -> Dict:
        """Carrega o script completo da Agente Ana 2.0"""
        return {
            "personality": {
                "name": "Ana",
                "role": "Assistente Virtual da Crânios",
                "tone": "Profissional, empática, persuasiva",
                "objective": "Fechar vendas ou agendar apresentações"
            },
            "opening_messages": {
                "initial": "Olá! Sou a Ana, assistente virtual da Crânios 🤖🧠\nA nossa missão é uma só: fazer você ganhar tempo e dinheiro, sem perder sua sanidade.\n\nPosso começar te perguntando: como nos conheceu?",
                "livia_team": "Que legal! A Lívia Team sempre fala muito bem dos profissionais do clube. Vocês são pessoas que valorizam qualidade de vida e eficiência, né?\n\nAjudo empresários e profissionais como você a automatizar processos e ganhar MUITO mais tempo para o que realmente importa - seja para a família, exercícios, ou focar no que ama fazer no trabalho.",
                "referral": "Excelente! Quem te indicou? [aguarda resposta]\n\nAh, o [Nome]! Ele está economizando mais de 20 horas por semana desde que implementamos a automação. Disse que foi uma das melhores decisões que já tomou para o negócio dele.\n\nPosso te mostrar como conseguimos esses resultados?",
                "social_media": "Ótimo! Você deve ter visto alguns dos nossos cases de sucesso, né?\n\nNossos clientes estão economizando entre 15-25 horas semanais e aumentando faturamento em 30-80% com nossas automações.\n\nQuer saber como isso funciona na prática?"
            },
            "business_presentations": {
                "saude": {
                    "title": "VitaFlow: Seu Agente Complementar no Cuidado",
                    "presentation": "Incrível! Trabalho com vários médicos e dentistas que transformaram completamente suas práticas.\n\nO VitaFlow não é só um sistema - é seu agente complementar no cuidado. Enquanto você foca no que ama (cuidar dos pacientes), ele cuida de tudo mais:\n\n• 5 atendentes virtuais trabalhando 24/7\n• Economia de 20-30 horas semanais\n• Economia de R$ 8.000-15.000/mês\n• +40% em agendamentos\n\nCase Real: Dr. [Nome] tinha 60% da agenda vazia. Hoje tem lista de espera e faturou 85% mais no último trimestre.",
                    "data": "Segundo pesquisa da SBIS (Sociedade Brasileira de Informática em Saúde):\n- 73% dos médicos gastam +15h/semana com tarefas administrativas\n- 68% perdem pacientes por demora no retorno\n- Clínicas com automação têm 45% mais eficiência operacional"
                },
                "comercio": {
                    "title": "Crânios Business: Seu Vendedor Incansável",
                    "presentation": "Fantástico! Nossos clientes do comércio estão tendo resultados impressionantes.\n\nImagina ter 5 vendedores trabalhando 24/7 sem salário, sem férias, sem reclamação:\n\n• Vendas automáticas\n• WhatsApp Business automatizado\n• Marketing personalizado\n• Controle total\n\nCase Real: Pet Shop [Nome] aumentou vendas em 180% em 6 meses. Antes vendia R$ 25K/mês, hoje vende R$ 70K/mês.",
                    "data": "Pesquisa do Sebrae 2024:\n- 67% dos pequenos negócios perdem vendas por atendimento lento\n- Empresas com automação vendem 65% mais\n- 89% dos consumidores preferem resposta imediata"
                },
                "servicos": {
                    "title": "Crânios Pro: Seu Assistente Pessoal",
                    "presentation": "Perfeito! Profissionais liberais são os que mais se beneficiam das nossas soluções.\n\nÉ como ter um assistente pessoal 24/7 que nunca tira férias:\n\n• Captação automática\n• Processos automatizados\n• Agenda otimizada\n• Cobrança automática\n\nCase Real: Advogado [Nome] dobrou a carteira de clientes em 4 meses sem contratar ninguém.",
                    "data": "Estudo da FGV sobre Profissionais Liberais:\n- 78% gastam mais tempo com administração que core business\n- 45% perdem clientes por falta de follow-up\n- Quem automatiza ganha 60% mais"
                },
                "imobiliaria": {
                    "title": "CrâniosImobi: Revolução no Atendimento",
                    "presentation": "Excelente! O mercado imobiliário de Aracaju está precisando MUITO disso.\n\nVocê sabe que o atendimento das imobiliárias aqui é péssimo, né? Demora, não retorna, cliente fica perdido...\n\nImagina ser a ÚNICA imobiliária que:\n\n• Responde na hora - 24/7\n• Qualifica leads automaticamente\n• Acompanha todo o processo\n• Fecha mais negócios\n\nOportunidade Única: Enquanto a concorrência dorme, você domina o mercado.",
                    "data": "Pesquisa que fizemos em Aracaju:\n- 89% dos clientes reclamam da demora no retorno\n- 67% desistem por falta de acompanhamento\n- Quem responde rápido fecha 3x mais"
                }
            },
            "objection_handling": {
                "tempo": {
                    "objection": "Não tenho tempo para isso agora",
                    "response": "Entendo perfeitamente! E é EXATAMENTE por isso que você precisa disso URGENTE!\n\nOlha só: você está me dizendo que não tem tempo, certo?\n\nNossos clientes economizam 20-30 horas por semana. São 80-120 horas por mês. São 960-1440 horas por ano!\n\nÉ como se você ganhasse 6-9 meses extras no ano para fazer o que quiser.\n\nO [Nome do Cliente] me disse: 'Ana, eu recuperei minha vida. Agora tenho tempo para ser pai, marido, e ainda cresci 70% no negócio.'\n\nSão 15 minutinhos de conversa que podem te devolver centenas de horas.\n\nNão vale o investimento?"
                },
                "preco": {
                    "objection": "Está caro",
                    "response": "Ótima pergunta! Vou te mostrar uma conta que vai te surpreender:\n\nCenário Atual (sem automação):\n- Você gasta 20h/semana com tarefas repetitivas\n- Seu tempo vale R$ 100/hora (sendo conservador)\n- São R$ 2.000/semana = R$ 8.000/mês perdidos\n\nCenário com Crânios:\n- Investimento: R$ 597/mês\n- Economia: R$ 8.000/mês\n- Lucro líquido: R$ 7.403/mês\n\nSem contar que você ainda vai vender mais, atender melhor, e ter qualidade de vida.\n\nO [Nome] calculou que o ROI dele foi de 1.340% no primeiro ano.\n\nA pergunta não é se está caro... é se você pode continuar perdendo R$ 8.000/mês!"
                },
                "complexidade": {
                    "objection": "Deve ser muito complicado",
                    "response": "Essa é a melhor parte!\n\nSabe configurar Netflix? Então você consegue usar o Crânios!\n\nNosso sistema foi feito pensando em pessoas ocupadas como você. Tudo é clique e pronto.\n\nO [Nome] me disse: 'Ana, meu filho de 12 anos configurou algumas coisas mais rápido que eu!'\n\nE olha, se por acaso você tiver alguma dúvida, nossa equipe faz tudo para você. Você literalmente não precisa mexer em nada.\n\nÉ mais fácil que pedir comida no iFood!"
                }
            },
            "closing_techniques": {
                "direct": "Baseado em tudo que conversamos, tenho certeza absoluta que conseguimos transformar seu negócio.\n\nO [Seu Nome] é especialista em [área específica] e já ajudou mais de [número] profissionais como você a:\n- Economizar 20-30 horas semanais\n- Aumentar faturamento em 40-80%\n- Ter qualidade de vida de volta\n\nQue tal uma conversa rápida de 15 minutinhos com ele?\n\nEle vai te mostrar exatamente como implementar isso no seu negócio e quanto você vai economizar.\n\nQuando você tem um tempinho livre? Hoje à tarde ou amanhã de manhã?",
                "urgency": "Olha, vou ser transparente com você...\n\nEstamos com a agenda lotada porque a demanda explodiu. Tem gente esperando 2 semanas para conversar.\n\nMas como você veio através do [origem], consegui encaixar você ainda esta semana.\n\nSão só 15 minutinhos que podem mudar completamente seu negócio.\n\nHoje às 16h ou amanhã às 9h? Qual funciona melhor?",
                "social_proof": "Sabe o que mais me motiva nesse trabalho?\n\nVer a transformação na vida das pessoas. Semana passada recebi um áudio do [Nome] emocionado porque conseguiu viajar com a família pela primeira vez em 3 anos... sem se preocupar com o negócio.\n\nO sistema estava vendendo, atendendo, e cuidando de tudo.\n\nVocê merece ter essa liberdade também.\n\nVamos agendar? 15 minutinhos que podem mudar sua vida."
            },
            "motivational_messages": [
                "E saiba: quando você junta visão estratégica + execução ousada, o que nasce é impossível de ignorar... e é exatamente isso que está acontecendo com a Crânios.\n\nAmanhã seguimos com tudo.\nAté lá, descanse bem — porque a revolução começa com quem sonha grande. 💭💥\nNos vemos em breve, CEO. 😎🧠"
            ]
        }
    
    def load_knowledge_base(self) -> Dict:
        """Carrega base de conhecimento por segmento"""
        return {
            "saude": {
                "vitaflow_features": [
                    "Agendamento automático 24/7",
                    "Confirmação de consultas via WhatsApp",
                    "Lembretes automáticos",
                    "Triagem inicial de pacientes",
                    "Integração com prontuário eletrônico",
                    "Relatórios de performance",
                    "Dashboard em tempo real"
                ],
                "benefits": [
                    "Redução de 60% no no-show",
                    "Aumento de 40% na ocupação da agenda",
                    "Economia de 20-30 horas semanais",
                    "Melhoria na satisfação do paciente",
                    "Redução de custos operacionais"
                ]
            },
            "comercio": {
                "features": [
                    "Catálogo digital automatizado",
                    "Vendas via WhatsApp",
                    "Controle de estoque",
                    "Programa de fidelidade",
                    "Marketing segmentado",
                    "Relatórios de vendas",
                    "Integração com delivery"
                ],
                "benefits": [
                    "Aumento de 50-180% nas vendas",
                    "Redução de 70% no tempo de atendimento",
                    "Melhoria na experiência do cliente",
                    "Controle total do negócio",
                    "Vendas 24/7 automatizadas"
                ]
            }
        }
    
    def load_persuasion_techniques(self) -> Dict:
        """Carrega técnicas de persuasão"""
        return {
            "spin_selling": {
                "situation": "Me conta rapidinho... qual é sua área de atuação e quantas pessoas trabalham com você?",
                "problem": "Hoje, onde você sente que mais perde tempo ou dinheiro? Atendimento? Controle? Vendas? Clientes que somem?",
                "implication": "E se isso continuar assim por mais 3 meses? O que você acha que vai acontecer com seu crescimento?",
                "need": "Imagina ter isso resolvido sem contratar ninguém, sem perder o controle e ainda podendo respirar com calma no fim do dia. Faz sentido pra você?"
            },
            "storytelling": {
                "template": "Tem uma coisa que eu sempre digo aqui: Tecnologia é só ferramenta. O que a gente vende é liberdade.\n\nUm cliente nosso, o [Nome], estava exausto, perdendo leads, sem tempo nem pra almoçar. A gente implementou a automação e, em 7 dias, ele estava fechando vendas enquanto dormia — e jantando com a esposa todos os dias.\n\nIsso te faria diferença?"
            },
            "mental_triggers": [
                "autoridade",
                "escassez", 
                "reciprocidade",
                "prova_social",
                "antecipacao",
                "compromisso_coerencia"
            ]
        }
    
    async def process_message(self, ai_request: AIRequest) -> AIResponse:
        """Processa mensagem principal"""
        try:
            # Processa mídia se presente
            if ai_request.media_type != "text" and ai_request.media_data:
                media_content = await self.process_media(ai_request.media_type, ai_request.media_data)
                ai_request.message += f"\n\n[Conteúdo da mídia: {media_content}]"
            
            # Analisa intenção e entidades
            intent_analysis = await self.analyze_intent(ai_request.message, ai_request.context)
            
            # Gera resposta baseada na intenção
            response_text = await self.generate_response(ai_request, intent_analysis)
            
            # Gera áudio se necessário
            audio_response = None
            if ai_request.context.get("audio_enabled", False):
                audio_response = await self.generate_audio_response(response_text)
            
            # Salva interação no Supabase
            await self.save_interaction(ai_request, response_text, intent_analysis)
            
            return AIResponse(
                text_response=response_text,
                audio_response=audio_response,
                confidence_score=intent_analysis.get("confidence", 0.8),
                intent=intent_analysis.get("intent", "general"),
                entities=intent_analysis.get("entities", {}),
                next_action=intent_analysis.get("next_action", "continue"),
                requires_human=intent_analysis.get("requires_human", False)
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            return AIResponse(
                text_response="Desculpe, ocorreu um erro. Pode repetir sua mensagem?",
                confidence_score=0.0,
                intent="error"
            )
    
    async def process_media(self, media_type: str, media_data: bytes) -> str:
        """Processa diferentes tipos de mídia"""
        try:
            if media_type == "audio":
                return await self.process_audio(media_data)
            elif media_type == "image":
                return await self.process_image(media_data)
            elif media_type == "video":
                return await self.process_video(media_data)
            else:
                return "Tipo de mídia não suportado"
                
        except Exception as e:
            logger.error(f"Erro ao processar mídia {media_type}: {e}")
            return f"Erro ao processar {media_type}"
    
    async def process_audio(self, audio_data: bytes) -> str:
        """Processa áudio e converte para texto"""
        try:
            # Salva áudio temporariamente
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Reconhece fala
            with sr.AudioFile(temp_file_path) as source:
                audio = self.speech_recognizer.record(source)
                text = self.speech_recognizer.recognize_google(audio, language="pt-BR")
            
            # Remove arquivo temporário
            os.unlink(temp_file_path)
            
            return text
            
        except Exception as e:
            logger.error(f"Erro ao processar áudio: {e}")
            return "Não consegui entender o áudio"
    
    async def process_image(self, image_data: bytes) -> str:
        """Processa imagem e extrai informações"""
        try:
            # Carrega imagem
            image = Image.open(BytesIO(image_data))
            
            # Converte para análise
            image_array = np.array(image)
            
            # Análise básica da imagem
            height, width = image_array.shape[:2]
            
            # Aqui você pode integrar com serviços de visão computacional
            # Por exemplo, Google Vision API, AWS Rekognition, etc.
            
            return f"Imagem recebida: {width}x{height} pixels. Analisando conteúdo..."
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            return "Erro ao analisar imagem"
    
    async def process_video(self, video_data: bytes) -> str:
        """Processa vídeo e extrai informações"""
        try:
            # Salva vídeo temporariamente
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                temp_file.write(video_data)
                temp_file_path = temp_file.name
            
            # Abre vídeo
            cap = cv2.VideoCapture(temp_file_path)
            
            # Extrai informações básicas
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            os.unlink(temp_file_path)
            
            return f"Vídeo recebido: {duration:.1f} segundos, {frame_count} frames. Analisando conteúdo..."
            
        except Exception as e:
            logger.error(f"Erro ao processar vídeo: {e}")
            return "Erro ao analisar vídeo"
    
    async def analyze_intent(self, message: str, context: Dict) -> Dict:
        """Analisa intenção da mensagem"""
        try:
            # Palavras-chave para diferentes intenções
            intent_keywords = {
                "interesse_compra": ["quero", "preciso", "comprar", "contratar", "investir"],
                "solicitar_proposta": ["proposta", "orçamento", "preço", "valor", "investimento"],
                "agendar_reuniao": ["agendar", "reunião", "conversar", "apresentação"],
                "objecao_preco": ["caro", "barato", "preço", "valor", "investimento"],
                "objecao_tempo": ["tempo", "ocupado", "corrido", "pressa"],
                "objecao_complexidade": ["difícil", "complicado", "complexo", "simples"],
                "duvida_tecnica": ["como", "funciona", "técnico", "integração"],
                "despedida": ["tchau", "obrigado", "até", "depois"]
            }
            
            message_lower = message.lower()
            detected_intents = []
            
            for intent, keywords in intent_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    detected_intents.append(intent)
            
            # Determina intenção principal
            main_intent = detected_intents[0] if detected_intents else "general"
            
            # Extrai entidades (nomes, números, etc.)
            entities = self.extract_entities(message)
            
            # Determina próxima ação
            next_action = self.determine_next_action(main_intent, context)
            
            return {
                "intent": main_intent,
                "confidence": 0.8 if detected_intents else 0.5,
                "entities": entities,
                "next_action": next_action,
                "requires_human": main_intent in ["objecao_complexa", "reclamacao"]
            }
            
        except Exception as e:
            logger.error(f"Erro na análise de intenção: {e}")
            return {"intent": "general", "confidence": 0.5}
    
    def extract_entities(self, message: str) -> Dict:
        """Extrai entidades da mensagem"""
        entities = {}
        
        # Extrai números
        import re
        numbers = re.findall(r'\d+', message)
        if numbers:
            entities["numbers"] = numbers
        
        # Extrai nomes próprios (simplificado)
        words = message.split()
        proper_nouns = [word for word in words if word.istitle()]
        if proper_nouns:
            entities["names"] = proper_nouns
        
        return entities
    
    def determine_next_action(self, intent: str, context: Dict) -> str:
        """Determina próxima ação baseada na intenção"""
        action_map = {
            "interesse_compra": "present_solution",
            "solicitar_proposta": "generate_proposal",
            "agendar_reuniao": "schedule_meeting",
            "objecao_preco": "handle_price_objection",
            "objecao_tempo": "handle_time_objection",
            "objecao_complexidade": "handle_complexity_objection",
            "duvida_tecnica": "provide_technical_info",
            "despedida": "close_conversation"
        }
        
        return action_map.get(intent, "continue")
    
    async def generate_response(self, ai_request: AIRequest, intent_analysis: Dict) -> str:
        """Gera resposta baseada na análise"""
        try:
            intent = intent_analysis.get("intent", "general")
            business_type = ai_request.business_type.lower()
            
            # Resposta baseada na intenção
            if intent == "interesse_compra":
                return self.get_business_presentation(business_type)
            elif intent == "solicitar_proposta":
                return await self.generate_proposal_response(ai_request.lead_data)
            elif intent == "agendar_reuniao":
                return self.get_scheduling_response()
            elif intent.startswith("objecao_"):
                objection_type = intent.replace("objecao_", "")
                return self.get_objection_response(objection_type)
            else:
                return await self.generate_contextual_response(ai_request, intent_analysis)
                
        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {e}")
            return "Desculpe, pode repetir sua pergunta?"
    
    def get_business_presentation(self, business_type: str) -> str:
        """Retorna apresentação específica do negócio"""
        presentations = self.ana_script["business_presentations"]
        
        if business_type in presentations:
            presentation = presentations[business_type]
            return f"{presentation['presentation']}\n\n{presentation['data']}"
        else:
            return "Nossos clientes estão tendo resultados incríveis com nossas automações. Quer saber como isso pode funcionar no seu negócio?"
    
    async def generate_proposal_response(self, lead_data: Dict) -> str:
        """Gera resposta para solicitação de proposta"""
        return """Perfeito! Vou preparar uma proposta personalizada para você.

Com base no que conversamos, vou incluir:

✅ Automação completa do atendimento
✅ Integração com WhatsApp Business
✅ Dashboard em tempo real
✅ Relatórios personalizados
✅ Suporte técnico completo

Vou enviar por email em até 2 horas.

Mas que tal uma conversa rápida de 15 minutos para eu te mostrar o sistema funcionando na prática?

Hoje às 16h ou amanhã às 9h?"""
    
    def get_scheduling_response(self) -> str:
        """Retorna resposta para agendamento"""
        return self.ana_script["closing_techniques"]["direct"]
    
    def get_objection_response(self, objection_type: str) -> str:
        """Retorna resposta para objeções"""
        objections = self.ana_script["objection_handling"]
        
        if objection_type in objections:
            return objections[objection_type]["response"]
        else:
            return "Entendo sua preocupação. Que tal conversarmos sobre isso? Posso esclarecer todas suas dúvidas."
    
    async def generate_contextual_response(self, ai_request: AIRequest, intent_analysis: Dict) -> str:
        """Gera resposta contextual usando Arcee.ai"""
        try:
            # Prepara contexto para a IA
            context_prompt = self.build_context_prompt(ai_request, intent_analysis)
            
            # Chama Arcee.ai
            response = await self.call_arcee_ai(context_prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"Erro ao gerar resposta contextual: {e}")
            return "Interessante! Me conta mais sobre isso. Como posso te ajudar especificamente?"
    
    def build_context_prompt(self, ai_request: AIRequest, intent_analysis: Dict) -> str:
        """Constrói prompt contextual para a IA"""
        prompt = f"""
Você é a Ana, assistente virtual da Crânios. Sua personalidade é profissional, empática e persuasiva.

Contexto da conversa:
- Tipo de negócio: {ai_request.business_type}
- Intenção detectada: {intent_analysis.get('intent')}
- Mensagem do cliente: {ai_request.message}

Histórico da conversa:
{json.dumps(ai_request.conversation_history, indent=2) if ai_request.conversation_history else 'Primeira interação'}

Dados do lead:
{json.dumps(ai_request.lead_data, indent=2) if ai_request.lead_data else 'Não coletados ainda'}

Instruções:
1. Responda como a Ana, mantendo o tom profissional e persuasivo
2. Use técnicas de vendas quando apropriado
3. Sempre direcione para o fechamento ou agendamento
4. Seja empática e entenda as necessidades do cliente
5. Use dados e cases de sucesso quando relevante
6. Mantenha respostas concisas mas impactantes

Resposta:
"""
        return prompt
    
    async def call_arcee_ai(self, prompt: str) -> str:
        """Chama API do Arcee.ai"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "arcee-agent",
                    "messages": [
                        {"role": "system", "content": "Você é a Ana, assistente virtual especialista em vendas da Crânios."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7
                }
                
                async with session.post(
                    f"{self.arcee_base_url}/chat/completions",
                    headers=self.arcee_headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        logger.error(f"Erro na API Arcee.ai: {response.status}")
                        return "Desculpe, estou com dificuldades técnicas. Pode repetir?"
                        
        except Exception as e:
            logger.error(f"Erro ao chamar Arcee.ai: {e}")
            return "Interessante! Me conta mais sobre isso."
    
    async def generate_audio_response(self, text: str) -> bytes:
        """Gera resposta em áudio"""
        try:
            # Salva áudio temporariamente
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            # Gera áudio
            self.tts_engine.save_to_file(text, temp_file_path)
            self.tts_engine.runAndWait()
            
            # Lê arquivo gerado
            with open(temp_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Remove arquivo temporário
            os.unlink(temp_file_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {e}")
            return b""
    
    async def save_interaction(self, ai_request: AIRequest, response: str, intent_analysis: Dict):
        """Salva interação no Supabase"""
        try:
            interaction_data = {
                "phone": ai_request.context.get("phone", ""),
                "message": ai_request.message,
                "response": response,
                "intent": intent_analysis.get("intent"),
                "confidence": intent_analysis.get("confidence"),
                "business_type": ai_request.business_type,
                "media_type": ai_request.media_type,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table('ai_interactions').insert(interaction_data).execute()
            
        except Exception as e:
            logger.error(f"Erro ao salvar interação: {e}")
    
    async def generate_personalized_response(self, lead_data: Dict, challenge: str, knowledge: Dict) -> str:
        """Gera resposta personalizada baseada nos dados do lead"""
        try:
            business_type = lead_data.get("business_type", "").lower()
            
            # Busca apresentação específica
            if business_type in self.ana_script["business_presentations"]:
                presentation = self.ana_script["business_presentations"][business_type]
                
                response = f"🎯 {presentation['title']}\n\n"
                response += f"{presentation['presentation']}\n\n"
                response += f"📊 {presentation['data']}\n\n"
                
                # Adiciona call-to-action
                response += "Quer ver como isso funciona na prática?\n\n"
                response += "Posso te mostrar o sistema funcionando em 15 minutinhos.\n\n"
                response += "Hoje à tarde ou amanhã de manhã?"
                
                return response
            else:
                return self.get_generic_presentation()
                
        except Exception as e:
            logger.error(f"Erro ao gerar resposta personalizada: {e}")
            return self.get_generic_presentation()
    
    def get_generic_presentation(self) -> str:
        """Retorna apresentação genérica"""
        return """🚀 Que incrível!

Nossos clientes estão tendo resultados impressionantes:

✅ Economia de 20-30 horas semanais
✅ Aumento de 40-80% no faturamento  
✅ Atendimento 24/7 automatizado
✅ Qualidade de vida de volta

Um cliente me disse: "Ana, pela primeira vez em anos consegui jantar com a família todos os dias!"

Isso não tem preço, né?

Quer ver como isso funciona na prática?

15 minutinhos que podem mudar seu negócio.

Hoje à tarde ou amanhã de manhã? 🎯"""

# Função para criar instância do AI Processor
def create_ai_processor(arcee_api_key: str, supabase_client: Client) -> AIProcessor:
    """Cria instância do AI Processor"""
    return AIProcessor(arcee_api_key, supabase_client)

