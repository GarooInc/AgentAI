import sqlite3
import threading
from contextlib import contextmanager
from functools import lru_cache
import os

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.db_path = self._get_db_path()
            self._local = threading.local()
            self._initialized = True
    
    def _get_db_path(self):
        from helper import get_db
        return get_db()
    
    def _get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_connection(self):
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            # No cerramos la conexión, la reutilizamos
            pass
    
    def execute_query(self, query: str):
        """Ejecuta consulta SQL optimizada con manejo de errores"""
        print(f"\n[DEBUG] - Consulta SQL: {query}")
        
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query)
                
                if query.strip().lower().startswith("select"):
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    conn.commit()
                    return [{"mensaje": f"Consulta ejecutada. Filas afectadas: {cursor.rowcount}"}]
                    
            except Exception as e:
                return [{"error": f"Error al ejecutar la consulta: {str(e)}"}]

# Singleton instance
db_manager = DatabaseManager()