"""
Setup inicial do banco de dados Crânios
Cria todas as tabelas e dados iniciais necessários
"""
import os
import asyncio
from supabase import create_client, Client
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseSetup:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not all([self.supabase_url, self.supabase_key]):
            raise ValueError("Variáveis SUPABASE_URL e SUPABASE_KEY são obrigatórias")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    async def create_tables(self):
        """Cria todas as tabelas necessárias"""
        try:
            # SQL para criação das tabelas
            tables_sql = [
                # Tabela de conversas
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    phone VARCHAR(20) NOT NULL,
                    name VARCHAR(100),
                    business_type VARCHAR(50),
                    company_size VARCHAR(20),
                    main_challenge VARCHAR(100),
                    lead_source VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'active',
                    context JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de leads
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID REFERENCES conversations(id),
                    name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    email VARCHAR(100),
                    business_type VARCHAR(50),
                    company_size VARCHAR(20),
                    estimated_revenue DECIMAL(10,2),
                    qualification_score INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'new',
                    assigned_to VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de propostas
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id),
                    proposal_data JSONB DEFAULT '{}',
                    total_value DECIMAL(10,2),
                    implementation_fee DECIMAL(10,2),
                    monthly_fee DECIMAL(10,2),
                    status VARCHAR(20) DEFAULT 'draft',
                    sent_at TIMESTAMP,
                    viewed_at TIMESTAMP,
                    signed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de contratos
                """
                CREATE TABLE IF NOT EXISTS contracts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    proposal_id UUID REFERENCES proposals(id),
                    contract_url VARCHAR(500),
                    autentique_id VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending',
                    signed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de tarefas
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    assigned_to VARCHAR(50),
                    client_id UUID,
                    task_type VARCHAR(50),
                    priority VARCHAR(20) DEFAULT 'medium',
                    status VARCHAR(20) DEFAULT 'pending',
                    due_date TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de transações financeiras
                """
                CREATE TABLE IF NOT EXISTS financial_transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    client_id UUID,
                    type VARCHAR(20), -- 'receivable' or 'payable'
                    description VARCHAR(200),
                    amount DECIMAL(10,2),
                    due_date DATE,
                    paid_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'pending',
                    pix_link VARCHAR(500),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de configurações
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value JSONB,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de templates
                """
                CREATE TABLE IF NOT EXISTS templates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) NOT NULL,
                    type VARCHAR(50) NOT NULL, -- 'proposal', 'contract', 'email'
                    business_type VARCHAR(50),
                    content TEXT,
                    variables JSONB DEFAULT '{}',
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """,
                
                # Tabela de automações
                """
                CREATE TABLE IF NOT EXISTS automations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) NOT NULL,
                    trigger_type VARCHAR(50) NOT NULL,
                    trigger_config JSONB DEFAULT '{}',
                    actions JSONB DEFAULT '[]',
                    status VARCHAR(20) DEFAULT 'active',
                    last_run TIMESTAMP,
                    run_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            ]
            
            # Executa criação das tabelas
            for sql in tables_sql:
                try:
                    self.supabase.rpc('exec_sql', {'sql': sql}).execute()
                    logger.info(f"Tabela criada com sucesso")
                except Exception as e:
                    logger.warning(f"Tabela pode já existir: {e}")
            
            logger.info("✅ Todas as tabelas foram criadas/verificadas")
            
        except Exception as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            raise
    
    async def insert_initial_data(self):
        """Insere dados iniciais necessários"""
        try:
            # Configurações iniciais
            initial_settings = [
                {
                    'key': 'system_status',
                    'value': {'status': 'active', 'version': '1.0.0'},
                    'description': 'Status geral do sistema'
                },
                {
                    'key': 'business_types',
                    'value': {
                        'types': ['Saúde', 'Comércio', 'Serviços', 'Imobiliária', 'Outro']
                    },
                    'description': 'Tipos de negócio disponíveis'
                },
                {
                    'key': 'company_sizes',
                    'value': {
                        'sizes': ['Solo', '2-5 funcionários', '6-15 funcionários', '15+ funcionários']
                    },
                    'description': 'Tamanhos de empresa disponíveis'
                },
                {
                    'key': 'pricing_rules',
                    'value': {
                        'Saúde': {'base': 2500, 'monthly': 500},
                        'Comércio': {'base': 2000, 'monthly': 400},
                        'Serviços': {'base': 2200, 'monthly': 450},
                        'Imobiliária': {'base': 2800, 'monthly': 600},
                        'Outro': {'base': 2000, 'monthly': 400}
                    },
                    'description': 'Regras de precificação por tipo de negócio'
                }
            ]
            
            # Insere configurações
            for setting in initial_settings:
                try:
                    self.supabase.table('settings').upsert(setting, on_conflict='key').execute()
                except Exception as e:
                    logger.warning(f"Configuração pode já existir: {e}")
            
            # Templates iniciais
            initial_templates = [
                {
                    'name': 'Proposta Padrão - Saúde',
                    'type': 'proposal',
                    'business_type': 'Saúde',
                    'content': '''
                    # Proposta de Automação - {{client_name}}
                    
                    ## Solução Personalizada para Área da Saúde
                    
                    Baseado na nossa conversa, identificamos que você precisa de:
                    - Automatização do atendimento ao paciente
                    - Sistema de agendamento inteligente
                    - Follow-up automático pós-consulta
                    - Gestão financeira integrada
                    
                    **Investimento:**
                    - Taxa de implementação: R$ {{implementation_fee}}
                    - Mensalidade: R$ {{monthly_fee}}
                    
                    **Prazo de implementação:** 15 dias úteis
                    ''',
                    'variables': {
                        'client_name': 'Nome do Cliente',
                        'implementation_fee': 'Taxa de Implementação',
                        'monthly_fee': 'Mensalidade'
                    }
                }
            ]
            
            # Insere templates
            for template in initial_templates:
                try:
                    self.supabase.table('templates').insert(template).execute()
                except Exception as e:
                    logger.warning(f"Template pode já existir: {e}")
            
            logger.info("✅ Dados iniciais inseridos com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inserir dados iniciais: {e}")
            raise
    
    async def create_indexes(self):
        """Cria índices para otimização"""
        try:
            indexes_sql = [
                "CREATE INDEX IF NOT EXISTS idx_conversations_phone ON conversations(phone);",
                "CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);",
                "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);",
                "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);",
                "CREATE INDEX IF NOT EXISTS idx_financial_status ON financial_transactions(status);",
                "CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);"
            ]
            
            for sql in indexes_sql:
                try:
                    self.supabase.rpc('exec_sql', {'sql': sql}).execute()
                except Exception as e:
                    logger.warning(f"Índice pode já existir: {e}")
            
            logger.info("✅ Índices criados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao criar índices: {e}")
            raise
    
    async def setup_rls_policies(self):
        """Configura políticas de segurança RLS"""
        try:
            # Habilita RLS nas tabelas sensíveis
            rls_sql = [
                "ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;",
                "ALTER TABLE leads ENABLE ROW LEVEL SECURITY;",
                "ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;",
                "ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;",
                "ALTER TABLE financial_transactions ENABLE ROW LEVEL SECURITY;"
            ]
            
            for sql in rls_sql:
                try:
                    self.supabase.rpc('exec_sql', {'sql': sql}).execute()
                except Exception as e:
                    logger.warning(f"RLS pode já estar habilitado: {e}")
            
            logger.info("✅ Políticas RLS configuradas")
            
        except Exception as e:
            logger.error(f"Erro ao configurar RLS: {e}")
            raise
    
    async def run_setup(self):
        """Executa setup completo do banco"""
        logger.info("🚀 Iniciando setup do banco de dados...")
        
        await self.create_tables()
        await self.insert_initial_data()
        await self.create_indexes()
        await self.setup_rls_policies()
        
        logger.info("✅ Setup do banco de dados concluído com sucesso!")

async def main():
    """Função principal"""
    try:
        setup = DatabaseSetup()
        await setup.run_setup()
        
    except Exception as e:
        logger.error(f"❌ Erro no setup: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
