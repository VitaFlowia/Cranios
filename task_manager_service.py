"""
Task Manager Service - Crânios
Gerenciador automático de tarefas e cronogramas
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import logging
from supabase import create_client, Client
from dataclasses import dataclass
import uuid
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TaskTemplate:
    title: str
    description: str
    task_type: str
    priority: str
    days_offset: int
    default_assignee: str
    dependencies: List[str]
    estimated_hours: int

class TaskManager:
    def __init__(self):
        # Configurações
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.evolution_api_url = os.getenv('EVOLUTION_API_URL')
        self.evolution_api_key = os.getenv('EVOLUTION_API_KEY')
        
        # Inicializar cliente
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Templates de tarefas por tipo de serviço
        self.task_templates = self._load_task_templates()
    
    def _load_task_templates(self) -> Dict[str, List[TaskTemplate]]:
        """Carrega templates de tarefas por tipo de serviço"""
        return {
            'saude': [
                TaskTemplate(
                    title="Análise inicial do processo clínico",
                    description="Mapear todos os processos atuais da clínica {client_name}",
                    task_type="analysis",
                    priority="high",
                    days_offset=1,
                    default_assignee="analista",
                    dependencies=[],
                    estimated_hours=4
                ),
                TaskTemplate(
                    title="Configuração do sistema de agendamento automático",
                    description="Implementar sistema de agendamento via WhatsApp para {client_name}",
                    task_type="implementation",
                    priority="high",
                    days_offset=3,
                    default_assignee="dev",
                    dependencies=["analysis"],
                    estimated_hours=8
                ),
                TaskTemplate(
                    title="Configuração de lembretes automáticos",
                    description="Configurar lembretes de consulta 24h e 2h antes",
                    task_type="automation",
                    priority="medium",
                    days_offset=5,
                    default_assignee="dev",
                    dependencies=["implementation"],
                    estimated_hours=3
                ),
                TaskTemplate(
                    title="Integração com sistema de pagamentos",
                    description="Configurar cobranças automáticas via PIX",
                    task_type="integration",
                    priority="medium",
                    days_offset=7,
                    default_assignee="dev",
                    dependencies=["automation"],
                    estimated_hours=4
                ),
                TaskTemplate(
                    title="Treinamento da equipe",
                    description="Treinar equipe da {client_name} no novo sistema",
                    task_type="training",
                    priority="high",
                    days_offset=10,
                    default_assignee="trainer",
                    dependencies=["integration"],
                    estimated_hours=6
                ),
                TaskTemplate(
                    title="Go-live e monitoramento",
                    description="Colocar sistema em produção e monitorar primeiros dias",
                    task_type="deployment",
                    priority="critical",
                    days_offset=14,
                    default_assignee="dev",
                    dependencies=["training"],
                    estimated_hours=8
                )
            ],
            'comercio': [
                TaskTemplate(
                    title="Análise do processo de vendas",
                    description="Mapear funil de vendas atual de {client_name}",
                    task_type="analysis",
                    priority="high",
                    days_offset=1,
                    default_assignee="analista",
                    dependencies=[],
                    estimated_hours=3
                ),
                TaskTemplate(
                    title="Configuração de chatbot de vendas",
                    description="Implementar assistente de vendas via WhatsApp",
                    task_type="implementation",
                    priority="high",
                    days_offset=2,
                    default_assignee="dev",
                    dependencies=["analysis"],
                    estimated_hours=6
                ),
                TaskTemplate(
                    title="Sistema de carrinho abandonado",
                    description="Implementar recuperação automática de carrinho",
                    task_type="automation",
                    priority="medium",
                    days_offset=4,
                    default_assignee="dev",
                    dependencies=["implementation"],
                    estimated_hours=4
                ),
                TaskTemplate(
                    title="Integração com estoque",
                    description="Conectar sistema com controle de estoque",
                    task_type="integration",
                    priority="medium",
                    days_offset=6,
                    default_assignee="dev",
                    dependencies=["automation"],
                    estimated_hours=5
                ),
                TaskTemplate(
                    title="Sistema de fidelidade automático",
                    description="Implementar programa de pontos automático",
                    task_type="automation",
                    priority="low",
                    days_offset=8,
                    default_assignee="dev",
                    dependencies=["integration"],
                    estimated_hours=6
                ),
                TaskTemplate(
                    title="Treinamento e go-live",
                    description="Treinar equipe e colocar sistema em produção",
                    task_type="deployment",
                    priority="critical",
                    days_offset=12,
                    default_assignee="trainer",
                    dependencies=["automation"],
                    estimated_hours=8
                )
            ],
            'servicos': [
                TaskTemplate(
                    title="Mapeamento do processo de atendimento",
                    description="Analisar fluxo atual de atendimento de {client_name}",
                    task_type="analysis",
                    priority="high",
                    days_offset=1,
                    default_assignee="analista",
                    dependencies=[],
                    estimated_hours=3
                ),
                TaskTemplate(
                    title="Assistente de qualificação de leads",
                    description="Implementar bot para qualificar leads automaticamente",
                    task_type="implementation",
                    priority="high",
                    days_offset=3,
                    default_assignee="dev",
                    dependencies=["analysis"],
                    estimated_hours=7
                ),
                TaskTemplate(
                    title="Sistema de agendamento inteligente",
                    description="Configurar agendamento baseado em disponibilidade",
                    task_type="automation",
                    priority="high",
                    days_offset=5,
                    default_assignee="dev",
                    dependencies=["implementation"],
                    estimated_hours=5
                ),
                TaskTemplate(
                    title="Follow-up automático pós-atendimento",
                    description="Implementar sequência de follow-up automática",
                    task_type="automation",
                    priority="medium",
                    days_offset=7,
                    default_assignee="dev",
                    dependencies=["automation"],
                    estimated_hours=4
                ),
                TaskTemplate(
                    title="Relatórios automáticos",
                    description="Configurar relatórios automáticos de performance",
                    task_type="reporting",
                    priority="medium",
                    days_offset=9,
                    default_assignee="dev",
                    dependencies=["automation"],
                    estimated_hours=3
                ),
                TaskTemplate(
                    title="Deployment final",
                    description="Colocar todo sistema em produção",
                    task_type="deployment",
                    priority="critical",
                    days_offset=12,
                    default_assignee="dev",
                    dependencies=["reporting"],
                    estimated_hours=6
                )
            ],
            'default': [
                TaskTemplate(
                    title="Análise inicial do negócio",
                    description="Entender necessidades específicas de {client_name}",
                    task_type="analysis",
                    priority="high",
                    days_offset=1,
                    default_assignee="analista",
                    dependencies=[],
                    estimated_hours=4
                ),
                TaskTemplate(
                    title="Desenvolvimento de solução personalizada",
                    description="Criar automação específica para {service_type}",
                    task_type="implementation",
                    priority="high",
                    days_offset=5,
                    default_assignee="dev",
                    dependencies=["analysis"],
                    estimated_hours=12
                ),
                TaskTemplate(
                    title="Testes e ajustes",
                    description="Realizar testes completos da solução",
                    task_type="testing",
                    priority="high",
                    days_offset=10,
                    default_assignee="dev",
                    dependencies=["implementation"],
                    estimated_hours=6
                ),
                TaskTemplate(
                    title="Treinamento e deploy",
                    description="Treinar cliente e colocar em produção",
                    task_type="deployment",
                    priority="critical",
                    days_offset=14,
                    default_assignee="trainer",
                    dependencies=["testing"],
                    estimated_hours=8
                )
            ]
        }
    
    async def create_implementation_tasks(self, client_id: str, service_type: str, contract_data: Dict) -> Dict[str, Any]:
        """Cria todas as tarefas de implementação para um cliente"""
        try:
            templates = self.task_templates.get(service_type, self.task_templates['default'])
            created_tasks = []
            
            for template in templates:
                task_data = {
                    "id": str(uuid.uuid4()),
                    "title": template.title,
                    "description": template.description.format(
                        client_name=contract_data.get('client_name', ''),
                        service_type=service_type
                    ),
                    "assigned_to": template.default_assignee,
                    "client_id": client_id,
                    "task_type": template.task_type,
                    "priority": template.priority,
                    "status": "pending",
                    "due_date": (datetime.now() + timedelta(days=template.days_offset)).isoformat(),
                    "estimated_hours": template.estimated_hours,
                    "dependencies": json.dumps(template.dependencies),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                result = self.supabase.table('tasks').insert(task_data).execute()
                if result.data:
                    created_tasks.append(result.data[0])
                    logger.info(f"Tarefa criada: {template.title}")
            
            # Notificar equipe sobre novas tarefas
            await self._notify_team_new_tasks(created_tasks, contract_data.get('client_name'))
            
            return {
                "success": True,
                "tasks_created": len(created_tasks),
                "tasks": created_tasks
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar tarefas: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _notify_team_new_tasks(self, tasks: List[Dict], client_name: str):
        """Notifica equipe sobre novas tarefas criadas"""
        try:
            # Agrupar tarefas por responsável
            tasks_by_assignee = {}
            for task in tasks:
                assignee = task['assigned_to']
                if assignee not in tasks_by_assignee:
                    tasks_by_assignee[assignee] = []
                tasks_by_assignee[assignee].append(task)
            
            # Enviar notificações
            for assignee, assignee_tasks in tasks_by_assignee.items():
                message = f"🔥 *Novas tarefas para você!*\n\n"
                message += f"Cliente: *{client_name}*\n"
                message += f"Total de tarefas: *{len(assignee_tasks)}*\n\n"
                
                for i, task in enumerate(assignee_tasks[:3], 1):  # Mostrar só as 3 primeiras
                    due_date = datetime.fromisoformat(task['due_date'].replace('Z', '+00:00'))
                    message += f"{i}. {task['title']}\n"
                    message += f"   📅 Prazo: {due_date.strftime('%d/%m/%Y')}\n"
                    message += f"   ⚡ Prioridade: {task['priority']}\n\n"
                
                if len(assignee_tasks) > 3:
                    message += f"+ {len(assignee_tasks) - 3} outras tarefas...\n\n"
                
                message += "Acesse o sistema para ver detalhes! 🚀"
                
                # Aqui você colocaria o número do WhatsApp do funcionário
                phone_mapping = {
                    "analista": "5511999999999",  # Substituir pelo número real
                    "dev": "5511888888888",       # Substituir pelo número real
                    "trainer": "5511777777777"    # Substituir pelo número real
                }
                
                phone = phone_mapping.get(assignee)
                if phone:
                    await self._send_whatsapp_message(phone, message)
            
        except Exception as e:
            logger.error(f"Erro ao notificar equipe: {str(e)}")
    
    async def _send_whatsapp_message(self, phone: str, message: str):
        """Envia mensagem via WhatsApp usando Evolution API"""
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
    
    async def check_overdue_tasks(self) -> Dict[str, Any]:
        """Verifica e processa tarefas atrasadas"""
        try:
            current_time = datetime.now().isoformat()
            
            # Buscar tarefas atrasadas
            result = self.supabase.table('tasks').select('*').lt('due_date', current_time).eq('status', 'pending').execute()
            
            overdue_tasks = result.data if result.data else []
            
            if overdue_tasks:
                # Notificar sobre tarefas atrasadas
                await self._notify_overdue_tasks(overdue_tasks)
                
                # Marcar como atrasadas
                for task in overdue_tasks:
                    self.supabase.table('tasks').update({
                        'status': 'overdue',
                        'updated_at': datetime.now().isoformat()
                    }).eq('id', task['id']).execute()
            
            return {
                "success": True,
                "overdue_count": len(overdue_tasks),
                "tasks": overdue_tasks
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar tarefas atrasadas: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _notify_overdue_tasks(self, overdue_tasks: List[Dict]):
        """Notifica sobre tarefas atrasadas"""
        try:
            # Agrupar por responsável
            tasks_by_assignee = {}
            for task in overdue_tasks:
                assignee = task['assigned_to']
                if assignee not in tasks_by_assignee:
                    tasks_by_assignee[assignee] = []
                tasks_by_assignee[assignee].append(task)
            
            # Notificar cada responsável
            for assignee, tasks in tasks_by_assignee.items():
                message = f"🚨 *ATENÇÃO: Tarefas Atrasadas!*\n\n"
                message += f"Você tem *{len(tasks)}* tarefa(s) em atraso:\n\n"
                
                for i, task in enumerate(tasks[:5], 1):
                    due_date = datetime.fromisoformat(task['due_date'].replace('Z', '+00:00'))
                    days_late = (datetime.now() - due_date).days
                    message += f"{i}. {task['title']}\n"
                    message += f"   📅 Atrasada há: *{days_late} dias*\n"
                    message += f"   ⚡ Prioridade: {task['priority']}\n\n"
                
                message += "Por favor, atualize o status urgentemente! ⚠️"
                
                phone_mapping = {
                    "analista": "5511999999999",
                    "dev": "5511888888888",
                    "trainer": "5511777777777"
                }
                
                phone = phone_mapping.get(assignee)
                if phone:
                    await self._send_whatsapp_message(phone, message)
        
        except Exception as e:
            logger.error(f"Erro ao notificar tarefas atrasadas: {str(e)}")
    
    async def update_task_status(self, task_id: str, status: str, notes: str = None) -> Dict[str, Any]:
        """Atualiza status de uma tarefa"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if status == 'completed':
                update_data['completed_at'] = datetime.now().isoformat()
            
            if notes:
                update_data['notes'] = notes
            
            result = self.supabase.table('tasks').update(update_data).eq('id', task_id).execute()
            
            if result.data:
                # Verificar se pode desbloquear tarefas dependentes
                await self._check_dependent_tasks(task_id)
                
                return {
                    "success": True,
                    "task": result.data[0]
                }
            
            return {"success": False, "error": "Task not found"}
            
        except Exception as e:
            logger.error(f"Erro ao atualizar tarefa: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _check_dependent_tasks(self, completed_task_id: str):
        """Verifica e ativa tarefas que dependem da tarefa completada"""
        try:
            # Buscar tarefa completada para pegar seu tipo
            completed_task = self.supabase.table('tasks').select('*').eq('id', completed_task_id).execute()
            
            if not completed_task.data:
                return
            
            task_type = completed_task.data[0]['task_type']
            client_id = completed_task.data[0]['client_id']
            
            # Buscar tarefas pendentes do mesmo cliente
            pending_tasks = self.supabase.table('tasks').select('*').eq('client_id', client_id).eq('status', 'pending').execute()
            
            if pending_tasks.data:
                for task in pending_tasks.data:
                    dependencies = json.loads(task.get('dependencies', '[]'))
                    
                    # Se esta tarefa depende da que foi completada
                    if task_type in dependencies:
                        # Verificar se todas as dependências foram completadas
                        all_dependencies_met = True
                        for dep in dependencies:
                            dep_tasks = self.supabase.table('tasks').select('*').eq('client_id', client_id).eq('task_type', dep).execute()
                            
                            if not dep_tasks.data or any(t['status'] != 'completed' for t in dep_tasks.data):
                                all_dependencies_met = False
                                break
                        
                        # Se todas dependências foram atendidas, ativar a tarefa
                        if all_dependencies_met:
                            self.supabase.table('tasks').update({
                                'status': 'ready',
                                'updated_at': datetime.now().isoformat()
                            }).eq('id', task['id']).execute()
                            
                            # Notificar responsável
                            await self._notify_task_ready(task)
        
        except Exception as e:
            logger.error(f"Erro ao verificar tarefas dependentes: {str(e)}")
    
    async def _notify_task_ready(self, task: Dict):
        """Notifica que uma tarefa está pronta para execução"""
        try:
            message = f"✅ *Tarefa Liberada!*\n\n"
            message += f"A tarefa *{task['title']}* está pronta para execução.\n\n"
            message += f"📅 Prazo: {datetime.fromisoformat(task['due_date'].replace('Z', '+00:00')).strftime('%d/%m/%Y')}\n"
            message += f"⚡ Prioridade: {task['priority']}\n\n"
            message += "Todas as dependências foram concluídas! 🚀"
            
            phone_mapping = {
                "analista": "5511999999999",
                "dev": "5511888888888",
                "trainer": "5511777777777"
            }
            
            phone = phone_mapping.get(task['assigned_to'])
            if phone:
                await self._send_whatsapp_message(phone, message)
        
        except Exception as e:
            logger.error(f"Erro ao notificar tarefa pronta: {str(e)}")
    
    async def get_team_workload(self) -> Dict[str, Any]:
        """Retorna carga de trabalho da equipe"""
        try:
            # Buscar todas as tarefas ativas
            result = self.supabase.table('tasks').select('*').in_('status', ['pending', 'ready', 'in_progress']).execute()
            
            tasks = result.data if result.data else []
            
            workload = {}
            for task in tasks:
                assignee = task['assigned_to']
                if assignee not in workload:
                    workload[assignee] = {
                        'total_tasks': 0,
                        'total_hours': 0,
                        'overdue': 0,
                        'high_priority': 0
                    }
                
                workload[assignee]['total_tasks'] += 1
                workload[assignee]['total_hours'] += task.get('estimated_hours', 0)
                
                if task['status'] == 'overdue':
                    workload[assignee]['overdue'] += 1
                
                if task['priority'] == 'high' or task['priority'] == 'critical':
                    workload[assignee]['high_priority'] += 1
            
            return {
                "success": True,
                "workload": workload
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular carga de trabalho: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def generate_progress_report(self, client_id: str = None) -> Dict[str, Any]:
        """Gera relatório de progresso das tarefas"""
        try:
            query = self.supabase.table('tasks').select('*')
            
            if client_id:
                query = query.eq('client_id', client_id)
            
            result = query.execute()
            tasks = result.data if result.data else []
            
            if not tasks:
                return {"success": True, "report": "Nenhuma tarefa encontrada"}
            
            # Estatísticas gerais
            total_tasks = len(tasks)
            completed = len([t for t in tasks if t['status'] == 'completed'])
            pending = len([t for t in tasks if t['status'] == 'pending'])
            in_progress = len([t for t in tasks if t['status'] == 'in_progress'])
            overdue = len([t for t in tasks if t['status'] == 'overdue'])
            
            completion_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0
            
            # Agrupar por cliente se não especificado
            by_client = {}
            if not client_id:
                for task in tasks:
                    cid = task['client_id']
                    if cid not in by_client:
                        by_client[cid] = {'completed': 0, 'total': 0}
                    
                    by_client[cid]['total'] += 1
                    if task['status'] == 'completed':
                        by_client[cid]['completed'] += 1
            
            report = {
                "total_tasks": total_tasks,
                "completed": completed,
                "pending": pending,
                "in_progress": in_progress,
                "overdue": overdue,
                "completion_rate": round(completion_rate, 2),
                "by_client": by_client if not client_id else None
            }
            
            return {
                "success": True,
                "report": report
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            return {"success": False, "error": str(e)}

# Função para executar verificações periódicas
async def run_periodic_checks():
    """Executa verificações periódicas do sistema"""
    task_manager = TaskManager()
    
    while True:
        try:
            # Verificar tarefas atrasadas
            await task_manager.check_overdue_tasks()
            
            # Aguardar 1 hora antes da próxima verificação
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Erro na verificação periódica: {str(e)}")
            await asyncio.sleep(300)  # Aguardar 5 minutos em caso de erro

if __name__ == "__main__":
    # Para testar o sistema
    import asyncio
    
    async def test_task_manager():
        tm = TaskManager()
        
        # Teste de criação de tarefas
        contract_data = {
            "client_name": "Clínica Exemplo",
            "service_type": "saude"
        }
        
        result = await tm.create_implementation_tasks("123", "saude", contract_data)
        print(f"Resultado: {result}")
        
        # Teste de relatório
        report = await tm.generate_progress_report()
        print(f"Relatório: {report}")
    
    # asyncio.run(test_task_manager())
