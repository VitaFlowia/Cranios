"""
Task Manager Service - Crânios
Responsável por criar tarefas de implementação após pagamento.
"""

import os
import logging
from datetime import datetime
from typing import List
from supabase import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    async def create_implementation_tasks(self, client_id: str, service_type: str = "default") -> List[dict]:
        """
        Cria tarefas padrão para o cliente após pagamento.
        """
        try:
            tasks = self._get_default_tasks(service_type)
            created = []

            for task in tasks:
                task_data = {
                    "client_id": client_id,
                    "title": task["title"],
                    "description": task["description"],
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }

                result = self.supabase.table("tasks").insert(task_data).execute()
                created.append(result.data[0] if result.data else {})

            logger.info(f"Tarefas criadas para o cliente {client_id}")
            return created

        except Exception as e:
            logger.error(f"Erro ao criar tarefas para cliente {client_id}: {e}")
            return []

    def _get_default_tasks(self, service_type: str) -> List[dict]:
        """
        Define tarefas padrão por tipo de serviço.
        """
        if service_type == "site":
            return [
                {"title": "Briefing do site", "description": "Reunir informações básicas sobre o projeto do site."},
                {"title": "Configurar domínio", "description": "Definir e apontar domínio do cliente para o servidor."},
                {"title": "Desenvolver páginas", "description": "Criar as páginas principais com base no briefing."}
            ]

        elif service_type == "consultoria":
            return [
                {"title": "Reunião inicial", "description": "Alinhar objetivos e contexto do cliente."},
                {"title": "Mapeamento de processos", "description": "Documentar o funcionamento atual do negócio."},
                {"title": "Plano de ação", "description": "Propor estratégia de automação."}
            ]

        # padrão genérico
        return [
            {"title": "Onboarding inicial", "description": "Enviar formulário para coletar dados do cliente."},
            {"title": "Configuração do sistema", "description": "Preparar ambiente com integrações necessárias."},
            {"title": "Ativar comunicação", "description": "Conectar canais de WhatsApp, e-mail ou outros meios."}
        ]

        report = await tm.generate_progress_report()
        print(f"Relatório: {report}")
    
    # asyncio.run(test_task_manager())
