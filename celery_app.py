15-celery_app.py
"""
Configuração do Celery para tarefas assíncronas
Handles: follow-ups, pagamentos, relatórios, etc.
"""
import os
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging

# Configuração do Redis como broker
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Inicialização do Celery
celery_app = Celery(
    'cranios',
    broker=redis_url,
    backend=redis_url,
    include=[
        'celery_tasks.follow_up_tasks',
        'celery_tasks.payment_tasks', 
        'celery_tasks.report_tasks',
        'celery_tasks.maintenance_tasks'
    ]
)

# Configurações do Celery
celery_app.conf.update(
    # Timezone
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Serialização
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Configurações de worker
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Configurações de resultado
    result_expires=3600,  # 1 hora
    
    # Configurações de retry
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,  # 1 minuto
    task_max_retries=3,
    
    # Configurações de roteamento
    task_routes={
        'celery_tasks.follow_up_tasks.*': {'queue': 'follow_up'},
        'celery_tasks.payment_tasks.*': {'queue': 'payments'},
        'celery_tasks.report_tasks.*': {'queue': 'reports'},
        'celery_tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    },
    
    # Agendamentos (Celery Beat)
    beat_schedule={
        # Follow-up automático a cada 30 minutos
        'process-follow-ups': {
            'task': 'celery_tasks.follow_up_tasks.process_scheduled_follow_ups',
            'schedule': crontab(minute='*/30'),
        },
        
        # Verificação de pagamentos a cada 5 minutos
        'check-payments': {
            'task': 'celery_tasks.payment_tasks.check_pending_payments',
            'schedule': crontab(minute='*/5'),
        },
        
        # Relatório diário às 8h
        'daily-report': {
            'task': 'celery_tasks.report_tasks.generate_daily_report',
            'schedule': crontab(hour=8, minute=0),
        },
        
        # Limpeza de dados às 2h da manhã
        'cleanup-data': {
            'task': 'celery_tasks.maintenance_tasks.cleanup_old_data',
            'schedule': crontab(hour=2, minute=0),
        },
        
        # Backup de dados às 3h da manhã
        'backup-data': {
            'task': 'celery_tasks.maintenance_tasks.backup_database',
            'schedule': crontab(hour=3, minute=0),
        },
        
        # Verificação de contratos pendentes a cada 2 horas
        'check-contracts': {
            'task': 'celery_tasks.follow_up_tasks.check_pending_contracts',
            'schedule': crontab(minute=0, hour='*/2'),
        },
        
        # Análise de leads inativos diariamente às 10h
        'analyze-inactive-leads': {
            'task': 'celery_tasks.follow_up_tasks.analyze_inactive_leads',
            'schedule': crontab(hour=10, minute=0),
        },
        
        # Relatório semanal nas segundas às 9h
        'weekly-report': {
            'task': 'celery_tasks.report_tasks.generate_weekly_report',
            'schedule': crontab(hour=9, minute=0, day_of_week=1),
        },
        
        # Atualização de métricas a cada 15 minutos
        'update-metrics': {
            'task': 'celery_tasks.report_tasks.update_real_time_metrics',
            'schedule': crontab(minute='*/15'),
        },
    },
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def debug_task(self):
    """Task de debug para testar o Celery"""
    print(f'Request: {self.request!r}')
    return 'Celery funcionando!'