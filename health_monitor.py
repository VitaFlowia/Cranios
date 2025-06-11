# health_monitor.py
import asyncio
import aiohttp
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import os
from dataclasses import dataclass
from supabase import create_client
import json
import time

logger = logging.getLogger(__name__)

@dataclass
class HealthCheck:
    service: str
    status: str  # healthy, warning, critical
    response_time: float
    last_check: datetime
    error_message: str = None

class SystemHealthMonitor:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.services = {
            'evolution_api': os.getenv('EVOLUTION_API_URL', 'http://localhost:8080'),
            'n8n': os.getenv('N8N_URL', 'http://localhost:5678'),
            'supabase': os.getenv('SUPABASE_URL'),
            'arcee_ai': 'https://api.arcee.ai/v1',
            'autentique': 'https://api.autentique.com.br/v2',
            'redis': 'redis://localhost:6379',
            'postgres': os.getenv('DATABASE_URL', 'postgresql://localhost:5432/cranios')
        }
        self.health_checks = {}
        self.thresholds = {
            'cpu_warning': 70,
            'cpu_critical': 90,
            'memory_warning': 80,
            'memory_critical': 95,
            'disk_warning': 85,
            'disk_critical': 95,
            'response_time_warning': 2.0,
            'response_time_critical': 5.0
        }

    async def check_service_health(self, service_name: str, url: str) -> HealthCheck:
        """Verifica a saúde de um serviço específico"""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        if response_time > self.thresholds['response_time_critical']:
                            status = 'critical'
                        elif response_time > self.thresholds['response_time_warning']:
                            status = 'warning'
                        else:
                            status = 'healthy'
                    else:
                        status = 'critical'
                        
                    return HealthCheck(
                        service=service_name,
                        status=status,
                        response_time=response_time,
                        last_check=datetime.now(),
                        error_message=None if response.status == 200 else f"HTTP {response.status}"
                    )
                    
        except Exception as e:
            logger.error(f"Erro ao verificar {service_name}: {str(e)}")
            return HealthCheck(
                service=service_name,
                status='critical',
                response_time=time.time() - start_time,
                last_check=datetime.now(),
                error_message=str(e)
            )

    def get_system_metrics(self) -> Dict:
        """Coleta métricas do sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'status': self._get_status(cpu_percent, 'cpu')
                },
                'memory': {
                    'percent': memory.percent,
                    'used': memory.used,
                    'total': memory.total,
                    'status': self._get_status(memory.percent, 'memory')
                },
                'disk': {
                    'percent': disk.percent,
                    'used': disk.used,
                    'total': disk.total,
                    'status': self._get_status(disk.percent, 'disk')
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao coletar métricas do sistema: {str(e)}")
            return {}

    def _get_status(self, value: float, metric_type: str) -> str:
        """Determina o status baseado nos thresholds"""
        if value >= self.thresholds[f'{metric_type}_critical']:
            return 'critical'
        elif value >= self.thresholds[f'{metric_type}_warning']:
            return 'warning'
        else:
            return 'healthy'

    async def check_database_health(self) -> HealthCheck:
        """Verifica a saúde do banco de dados"""
        start_time = time.time()
        
        try:
            # Testa uma query simples
            result = self.supabase.table('health_checks').select('*').limit(1).execute()
            response_time = time.time() - start_time
            
            if result.data is not None:
                status = 'healthy' if response_time < 1.0 else 'warning'
            else:
                status = 'critical'
                
            return HealthCheck(
                service='database',
                status=status,
                response_time=response_time,
                last_check=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao verificar banco de dados: {str(e)}")
            return HealthCheck(
                service='database',
                status='critical',
                response_time=time.time() - start_time,
                last_check=datetime.now(),
                error_message=str(e)
            )

    async def save_health_check(self, health_check: HealthCheck):
        """Salva o resultado do health check no banco"""
        try:
            self.supabase.table('health_checks').insert({
                'service': health_check.service,
                'status': health_check.status,
                'response_time': health_check.response_time,
                'last_check': health_check.last_check.isoformat(),
                'error_message': health_check.error_message
            }).execute()
        except Exception as e:
            logger.error(f"Erro ao salvar health check: {str(e)}")

    async def run_health_checks(self) -> Dict:
        """Executa todos os health checks"""
        results = {}
        
        # Verifica serviços externos
        for service_name, url in self.services.items():
            if service_name in ['redis', 'postgres']:
                continue  # Estes serão verificados separadamente
                
            health_check = await self.check_service_health(service_name, url)
            results[service_name] = health_check
            await self.save_health_check(health_check)

        # Verifica banco de dados
        db_health = await self.check_database_health()
        results['database'] = db_health
        await self.save_health_check(db_health)

        # Coleta métricas do sistema
        system_metrics = self.get_system_metrics()
        results['system'] = system_metrics

        # Salva métricas do sistema
        if system_metrics:
            try:
                self.supabase.table('system_metrics').insert(system_metrics).execute()
            except Exception as e:
                logger.error(f"Erro ao salvar métricas do sistema: {str(e)}")

        return results

    async def send_alert(self, service: str, status: str, message: str):
        """Envia alertas para serviços críticos"""
        if status == 'critical':
            alert_data = {
                'service': service,
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'alert_type': 'system_health'
            }
            
            try:
                # Envia alerta via WhatsApp (Evolution API)
                evolution_url = self.services.get('evolution_api')
                if evolution_url:
                    async with aiohttp.ClientSession() as session:
                        await session.post(
                            f"{evolution_url}/message/sendText",
                            json={
                                'number': os.getenv('ADMIN_PHONE'),
                                'text': f"🚨 ALERTA CRÍTICO: {service}\n{message}"
                            }
                        )
                
                # Salva alerta no banco
                self.supabase.table('system_alerts').insert(alert_data).execute()
                
            except Exception as e:
                logger.error(f"Erro ao enviar alerta: {str(e)}")

    async def start_monitoring(self, interval: int = 300):
        """Inicia o monitoramento contínuo"""
        logger.info("Iniciando monitoramento de saúde do sistema")
        
        while True:
            try:
                results = await self.run_health_checks()
                
                # Verifica por problemas críticos
                for service, health_check in results.items():
                    if hasattr(health_check, 'status') and health_check.status == 'critical':
                        await self.send_alert(
                            service, 
                            health_check.status, 
                            health_check.error_message or "Serviço indisponível"
                        )
                
                logger.info(f"Health check completo: {len(results)} serviços verificados")
                
            except Exception as e:
                logger.error(f"Erro durante monitoramento: {str(e)}")
            
            await asyncio.sleep(interval)

    def get_health_summary(self) -> Dict:
        """Retorna um resumo da saúde do sistema"""
        try:
            # Busca últimos health checks
            recent_checks = self.supabase.table('health_checks')\
                .select('*')\
                .gte('last_check', (datetime.now() - timedelta(minutes=10)).isoformat())\
                .execute()
            
            summary = {
                'overall_status': 'healthy',
                'services': {},
                'last_updated': datetime.now().isoformat()
            }
            
            critical_count = 0
            warning_count = 0
            
            for check in recent_checks.data:
                service = check['service']
                status = check['status']
                
                summary['services'][service] = {
                    'status': status,
                    'response_time': check['response_time'],
                    'last_check': check['last_check']
                }
                
                if status == 'critical':
                    critical_count += 1
                elif status == 'warning':
                    warning_count += 1
            
            # Determina status geral
            if critical_count > 0:
                summary['overall_status'] = 'critical'
            elif warning_count > 0:
                summary['overall_status'] = 'warning'
            
            return summary
            
        except Exception as e:
            logger.error(f"Erro ao obter resumo de saúde: {str(e)}")
            return {
                'overall_status': 'unknown',
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }

# Inicialização
if __name__ == "__main__":
    import asyncio
    
    monitor = SystemHealthMonitor()
    asyncio.run(monitor.start_monitoring())

