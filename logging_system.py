26-Sistema de Configuração

# logging_system.py
import logging
import logging.handlers
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import asyncio
from supabase import create_client
import traceback
import sys
import threading
from queue import Queue
from functools import wraps

class CustomFormatter(logging.Formatter):
    """Formatter personalizado para logs estruturados"""
    
    def format(self, record):
        # Cria estrutura JSON para o log
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Adiciona informações extras se disponíveis
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'client_phone'):
            log_data['client_phone'] = record.client_phone
        if hasattr(record, 'automation_id'):
            log_data['automation_id'] = record.automation_id
        
        # Adiciona stack trace para erros
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)

class DatabaseLogHandler(logging.Handler):
    """Handler para salvar logs no banco de dados"""
    
    def __init__(self):
        super().__init__()
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.queue = Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
    
    def emit(self, record):
        """Adiciona log à fila para processamento assíncrono"""
        try:
            log_data = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.thread,
                'process': record.process,
                'user_id': getattr(record, 'user_id', None),
                'request_id': getattr(record, 'request_id', None),
                'client_phone': getattr(record, 'client_phone', None),
                'automation_id': getattr(record, 'automation_id', None)
            }
            
            if record.exc_info:
                log_data['exception_type'] = record.exc_info[0].__name__
                log_data['exception_message'] = str(record.exc_info[1])
                log_data['traceback'] = ''.join(traceback.format_exception(*record.exc_info))
            
            self.queue.put(log_data)
            
        except Exception:
            self.handleError(record)
    
    def _worker(self):
        """Worker thread para processar logs da fila"""
        while True:
            try:
                log_data = self.queue.get()
                if log_data is None:
                    break
                
                # Salva no banco de dados
                self.supabase.table('system_logs').insert(log_data).execute()
                self.queue.task_done()
                
            except Exception as e:
                # Em caso de erro, não podemos usar logging aqui para evitar recursão
                print(f"Erro ao salvar log no banco: {e}", file=sys.stderr)

