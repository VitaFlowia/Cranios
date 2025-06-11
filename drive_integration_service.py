06-Drive Integration Service
"""
Drive Integration Service - Crânios
Integração com Google Drive para base de conhecimento
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import aiofiles
import asyncio
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DriveKnowledgeBase:
    def __init__(self):
        # Configurações
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', './credentials.json')
        self.drive_folder_id = os.getenv('DRIVE_KNOWLEDGE_BASE_ID')
        
        # Scopes necessários
        self.scopes = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/documents.readonly'
        ]
        
        # Inicializar serviços
        self.service = None
        self.docs_service = None
        self._initialize_services()
        
        # Cache para evitar requisições desnecessárias
        self.knowledge_cache = {}
        self.cache_ttl = 3600  # 1 hora
        
        # Mapeamento de tipos de negócio para pastas
        self.business_folders = {
            'saude': 'Saúde',
            'comercio': 'Comércio', 
            'servicos': 'Profissionais Liberais',
            'imobiliaria': 'Imobiliárias',
            'default': 'Geral'
        }
    
    def _initialize_services(self):
        """Inicializa os serviços do Google"""
        try:
            # Carregar credenciais
            if os.path.exists(self.credentials_path):
                credentials = Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=self.scopes
                )
            else:
                # Tentar carregar de variável de ambiente
                creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
                if creds_json:
                    creds_data = json.loads(creds_json)
                    credentials = Credentials.from_service_account_info(
                        creds_data, 
                        scopes=self.scopes
                    )
                else:
                    raise Exception("Credenciais do Google não encontradas")
            
            # Inicializar serviços
            self.service = build('drive', 'v3', credentials=credentials)
            self.docs_service = build('docs', 'v1', credentials=credentials)
            
            logger.info("Serviços Google inicializados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar serviços Google: {str(e)}")
            raise
    
    async def get_knowledge_for_business(self, business_type: str) -> str:
        """Retorna conhecimento específico para um tipo de negócio"""
        try:
            # Verificar cache
            cache_key = f"knowledge_{business_type}"
            if cache_key in self.knowledge_cache:
                cached_data = self.knowledge_cache[cache_key]
                if cached_data['timestamp'] + self.cache_ttl > asyncio.get_event_loop().time():
                    return cached_data['content']
            
            # Buscar pasta do tipo de negócio
            folder_name = self.business_folders.get(business_type, self.business_folders['default'])
            folder_id = await self._find_folder_by_name(folder_name)
            
            if not folder_id:
                logger.warning(f"Pasta não encontrada para {business_type}")
                return "Base de conhecimento não encontrada para este tipo de negócio."
            
            # Listar arquivos na pasta
            files = await self._list_files_in_folder(folder_id)
            
            # Processar cada arquivo
            knowledge_content = ""
            
            for file in files:
                file_content = await self._get_file_content(file)
                if file_content:
                    knowledge_content += f"\n\n=== {file['name']} ===\n"
                    knowledge_content += file_content
            
            # Salvar no cache
            self.knowledge_cache[cache_key] = {
                'content': knowledge_content,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            return knowledge_content
            
        except Exception as e:
            logger.error(f"Erro ao buscar conhecimento: {str(e)}")
            return "Erro ao acessar base de conhecimento."
    
    async def _find_folder_by_name(self, folder_name: str) -> Optional[str]:
        """Encontra pasta por nome dentro da pasta principal"""
        try:
            query = f"'{self.drive_folder_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar pasta {folder_name}: {str(e)}")
            return None
    
    async def _list_files_in_folder(self, folder_id: str) -> List[Dict]:
        """Lista todos os arquivos em uma pasta"""
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="name"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {str(e)}")
            return []
    
    async def _get_file_content(self, file: Dict) -> Optional[str]:
        """Extrai conteúdo de um arquivo baseado no tipo"""
        try:
            file_id = file['id']
            mime_type = file['mimeType']
            
            if mime_type == 'application/vnd.google-apps.document':
                # Google Docs
                return await self._get_google_doc_content(file_id)
            
            elif mime_type == 'text/plain':
                # Arquivo de texto
                return await self._get_text_file_content(file_id)
            
            elif mime_type == 'text/markdown':
                # Arquivo Markdown
                return await self._get_text_file_content(file_id)
            
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Google Sheets - extrair primeira aba
                return await self._get_sheet_content(file_id)
            
            else:
                logger.warning(f"Tipo de arquivo não suportado: {mime_type}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao extrair conteúdo do arquivo {file['name']}: {str(e)}")
            return None
    
    async def _get_google_doc_content(self, file_id: str) -> Optional[str]:
        """Extrai conteúdo de um Google Doc"""
        try:
            doc = self.docs_service.documents().get(documentId=file_id).execute()
            
            content = ""
            for element in doc.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    for text_element in paragraph.get('elements', []):
                        text_run = text_element.get('textRun')
                        if text_run:
                            content += text_run.get('content', '')
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Erro ao ler Google Doc: {str(e)}")
            return None
    
    async def _get_text_file_content(self, file_id: str) -> Optional[str]:
        """Extrai conteúdo de arquivo de texto"""
        try:
            media = self.service.files().get_media(fileId=file_id).execute()
            return media.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de texto: {str(e)}")
            return None
    
    async def _get_sheet_content(self, file_id: str) -> Optional[str]:
        """Extrai conteúdo básico de uma planilha"""
        try:
            # Para sheets, precisaríamos da API do Sheets
            # Por simplicidade, retornamos uma mensagem
            return "Conteúdo de planilha - integração específica necessária"
            
        except Exception as e:
            logger.error(f"Erro ao ler planilha: {str(e)}")
            return None
    
    async def search_knowledge(self, business_type: str, query: str) -> str:
        """Busca conhecimento específico baseado em uma query"""
        try:
            knowledge = await self.get_knowledge_for_business(business_type)
            
            # Busca simples por palavras-chave
            query_words = query.lower().split()
            relevant_sections = []
            
            sections = knowledge.split('\n\n')
            for section in sections:
                section_lower = section.lower()
                score = sum(1 for word in query_words if word in section_lower)
                
                if score > 0:
                    relevant_sections.append((score, section))
            
            # Ordenar por relevância
            relevant_sections.sort(key=lambda x: x[0], reverse=True)
            
            # Retornar as seções mais relevantes
            result = ""
            for score, section in relevant_sections[:3]:  # Top 3
                result += section + "\n\n"
            
            return result.strip() if result else knowledge[:1000]  # Fallback
            
        except Exception as e:
            logger.error(f"Erro ao buscar conhecimento: {str(e)}")
            return "Erro ao buscar informações específicas."
    
    async def update_knowledge_cache(self):
        """Força atualização do cache de conhecimento"""
        try:
            self.knowledge_cache.clear()
            
            # Pré-carregar conhecimento para todos os tipos de negócio
            for business_type in self.business_folders.keys():
                if business_type != 'default':
                    await self.get_knowledge_for_business(business_type)
            
            logger.info("Cache de conhecimento atualizado")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar cache: {str(e)}")
    
    def get_cache_status(self) -> Dict:
        """Retorna status do cache"""
        return {
            'cached_items': len(self.knowledge_cache),
            'cache_keys': list(self.knowledge_cache.keys()),
            'last_update': datetime.now().isoformat()
        }

# Função auxiliar para uso no N8N
async def get_business_knowledge(business_type: str, query: str = None) -> str:
    """Função wrapper para uso em fluxos N8N"""
    try:
        drive_kb = DriveKnowledgeBase()
        
        if query:
            return await drive_kb.search_knowledge(business_type, query)
        else:
            return await drive_kb.get_knowledge_for_business(business_type)
            
    except Exception as e:
        logger.error(f"Erro na função wrapper: {str(e)}")
        return "Erro ao acessar base de conhecimento."

# Para teste local
if __name__ == "__main__":
    async def test():
        kb = DriveKnowledgeBase()
        result = await kb.get_knowledge_for_business('saude')
        print(result[:500])  # Primeiros 500 caracteres
    
    asyncio.run(test())