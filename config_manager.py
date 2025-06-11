# config_manager.py
import os
import json
import yaml
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from supabase import create_client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Configurações do banco de dados"""
    url: str
    key: str
    max_connections: int = 10
    connection_timeout: int = 30

@dataclass
class APIConfig:
    """Configurações de APIs externas"""
    evolution_api_url: str
    evolution_api_key: str
    arcee_api_key: str
    autentique_api_key: str
    n8n_url: str
    n8n_api_key: str = None

@dataclass
class BusinessConfig:
    """Configurações de negócio"""
    company_name: str = "Crânios"
    admin_phone: str = None
    business_hours_start: str = "08:00"
    business_hours_end: str = "18:00"
    timezone: str = "America/Sao_Paulo"
    default_language: str = "pt-BR"

@dataclass
class AutomationConfig:
    """Configurações de automação"""
    max_concurrent_tasks: int = 10
    default_timeout: int = 300
    retry_attempts: int = 3
    retry_delay: int = 60
    enable_ai_learning: bool = True
    ai_confidence_threshold: float = 0.8

@dataclass
class NotificationConfig:
    """Configurações de notificação"""
    enable_email_alerts: bool = True
    enable_whatsapp_alerts: bool = True
    enable_system_alerts: bool = True
    admin_email: str = None
    alert_threshold_errors: int = 5
    alert_threshold_timeframe: int = 300  # 5 minutos

@dataclass
class BackupConfig:
    """Configurações de backup"""
    enable_auto_backup: bool = True
    backup_schedule: str = "0 2 * * *"  # Cron expression para 2:00 AM diariamente
    retention_days: int = 30
    use_s3: bool = False
    s3_bucket: str = None
    aws_access_key: str = None
    aws_secret_key: str = None
    aws_region: str = "us-east-1"

@dataclass
class SecurityConfig:
    """Configurações de segurança"""
    jwt_secret: str
    jwt_expiration: int = 3600  # 1 hora
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutos
    enable_2fa: bool = False
    password_min_length: int = 8
    session_timeout: int = 7200  # 2 horas

@dataclass
class LoggingConfig:
    """Configurações de logging"""
    log_level: str = "INFO"
    log_dir: str = "/opt/cranios/logs"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 10
    enable_db_logging: bool = True
    log_retention_days: int = 90

class ConfigManager:
    """Gerenciador central de configurações"""
    
    def __init__(self, config_file: str = None):
        self.config_file = Path(config_file or os.getenv('CONFIG_FILE', '/opt/cranios/config/config.yaml'))
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configurações padrão
        self._default_config = {
            'database': DatabaseConfig(
                url=os.getenv('SUPABASE_URL', ''),
                key=os.getenv('SUPABASE_KEY', '')
            ),
            'api': APIConfig(
                evolution_api_url=os.getenv('EVOLUTION_API_URL', 'http://localhost:8080'),
                evolution_api_key=os.getenv('EVOLUTION_API_KEY', ''),
                arcee_api_key=os.getenv('ARCEE_API_KEY', ''),
                autentique_api_key=os.getenv('AUTENTIQUE_API_KEY', ''),
                n8n_url=os.getenv('N8N_URL', 'http://localhost:5678')
            ),
            'business': BusinessConfig(
                admin_phone=os.getenv('ADMIN_PHONE')
            ),
            'automation': AutomationConfig(),
            'notification': NotificationConfig(
                admin_email=os.getenv('ADMIN_EMAIL')
            ),
            'backup': BackupConfig(
                s3_bucket=os.getenv('S3_BACKUP_BUCKET'),
                aws_access_key=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                use_s3=os.getenv('USE_S3_BACKUP', 'false').lower() == 'true'
            ),
            'security': SecurityConfig(
                jwt_secret=os.getenv('JWT_SECRET', 'your-secret-key-change-this')
            ),
            'logging': LoggingConfig(
                log_level=os.getenv('LOG_LEVEL', 'INFO'),
                log_dir=os.getenv('LOG_DIR', '/opt/cranios/logs')
            )
        }
        
        self._config = {}
        self._load_config()
        
        # Inicializa Supabase se configurado
        self.supabase = None
        if self._config['database'].url and self._config['database'].key:
            try:
                self.supabase = create_client(
                    self._config['database'].url,
                    self._config['database'].key
                )
            except Exception as e:
                logger.error(f"Erro ao conectar com Supabase: {e}")
    
    def _load_config(self):
        """Carrega configurações do arquivo e variáveis de ambiente"""
        # Carrega configurações padrão
        self._config = self._default_config.copy()
        
        # Carrega do arquivo se existir
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    self._merge_config(file_config)
                logger.info(f"Configurações carregadas de {self.config_file}")
            except Exception as e:
                logger.error(f"Erro ao carregar configurações do arquivo: {e}")
        
        # Override com variáveis de ambiente
        self._load_env_overrides()
    
    def _merge_config(self, new_config: Dict[str, Any]):
        """Mescla nova configuração com a existente"""
        for section, values in new_config.items():
            if section in self._config:
                if isinstance(values, dict):
                    # Atualiza campos específicos do dataclass
                    current_dataclass = self._config[section]
                    updated_values = asdict(current_dataclass)
                    updated_values.update(values)
                    
                    # Recria o dataclass com os novos valores
                    dataclass_type = type(current_dataclass)
                    self._config[section] = dataclass_type(**updated_values)
                else:
                    self._config[section] = values
    
    def _load_env_overrides(self):
        """Carrega overrides das variáveis de ambiente"""
        env_mappings = {
            # Database
            'SUPABASE_URL': ('database', 'url'),
            'SUPABASE_KEY': ('database', 'key'),
            
            # API
            'EVOLUTION_API_URL': ('api', 'evolution_api_url'),
            'EVOLUTION_API_KEY': ('api', 'evolution_api_key'),
            'ARCEE_API_KEY': ('api', 'arcee_api_key'),
            'AUTENTIQUE_API_KEY': ('api', 'autentique_api_key'),
            'N8N_URL': ('api', 'n8n_url'),
            
            # Business
            'ADMIN_PHONE': ('business', 'admin_phone'),
            'COMPANY_NAME': ('business', 'company_name'),
            'TIMEZONE': ('business', 'timezone'),
            
            # Security
            'JWT_SECRET': ('security', 'jwt_secret'),
            
            # Logging
            'LOG_LEVEL': ('logging', 'log_level'),
            'LOG_DIR': ('logging', 'log_dir'),
            
            # Backup
            'S3_BACKUP_BUCKET': ('backup', 's3_bucket'),
            'AWS_ACCESS_KEY_ID': ('backup', 'aws_access_key'),
            'AWS_SECRET_ACCESS_KEY': ('backup', 'aws_secret_key'),
        }
        
        for env_var, (section, field) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                current_dataclass = self._config[section]
                updated_values = asdict(current_dataclass)
                updated_values[field] = value
                
                dataclass_type = type(current_dataclass)
                self._config[section] = dataclass_type(**updated_values)
    
    def save_config(self):
        """Salva configurações no arquivo"""
        try:
            config_dict = {}
            for section, dataclass_obj in self._config.items():
                config_dict[section] = asdict(dataclass_obj)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Configurações salvas em {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return False
    
    def get(self, section: str, field: str = None) -> Any:
        """Obtém configuração específica"""
        if section not in self._config:
            return None
        
        if field is None:
            return self._config[section]
        
        return getattr(self._config[section], field, None)
    
    def set(self, section: str, field: str, value: Any):
        """Define configuração específica"""
        if section not in self._config:
            logger.error(f"Seção de configuração não encontrada: {section}")
            return False
        
        try:
            current_dataclass = self._config[section]
            updated_values = asdict(current_dataclass)
            updated_values[field] = value
            
            dataclass_type = type(current_dataclass)
            self._config[section] = dataclass_type(**updated_values)
            
            logger.info(f"Configuração atualizada: {section}.{field} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao definir configuração {section}.{field}: {e}")
            return False
    
    def update_from_database(self):
        """Atualiza configurações do banco de dados"""
        if not self.supabase:
            return False
        
        try:
            result = self.supabase.table('system_config').select('*').execute()
            
            for config in result.data:
                section = config['section']
                field = config['field']
                value = config['value']
                
                # Converte valor baseado no tipo
                if config.get('value_type') == 'bool':
                    value = value.lower() in ('true', '1', 'yes')
                elif config.get('value_type') == 'int':
                    value = int(value)
                elif config.get('value_type') ==
                elif config.get(\'value_type\') == \'float\':
                    value = float(value)
                # Adicione outras conversões de tipo conforme necessário

                self.set(section, field, value)
            
            logger.info("Configurações atualizadas do banco de dados.")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar configurações do banco de dados: {e}")
            return False

# Exemplo de uso (opcional, para teste)
if __name__ == "__main__":
    # Para testar, defina as variáveis de ambiente necessárias (SUPABASE_URL, SUPABASE_KEY, etc.)
    # ou crie um arquivo config.yaml com as configurações.
    
    # Configurar logging básico para ver as saídas do ConfigManager
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    config_manager = ConfigManager()

    # Obter configurações
    print(f"Database URL: {config_manager.get('database', 'url')}")
    print(f"Evolution API Key: {config_manager.get('api', 'evolution_api_key')}")
    print(f"Nome da Empresa: {config_manager.get('business', 'company_name')}")
    print(f"Nível de Log: {config_manager.get('logging', 'log_level')}")

    # Definir uma configuração (exemplo)
    # config_manager.set('business', 'company_name', 'Nova Empresa Crânios')
    # print(f"Novo Nome da Empresa: {config_manager.get('business', 'company_name')}")

    # Salvar configurações (se alguma alteração foi feita e precisa ser persistida no arquivo)
    # config_manager.save_config()

    # Exemplo de atualização pelo banco (simulado, pois a tabela system_config precisaria existir e ter dados)
    # print("Tentando atualizar configurações do banco de dados...")
    # if config_manager.supabase:
    #     # Simular dados que viriam do banco
    #     # Geralmente, esta tabela seria populada por uma interface administrativa ou scripts de setup.
    #     # Exemplo de como a tabela 'system_config' poderia ser estruturada:
    #     # | id | section    | field        | value                | value_type |
    #     # |----|------------|--------------|----------------------|------------|
    #     # | 1  | business   | company_name | Empresa Exemplo DB   | string     |
    #     # | 2  | automation | max_tasks    | 20                   | int        |
    #     print("Supabase client inicializado, mas a atualização real depende da tabela 'system_config'.")
    # else:
    #     print("Supabase client não inicializado. Verifique as configurações de URL e KEY.")


