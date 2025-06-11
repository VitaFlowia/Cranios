07-Evolution API Service 
"""
Evolution API Service - Crânios
Integração completa com WhatsApp via Evolution API
"""
import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EvolutionAPIService:
    def __init__(self):
        # Configurações da Evolution API
        self.base_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:8080')
        self.api_key = os.getenv('EVOLUTION_API_KEY')
        self.instance_name = os.getenv('EVOLUTION_INSTANCE_NAME', 'cranios')
        
        # Headers padrão
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': self.api_key
        }
        
        # Configurações de webhook
        self.webhook_url = os.getenv('WEBHOOK_URL')
        
    async def create_instance(self) -> Dict:
        """Cria uma nova instância do WhatsApp"""
        try:
            url = f"{self.base_url}/instance/create"
            
            payload = {
                "instanceName": self.instance_name,
                "token": self.api_key,
                "qrcode": True,
                "webhook": self.webhook_url,
                "webhookByEvents": True,
                "webhookBase64": False,
                "events": [
                    "APPLICATION_STARTUP",
                    "QRCODE_UPDATED",
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "MESSAGES_DELETE",
                    "SEND_MESSAGE",
                    "CONTACTS_SET",
                    "CONTACTS_UPSERT",
                    "CONTACTS_UPDATE",
                    "PRESENCE_UPDATE",
                    "CHATS_SET",
                    "CHATS_UPSERT",
                    "CHATS_UPDATE",
                    "CHATS_DELETE",
                    "GROUPS_UPSERT",
                    "GROUP_UPDATE",
                    "GROUP_PARTICIPANTS_UPDATE",
                    "CONNECTION_UPDATE"
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Instância criada: {self.instance_name}")
                        return result
                    else:
                        error = await response.text()
                        logger.error(f"Erro ao criar instância: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao criar instância: {str(e)}")
            return None
    
    async def get_qr_code(self) -> Optional[str]:
        """Obtém o QR Code para conectar WhatsApp"""
        try:
            url = f"{self.base_url}/instance/connect/{self.instance_name}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('base64')
                    else:
                        logger.error(f"Erro ao obter QR Code: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao obter QR Code: {str(e)}")
            return None
    
    async def check_connection_status(self) -> Dict:
        """Verifica status da conexão"""
        try:
            url = f"{self.base_url}/instance/connectionState/{self.instance_name}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"state": "DISCONNECTED"}
                        
        except Exception as e:
            logger.error(f"Erro ao verificar conexão: {str(e)}")
            return {"state": "ERROR"}
    
    async def send_text_message(self, phone: str, message: str) -> Dict:
        """Envia mensagem de texto"""
        try:
            url = f"{self.base_url}/message/sendText/{self.instance_name}"
            
            # Limpar e formatar número
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "number": clean_phone,
                "textMessage": {
                    "text": message
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Mensagem enviada para {phone}")
                        return result
                    else:
                        error = await response.text()
                        logger.error(f"Erro ao enviar mensagem: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {str(e)}")
            return None
    
    async def send_media_message(self, phone: str, media_url: str, caption: str = "", media_type: str = "image") -> Dict:
        """Envia mensagem com mídia"""
        try:
            url = f"{self.base_url}/message/sendMedia/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "number": clean_phone,
                "mediaMessage": {
                    "mediatype": media_type,
                    "media": media_url,
                    "caption": caption
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Mídia enviada para {phone}")
                        return result
                    else:
                        error = await response.text()
                        logger.error(f"Erro ao enviar mídia: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao enviar mídia: {str(e)}")
            return None
    
    async def send_button_message(self, phone: str, text: str, buttons: List[Dict]) -> Dict:
        """Envia mensagem com botões"""
        try:
            url = f"{self.base_url}/message/sendButtons/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            # Formatar botões
            formatted_buttons = []
            for i, button in enumerate(buttons):
                formatted_buttons.append({
                    "buttonId": str(i + 1),
                    "buttonText": {"displayText": button["text"]},
                    "type": 1
                })
            
            payload = {
                "number": clean_phone,
                "buttonsMessage": {
                    "text": text,
                    "buttons": formatted_buttons,
                    "headerType": 1
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Botões enviados para {phone}")
                        return result
                    else:
                        error = await response.text()
                        logger.error(f"Erro ao enviar botões: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao enviar botões: {str(e)}")
            return None
    
    async def send_list_message(self, phone: str, text: str, button_text: str, sections: List[Dict]) -> Dict:
        """Envia mensagem com lista de opções"""
        try:
            url = f"{self.base_url}/message/sendList/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "number": clean_phone,
                "listMessage": {
                    "text": text,
                    "buttonText": button_text,
                    "sections": sections
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Lista enviada para {phone}")
                        return result
                    else:
                        error = await response.text()
                        logger.error(f"Erro ao enviar lista: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao enviar lista: {str(e)}")
            return None
    
    async def get_contact_info(self, phone: str) -> Dict:
        """Obtém informações do contato"""
        try:
            url = f"{self.base_url}/chat/whatsappNumbers/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "numbers": [clean_phone]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result and len(result) > 0:
                            return result[0]
                        return None
                    else:
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao obter info do contato: {str(e)}")
            return None
    
    async def mark_message_as_read(self, phone: str, message_id: str) -> bool:
        """Marca mensagem como lida"""
        try:
            url = f"{self.base_url}/chat/markMessageAsRead/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "readMessages": [{
                    "remoteJid": f"{clean_phone}@s.whatsapp.net",
                    "id": message_id
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=self.headers) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Erro ao marcar como lida: {str(e)}")
            return False
    
    async def set_presence(self, phone: str, presence: str = "available") -> bool:
        """Define presença (online, offline, etc)"""
        try:
            url = f"{self.base_url}/chat/presence/{self.instance_name}"
            
            clean_phone = self._clean_phone_number(phone)
            
            payload = {
                "number": clean_phone,
                "presence": presence
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=payload, headers=self.headers) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Erro ao definir presença: {str(e)}")
            return False
    
    def _clean_phone_number(self, phone: str) -> str:
        """Limpa e formata número de telefone"""
        # Remove todos os caracteres não numéricos
        clean = ''.join(filter(str.isdigit, phone))
        
        # Se não tem código do país, adiciona 55 (Brasil)
        if len(clean) == 11 and clean.startswith('11'):
            clean = '55' + clean
        elif len(clean) == 10:
            clean = '5511' + clean
        elif len(clean) == 11 and not clean.startswith('55'):
            clean = '55' + clean
        
        return clean
    
    async def process_webhook_message(self, webhook_data: Dict) -> Dict:
        """Processa mensagem recebida via webhook"""
        try:
            # Extrair dados da mensagem
            event_type = webhook_data.get('event')
            
            if event_type == 'messages.upsert':
                message_data = webhook_data.get('data', {})
                
                if message_data.get('messageType') == 'conversation':
                    # Mensagem de texto
                    phone = message_data.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
                    message = message_data.get('message', {}).get('conversation', '')
                    message_id = message_data.get('key', {}).get('id')
                    
                    return {
                        'type': 'text',
                        'phone': phone,
                        'message': message,
                        'message_id': message_id,
                        'timestamp': datetime.now().isoformat()
                    }
                
                elif message_data.get('messageType') == 'extendedTextMessage':
                    # Mensagem de texto com botão/lista
                    phone = message_data.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
                    message = message_data.get('message', {}).get('extendedTextMessage', {}).get('text', '')
                    message_id = message_data.get('key', {}).get('id')
                    
                    return {
                        'type': 'button_response',
                        'phone': phone,
                        'message': message,
                        'message_id': message_id,
                        'timestamp': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook: {str(e)}")
            return None
    
    async def send_typing_indicator(self, phone: str, duration: int = 3) -> bool:
        """Simula digitação"""
        try:
            clean_phone = self._clean_phone_number(phone)
            
            # Inicia digitação
            await self.set_presence(clean_phone, "composing")
            
            # Aguarda
            await asyncio.sleep(duration)
            
            # Para digitação
            await self.set_presence(clean_phone, "paused")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao simular digitação: {str(e)}")
            return False

# Funções auxiliares para N8N
async def send_whatsapp_message(phone: str, message: str) -> Dict:
    """Função wrapper para envio de mensagem via N8N"""
    try:
        evolution = EvolutionAPIService()
        return await evolution.send_text_message(phone, message)
    except Exception as e:
        logger.error(f"Erro no wrapper de envio: {str(e)}")
        return None

async def send_whatsapp_buttons(phone: str, text: str, buttons: List[str]) -> Dict:
    """Função wrapper para envio de botões via N8N"""
    try:
        evolution = EvolutionAPIService()
        
        # Formatar botões
        formatted_buttons = [{"text": btn} for btn in buttons]
        
        return await evolution.send_button_message(phone, text, formatted_buttons)
    except Exception as e:
        logger.error(f"Erro no wrapper de botões: {str(e)}")
        return None

# Para teste local
if __name__ == "__main__":
    async def test():
        evolution = EvolutionAPIService()
        status = await evolution.check_connection_status()
        print(f"Status: {status}")
    
    asyncio.run(test())