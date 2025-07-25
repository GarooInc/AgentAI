#!/usr/bin/env python3
"""
Script optimizado para iniciar el servidor en producción (Windows)
"""
import uvicorn
import os

def main():
    port = int(os.getenv("PORT", 8000))
    
    print("🚀 Iniciando Itzana Agents API en modo producción...")
    print(f"Puerto: {port}")
    print("Sistema: Windows (single worker)")
    
    # Configuración optimizada para Windows
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        workers=1,  # Windows funciona mejor con 1 worker
        access_log=False,  # Mejor rendimiento
        log_level="info",
        reload=False  # Desactivar reload en producción
    )

if __name__ == "__main__":
    main()