class CraniosLogger:
    """Classe principal para gerenciar logs do sistema Crânios"""
    
    def __init__(self):
        self.log_dir = Path(os.getenv('LOG_DIR', '/opt/cranios/logs'))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações de log
        self.log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
        self.max_file_size = int(os.getenv('LOG_MAX_FILE_SIZE', '10485760'))  # 10MB
        self.backup_count = int(os.getenv('LOG_BACKUP_COUNT', '10'))
        
        self.setup_logging()
    
    def setup_logging(self):
        """Configura o sistema de logging"""
        # Logger principal
        self.logger = logging.getLogger('cranios')
        self.logger.setLevel(self.log_level)
        
        # Remove handlers existentes
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Handler para arquivo principal
        main_file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'cranios.log',
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        main_file_handler.setFormatter(CustomFormatter())
        self.logger.addHandler(main_file_handler)
        
        # Handler para erros
        error_file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'errors.log',
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(CustomFormatter())
        self.logger.addHandler(error_file_handler)
        
        # Handler para console (desenvolvimento)
        if os.getenv('ENVIRONMENT') == 'development':
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(console_handler)
        
        # Handler para banco de dados
        db_handler = DatabaseLogHandler()
        db_handler.setLevel(logging.WARNING)  # Só salva warnings e erros no banco
        self.logger.addHandler(db_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Retorna um logger específico"""
        return logging.getLogger(f'cranios.{name}')
    
    def log_automation_event(self, automation_id: str, event: str, details: Dict[str, Any], level: str = 'INFO'):
        """Log específico para eventos de automação"""
        logger = self.get_logger('automation')
        log_level = getattr(logging, level.upper())
        
        extra = {
            'automation_id': automation_id,
            'event_type': event
        }
        
        message = f"Automation {event}: {json.dumps(details, ensure_ascii=False)}"
        logger.log(log_level, message, extra=extra)
    
    def log_client_interaction(self, client_phone: str, interaction_type: str, details: Dict[str, Any]):
        """Log específico para interações com clientes"""
        logger = self.get_logger('client_interaction')
        
        extra = {
            'client_phone': client_phone,
            'interaction_type': interaction_type
        }
        
        message = f"Client interaction: {json.dumps(details, ensure_ascii=False)}"
        logger.info(message, extra=extra)
    
    def log_api_request(self, endpoint: str, method: str, status_code: int, response_time: float, user_id: str = None):
        """Log específico para requisições API"""
        logger = self.get_logger('api')
        
        extra = {
            'user_id': user_id,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_time': response_time
        }
        
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        message = f"API {method} {endpoint} - {status_code} ({response_time:.3f}s)"
        logger.log(level, message, extra=extra)
    
    def log_payment_event(self, client_id: str, event_type: str, amount: float, details: Dict[str, Any]):
        """Log específico para eventos de pagamento"""
        logger = self.get_logger('payment')
        
        extra = {
            'client_id': client_id,
            'payment_event': event_type,
            'amount': amount
        }
        
        message = f"Payment {event_type}: R$ {amount:.2f} - {json.dumps(details, ensure_ascii=False)}"
        logger.info(message, extra=extra)
    
    def log_system_metric(self, metric_name: str, value: float, unit: str = None):
        """Log para métricas do sistema"""
        logger = self.get_logger('metrics')
        
        extra = {
            'metric_name': metric_name,
            'metric_value': value,
            'metric_unit': unit
        }
        
        message = f"Metric {metric_name}: {value} {unit or ''}"
        logger.info(message, extra=extra)

# Decorador para logging automático de funções
def log_function_call(logger_name: str = None):
    """Decorador para log automático de chamadas de função"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name or f'cranios.{func.__module__}')
            
            start_time = datetime.now()
            
            # Log de entrada
            logger.debug(f"Iniciando {func.__name__} com args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log de sucesso
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Concluído {func.__name__} em {duration:.3f}s")
                
                return result
                
            except Exception as e:
                # Log de erro
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"Erro em {func.__name__} após {duration:.3f}s: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator

# Decorador para logging assíncrono
def log_async_function_call(logger_name: str = None):
    """Decorador para log automático de funções assíncronas"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name or f'cranios.{func.__module__}')
            
            start_time = datetime.now()
            
            # Log de entrada
            logger.debug(f"Iniciando {func.__name__} (async) com args={args}, kwargs={kwargs}")
            
            try:
                result = await func(*args, **kwargs)
                
                # Log de sucesso
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Concluído {func.__name__} (async) em {duration:.3f}s")
                
                return result
                
            except Exception as e:
                # Log de erro
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"Erro em {func.__name__} (async) após {duration:.3f}s: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator

class LogAnalyzer:
    """Analisador de logs para insights e alertas"""
    
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
    
    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Retorna resumo de erros das últimas horas"""
        try:
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            result = self.supabase.table('system_logs')\
                .select('*')\
                .eq('level', 'ERROR')\
                .gte('timestamp', cutoff_time)\
                .execute()
            
            errors = result.data
            
            # Agrupa erros por tipo
            error_summary = {}
            for error in errors:
                error_type = error.get('exception_type', 'Unknown')
                if error_type not in error_summary:
                    error_summary[error_type] = {
                        'count': 0,
                        'latest': None,
                        'modules': set()
                    }
                
                error_summary[error_type]['count'] += 1
                error_summary[error_type]['modules'].add(error.get('module', 'Unknown'))
                
                if not error_summary[error_type]['latest'] or error['timestamp'] > error_summary[error_type]['latest']:
                    error_summary[error_type]['latest'] = error['timestamp']
            
            # Converte sets para listas para serialização JSON
            for error_type in error_summary:
                error_summary[error_type]['modules'] = list(error_summary[error_type]['modules'])
            
            return {
                'total_errors': len(errors),
                'period_hours': hours,
                'error_types': error_summary,
                'analysis_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.getLogger('cranios.log_analyzer').error(f"Erro ao analisar logs: {str(e)}")
            return {}
    
    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detecta anomalias nos logs"""
        anomalies = []
        
        try:
            # Verifica alta frequência de erros
            last_hour = (datetime.now() - timedelta(hours=1)).isoformat()
            
            error_count = self.supabase.table('system_logs')\
                .select('id', count='exact')\
                .eq('level', 'ERROR')\
                .gte('timestamp', last_hour)\
                .execute()
            
            if error_count.count > 10:  # Mais de 10 erros na última hora
                anomalies.append({
                    'type': 'high_error_rate',
                    'severity': 'high',
                    'message': f'{error_count.count} erros na última hora',
                    'timestamp': datetime.now().isoformat()
                })
            
            # Verifica erros críticos repetidos
            critical_errors = self.supabase.table('system_logs')\
                .select('exception_type')\
                .eq('level', 'ERROR')\
                .gte('timestamp', last_hour)\
                .execute()
            
            error_types = {}
            for error in critical_errors.data:
                error_type = error.get('exception_type', 'Unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                if count >= 5:  # Mesmo erro 5+ vezes
                    anomalies.append({
                        'type': 'repeated_error',
                        'severity': 'medium',
                        'message': f'{error_type} ocorreu {count} vezes na última hora',
                        'timestamp': datetime.now().isoformat()
                    })
            
            return anomalies
            
        except Exception as e:
            logging.getLogger('cranios.log_analyzer').error(f"Erro ao detectar anomalias: {str(e)}")
            return []

# Configuração global do sistema de logs
def setup_cranios_logging():
    """Configura o sistema de logs para toda a aplicação"""
    cranios_logger = CraniosLogger()
    
    # Configura loggers específicos
    loggers_config = {
        'cranios.automation': logging.INFO,
        'cranios.api': logging.INFO,
        'cranios.client_interaction': logging.INFO,
        'cranios.payment': logging.INFO,
        'cranios.metrics': logging.INFO,
        'cranios.health': logging.WARNING,
        'cranios.backup': logging.INFO
    }
    
    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    return cranios_logger

# Instância global
cranios_logger = setup_cranios_logging()

# Funções de conveniência
def get_logger(name: str) -> logging.Logger:
    """Função de conveniência para obter logger"""
    return cranios_logger.get_logger(name)

def log_automation_event(automation_id: str, event: str, details: Dict[str, Any], level: str = 'INFO'):
    """Função de conveniência para log de automação"""
    cranios_logger.log_automation_event(automation_id, event, details, level)

def log_client_interaction(client_phone: str, interaction_type: str, details: Dict[str, Any]):
    """Função de conveniência para log de interação"""
    cranios_logger.log_client_interaction(client_phone, interaction_type, details)

if __name__ == "__main__":
    # Teste do sistema de logs
    logger = get_logger('test')
    
    logger.info("Sistema de logs inicializado com sucesso")
    logger.warning("Este é um teste de warning")
    
    try:
        raise ValueError("Erro de teste")
    except Exception as e:
        logger.error("Teste de log de erro", exc_info=True)
    
    # Teste de log de automação
    log_automation_event('test_automation', 'started', {'test': True})
    
    print("Teste do sistema de logs concluído. Verifique os arquivos de log.")

from datetime import timedelta