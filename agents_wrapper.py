# agents.py - Re-exportar clases de agents (openai-agents)
from agents import Agent, function_tool, AgentOutputSchema, Runner

# Re-exportar para compatibilidad
__all__ = ['Agent', 'function_tool', 'AgentOutputSchema', 'Runner']