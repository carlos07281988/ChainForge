"""ChainForge Evolution — advanced agent optimization capabilities.

Modules:
  - dream: Dream/Simulation mode for predicting tool outcomes
  - tech_tree: Technology tree for unlocking agent capabilities
  - population: Multi-generational evolution for optimal configs
"""

from chainforge.evolution.dream import DreamConfig, DreamMode, DreamPrediction
from chainforge.evolution.tech_tree import TechTree, TechNode, default_tech_tree
from chainforge.evolution.population import AgentPopulation, Individual, IndividualGenome

__all__ = [
    "DreamConfig", "DreamMode", "DreamPrediction",
    "TechTree", "TechNode", "default_tech_tree",
    "AgentPopulation", "Individual", "IndividualGenome",
]
