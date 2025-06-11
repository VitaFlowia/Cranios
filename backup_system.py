# backup_system.py
import os
import asyncio
import logging
from datetime import datetime, timedelta
import subprocess
import boto3
from botocore.exceptions import ClientError
import gzip
import shutil
from pathlib import Path
import json
from typing import Dict, List
from supabase import create_client

logger = logging.getLogger(__name__)

class BackupSystem:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        
        # Configurações de backup
        self.backup_dir = Path(os.getenv('BACKUP_DIR', '/opt/cranios/backups'))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações AWS S3 (opcional)
        self.use_s3 = os.getenv('USE_S3_BACKUP', 'false').lower() == 'true'
        if self.use_s3:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            self.s3_bucket = os.getenv('S3_BACKUP_BUCKET')
        
        # Configurações de retenção
        self.retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        
    async def backup_database(self) -> Dict:
        """Realiza backup do banco de dados PostgreSQL"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"cranios_db_backup_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Comando pg_dump
            cmd = [
                'pg_dump',
                os.getenv('DATABASE_URL'),
                '--verbose',
                '--clean',
                '--no-owner',
                '--no-privileges',
                '-f', str(backup_path)
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0:
                # Comprimir backup
                compressed_path = self.compress_file(backup_path)
                
                # Upload para S3 se configurado
                s3_url = None
                if self.use_s3:
                    s3_url = await self.upload_to_s3(compressed_path, f"database/{compressed_path.name}")
                
                # Salvar registro do backup
                backup_record = {
                    'backup_type': 'database',
                    'filename': compressed_path.name,
                    'file_size': compressed_path.stat().st_size,
                    'backup_date': datetime.now().isoformat(),
                    's3_url': s3_url,
                    'status': 'completed',
                    'checksum': self.calculate_checksum(compressed_path)
                }
                
                self.supabase.table('backups').insert(backup_record).execute()
                
                # Remove arquivo original não comprimido
                backup_path.unlink()
                
                logger.info(f"Backup do banco de dados criado: {compressed_path}")
                return backup_record
                
            else:
                error_msg = process.stderr
                logger.error(f"Erro no backup do banco: {error_msg}")
                raise Exception(f"pg_dump falhou: {error_msg}")
                
        except Exception as e:
            logger.error(f"Erro durante backup do banco: {str(e)}")
            # Registra falha
            self.supabase.table('backups').insert({
                'backup_type': 'database',
                'backup_date': datetime.now().isoformat(),
                'status': 'failed',
                'error_message': str(e)
            }).execute()
            raise

    async def backup_files(self) -> Dict:
        """Backup de arquivos importantes"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"cranios_files_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        # Diretórios para backup
        dirs_to_backup = [
            '/opt/cranios/uploads',
            '/opt/cranios/logs',
            '/opt/cranios/config',
            '/opt/cranios/.env'
        ]
        
        try:
            # Criar arquivo tar.gz
            cmd = ['tar', '-czf', str(backup_path)] + [d for d in dirs_to_backup if os.path.exists(d)]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0:
                # Upload para S3 se configurado
                s3_url = None
                if self.use_s3:
                    s3_url = await self.upload_to_s3(backup_path, f"files/{backup_path.name}")
                
                backup_record = {
                    'backup_type': 'files',
                    'filename': backup_path.name,
                    'file_size': backup_path.stat().st_size,
                    'backup_date': datetime.now().isoformat(),
                    's3_url': s3_url,
                    'status': 'completed',
                    'checksum': self.calculate_checksum(backup_path)
                }
                
                self.supabase.table('backups').insert(backup_record).execute()
                
                logger.info(f"Backup de arquivos criado: {backup_path}")
                return backup_record
                
            else:
                error_msg = process.stderr
                logger.error(f"Erro no backup de arquivos: {error_msg}")
                raise Exception(f"tar falhou: {error_msg}")
                
        except Exception as e:
            logger.error(f"Erro durante backup de arquivos: {str(e)}")
            self.supabase.table('backups').insert({
                'backup_type': 'files',
                'backup_date': datetime.now().isoformat(),
                'status': 'failed',
                'error_message': str(e)
            }).execute()
            raise

    async def backup_n8n_workflows(self) -> Dict:
        """Backup dos workflows do N8N"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"cranios_n8n_workflows_{timestamp}.json"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Conecta à API do N8N para exportar workflows
            n8n_url = os.getenv('N8N_URL', 'http://localhost:5678')
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # Busca todos os workflows
                async with session.get(f"{n8n_url}/api/v1/workflows") as response:
                    if response.status == 200:
                        workflows = await response.json()
                        
                        # Salva workflows em arquivo JSON
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            json.dump(workflows, f, indent=2, ensure_ascii=False)
                        
                        # Comprimir
                        compressed_path = self.compress_file(backup_path)
                        
                        # Upload para S3 se configurado
                        s3_url = None
                        if self.use_s3:
                            s3_url = await self.upload_to_s3(compressed_path, f"n8n/{compressed_path.name}")
                        
                        backup_record = {
                            'backup_type': 'n8n_workflows',
                            'filename': compressed_path.name,
                            'file_size': compressed_path.stat().st_size,
                            'backup_date': datetime.now().isoformat(),
                            's3_url': s3_url,
                            'status': 'completed',
                            'checksum': self.calculate_checksum(compressed_path)
                        }
                        
                        self.supabase.table('backups').insert(backup_record).execute()
                        
                        # Remove arquivo original
                        backup_path.unlink()
                        
                        logger.info(f"Backup do N8N criado: {compressed_path}")
                        return backup_record
                    else:
                        raise Exception(f"Erro ao acessar N8N API: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erro durante backup do N8N: {str(e)}")
            self.supabase.table('backups').insert({
                'backup_type': 'n8n_workflows',
                'backup_date': datetime.now().isoformat(),
                'status': 'failed',
                'error_message': str(e)
            }).execute()
            raise

    def compress_file(self, file_path: Path) -> Path:
        """Comprime um arquivo usando gzip"""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return compressed_path

    def calculate_checksum(self, file_path: Path) -> str:
        """Calcula checksum MD5 do arquivo"""
        import hashlib
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def upload_to_s3(self, file_path: Path, s3_key: str) -> str:
        """Upload de arquivo para S3"""
        if not self.use_s3:
            return None
            
        try:
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={'StorageClass': 'STANDARD_IA'}
            )
            
            s3_url = f"s3://{self.s3_bucket}/{s3_key}"
            logger.info(f"Arquivo enviado para S3: {s3_url}")
            return s3_url
            
        except ClientError as e:
            logger.error(f"Erro ao enviar para S3: {str(e)}")
            return None

    async def cleanup_old_backups(self):
        """Remove backups antigos baseado na política de retenção"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        try:
            # Busca backups antigos no banco
            old_backups = self.supabase.table('backups')\
                .select('*')\
                .lt('backup_date', cutoff_date.isoformat())\
                .execute()
            
            for backup in old_backups.data:
                try:
                    # Remove arquivo local se existir
                    local_file = self.backup_dir / backup['filename']
                    if local_file.exists():
                        local_file.unlink()
                        logger.info(f"Arquivo local removido: {local_file}")
                    
                    # Remove do S3 se existir
                    if backup.get('s3_url') and self.use_s3:
                        s3_key = backup['s3_url'].replace(f"s3://{self.s3_bucket}/", "")
                        self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
                        logger.info(f"Arquivo S3 removido: {backup['s3_url']}")
                    
                    # Remove registro do banco
                    self.supabase.table('backups').delete().eq('id', backup['id']).execute()
                    
                except Exception as e:
                    logger.error(f"Erro ao remover backup {backup['filename']}: {str(e)}")
            
            logger.info(f"Limpeza de backups concluída: {len(old_backups.data)} backups removidos")
            
        except Exception as e:
            logger.error(f"Erro durante limpeza de backups: {str(e)}")

    async def full_backup(self) -> Dict:
        """Executa backup completo do sistema"""
        logger.info("Iniciando backup completo do sistema")
        
        backup_results = {
            'start_time': datetime.now().isoformat(),
            'backups': {},
            'status': 'success',
            'errors': []
        }
        
        # Backup do banco de dados
        try:
            db_backup = await self.backup_database()
            backup_results['backups']['database'] = db_backup
        except Exception as e:
            backup_results['errors'].append(f"Database backup failed: {str(e)}")
            backup_results['status'] = 'partial'
        
        # Backup de arquivos
        try:
            files_backup = await self.backup_files()
            backup_results['backups']['files'] = files_backup
        except Exception as e:
            backup_results['errors'].append(f"Files backup failed: {str(e)}")
            backup_results['status'] = 'partial'
        
        # Backup dos workflows N8N
        try:
            n8n_backup = await self.backup_n8n_workflows()
            backup_results['backups']['n8n'] = n8n_backup
        except Exception as e:
            backup_results['errors'].append(f"N8N backup failed: {str(e)}")
            backup_results['status'] = 'partial'
        
        # Limpeza de backups antigos
        try:
            await self.cleanup_old_backups()
        except Exception as e:
            backup_results['errors'].append(f"Cleanup failed: {str(e)}")
        
        backup_results['end_time'] = datetime.now().isoformat()
        
        # Registra resultado geral
        self.supabase.table('backup_sessions').insert({
            'session_date': backup_results['start_time'],
            'status': backup_results['status'],
            'backups_created': len(backup_results['backups']),
            'errors': backup_results['errors'],
            'duration_seconds': (
                datetime.fromisoformat(backup_results['end_time']) - 
                datetime.fromisoformat(backup_results['start_time'])
            ).total_seconds()
        }).execute()
        
        logger.info(f"Backup completo finalizado: {backup_results['status']}")
        return backup_results

    async def restore_database(self, backup_filename: str) -> bool:
        """Restaura banco de dados a partir de um backup"""
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            # Tenta baixar do S3 se configurado
            if self.use_s3:
                try:
                    self.s3_client.download_file(
                        self.s3_bucket,
                        f"database/{backup_filename}",
                        str(backup_path)
                    )
                except ClientError:
                    logger.error(f"Backup não encontrado: {backup_filename}")
                    return False
            else:
                logger.error(f"Backup não encontrado: {backup_filename}")
                return False
        
        try:
            # Descomprime se necessário
            if backup_filename.endswith('.gz'):
                decompressed_path = backup_path.with_suffix('')
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(decompressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path = decompressed_path
            
            # Restaura banco
            cmd = [
                'psql',
                os.getenv('DATABASE_URL'),
                '-f', str(backup_path)
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0:
                logger.info(f"Banco de dados restaurado com sucesso: {backup_filename}")
                return True
            else:
                logger.error(f"Erro na restauração: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Erro durante restauração: {str(e)}")
            return False

# Scheduler para backups automáticos
async def schedule_backups():
    """Agenda backups automáticos"""
    backup_system = BackupSystem()
    
    while True:
        try:
            # Backup completo diário às 2:00 AM
            now = datetime.now()
            if now.hour == 2 and now.minute == 0:
                await backup_system.full_backup()
                await asyncio.sleep(3600)  # Espera 1 hora para não executar novamente
            
            await asyncio.sleep(60)  # Verifica a cada minuto
            
        except Exception as e:
            logger.error(f"Erro no scheduler de backups: {str(e)}")
            await asyncio.sleep(300)  # Espera 5 minutos em caso de erro

if __name__ == "__main__":
    import asyncio
    
    backup_system = BackupSystem()
    asyncio.run(backup_system.full_backup())
