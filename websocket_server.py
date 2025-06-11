21-websocket_server.py

# websocket_server.py
import asyncio
import logging
import os
from websocket_manager import dashboard_manager, start_websocket_server

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Função principal do servidor WebSocket"""
    try:
        # Configurações do servidor
        host = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
        port = int(os.getenv("WEBSOCKET_PORT", "8765"))
        
        logger.info(f"Iniciando servidor WebSocket em {host}:{port}")
        
        # Inicia as tarefas em background
        await dashboard_manager.start_background_tasks()
        
        # Inicia o servidor WebSocket
        server = await start_websocket_server(host, port)
        
        logger.info("Servidor WebSocket iniciado com sucesso!")
        logger.info("Aguardando conexões...")
        
        # Mantém o servidor rodando
        await server.wait_closed()
        
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor WebSocket: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Servidor WebSocket interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        exit(1)