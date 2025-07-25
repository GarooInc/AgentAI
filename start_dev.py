#!/usr/bin/env python3
"""
Script para desarrollo con optimizaciones básicas
"""
import uvicorn

def main():
    print("🔧 Iniciando Itzana Agents API en modo desarrollo...")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload para desarrollo
        log_level="info"
    )

if __name__ == "__main__":
    main()