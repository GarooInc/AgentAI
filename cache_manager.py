from functools import lru_cache
import os
from typing import Dict, Any

class KnowledgeCache:
    _cache: Dict[str, str] = {}
    _file_timestamps: Dict[str, float] = {}
    
    @classmethod
    def get_content(cls, filename: str) -> str:
        """Obtiene contenido con cache inteligente basado en timestamp"""
        try:
            current_mtime = os.path.getmtime(filename)
            
            # Si el archivo cambió o no está en cache, recargarlo
            if (filename not in cls._cache or 
                filename not in cls._file_timestamps or 
                cls._file_timestamps[filename] != current_mtime):
                
                with open(filename, "r", encoding="utf-8") as f:
                    cls._cache[filename] = f.read()
                cls._file_timestamps[filename] = current_mtime
                print(f"[CACHE] Recargado: {filename}")
            
            return cls._cache[filename]
            
        except FileNotFoundError:
            return f"No se pudo cargar {filename}"

# Cache global
knowledge_cache = KnowledgeCache()

@lru_cache(maxsize=32)
def get_cached_knowledge():
    """Cache para datos que no cambian frecuentemente"""
    return {
        'reservations_columns': knowledge_cache.get_content("knowledge/reservations_columns.md"),
        'wholesalers_list': knowledge_cache.get_content("knowledge/wholesalers.txt"),
        'itzana_knowledge': knowledge_cache.get_content("knowledge/itzana_context.md")
    }