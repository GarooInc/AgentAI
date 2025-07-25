import os
from typing import Dict, Any

class ProductionConfig:
    """Configuración optimizada para producción"""
    
    # Configuración de uvicorn para Windows
    UVICORN_CONFIG = {
        "host": "0.0.0.0",
        "port": int(os.getenv("PORT", 8000)),
        "workers": 1,  # Windows no soporta múltiples workers bien
        "access_log": False,  # Desactivar logs de acceso para mejor rendimiento
        "log_level": "warning"
    }
    
    # Configuración de OpenAI
    OPENAI_CONFIG = {
        "max_retries": 3,
        "timeout": 30.0,
        "max_tokens": 2000
    }
    
    # Configuración de cache
    CACHE_CONFIG = {
        "knowledge_cache_size": 64,
        "query_cache_ttl": 300  # 5 minutos
    }
    
    # Configuración de base de datos
    DATABASE_CONFIG = {
        "connection_timeout": 30.0,
        "max_connections_per_thread": 1
    }

def get_production_config() -> Dict[str, Any]:
    return {
        "uvicorn": ProductionConfig.UVICORN_CONFIG,
        "openai": ProductionConfig.OPENAI_CONFIG,
        "cache": ProductionConfig.CACHE_CONFIG,
        "database": ProductionConfig.DATABASE_CONFIG
    }