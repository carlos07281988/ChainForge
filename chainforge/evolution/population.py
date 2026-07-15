# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Multi-Generational Agent Evolution."""
from __future__ import annotations

import copy, math, random, time
from typing import Any
from pydantic import BaseModel, Field

class IndividualGenome(BaseModel):
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_iterations: int = Field(default=10, ge=1, le=50)
    system_prompt_keywords: list[str] = Field(default_factory=list)
    tool_list: list[str] = Field(default_factory=list)
    reasoning_enabled: bool = Field(default=False)
    parallel_tool_calls: bool = Field(default=True)
    mutation_id: str = Field(default="")

class Individual(BaseModel):
    genome: IndividualGenome = Field(default_factory=IndividualGenome)
    fitness: float = Field(default=0.0)
    generation: int = Field(default=0)
    eval_count: int = Field(default=0)
    success_count: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    avg_latency: float = Field(default=0.0)

class AgentPopulation(BaseModel):
    individuals: list[Individual] = Field(default_factory=list)
    generation: int = Field(default=0)
    mutation_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    crossover_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    elite_count: int = Field(default=2)
    tournament_size: int = Field(default=3)

    def initialize(self, base_config: dict | None = None, size: int = 10) -> None:
        self.individuals = []
        base = IndividualGenome(**(base_config or {}))
        for i in range(size):
            genome = copy.deepcopy(base)
            if i > 0:
                self._mutate(genome, rate=0.3)
                genome.mutation_id = f"init_{i}"
            self.individuals.append(Individual(genome=genome, generation=0))

    def evolve(self, fitness_scores: list[tuple[int, float]]) -> None:
        if not self.individuals:
            return
        for idx, score in fitness_scores:
            if 0 <= idx < len(self.individuals):
                self.individuals[idx].fitness = score
        self.individuals.sort(key=lambda ind: ind.fitness, reverse=True)
        next_gen: list[Individual] = []
        elites = self.individuals[:self.elite_count]
        for ind in elites:
            next_gen.append(copy.deepcopy(ind))
        while len(next_gen) < len(self.individuals):
            if random.random() < self.crossover_rate and len(self.individuals) >= 2:
                p1 = self._tournament_select()
                p2 = self._tournament_select()
                child_genome = self._crossover(p1.genome, p2.genome)
            else:
                parent = self._tournament_select()
                child_genome = copy.deepcopy(parent.genome)
            self._mutate(child_genome)
            child = Individual(genome=child_genome, generation=self.generation + 1)
            next_gen.append(child)
        self.individuals = next_gen[:len(self.individuals)]
        self.generation += 1

    @property
    def best_individual(self) -> Individual | None:
        if not self.individuals:
            return None
        return max(self.individuals, key=lambda ind: ind.fitness)

    @property
    def avg_fitness(self) -> float:
        if not self.individuals:
            return 0.0
        return sum(ind.fitness for ind in self.individuals) / len(self.individuals)

    def fitness_history(self) -> list[dict]:
        history = {}
        for ind in self.individuals:
            gen = ind.generation
            if gen not in history:
                history[gen] = []
            if ind.fitness > 0:
                history[gen].append(ind.fitness)
        result = [{"generation": gen, "avg_fitness": sum(s)/len(s) if s else 0,
                    "max_fitness": max(s) if s else 0, "count": len(s)}
                   for gen, s in sorted(history.items())]
        return result

    def summary(self) -> str:
        best = self.best_individual
        parts = [f"Generation: {self.generation}", f"Population: {len(self.individuals)}",
                 f"Avg fitness: {self.avg_fitness:.3f}"]
        if best:
            parts.append(f"Best fitness: {best.fitness:.3f}")
            parts.append(f"Best config: temp={best.genome.temperature:.2f}, "
                         f"iterations={best.genome.max_iterations}, "
                         f"reasoning={best.genome.reasoning_enabled}")
        return "\n".join(parts)

    def _tournament_select(self) -> Individual:
        pool = random.sample(self.individuals, min(self.tournament_size, len(self.individuals)))
        return max(pool, key=lambda ind: ind.fitness)

    def _crossover(self, g1: IndividualGenome, g2: IndividualGenome) -> IndividualGenome:
        child = IndividualGenome()
        child.temperature = (g1.temperature + g2.temperature) / 2
        child.max_iterations = random.choice([g1.max_iterations, g2.max_iterations])
        child.reasoning_enabled = random.choice([g1.reasoning_enabled, g2.reasoning_enabled])
        child.parallel_tool_calls = random.choice([g1.parallel_tool_calls, g2.parallel_tool_calls])
        kw = list(set(g1.system_prompt_keywords + g2.system_prompt_keywords))
        random.shuffle(kw)
        child.system_prompt_keywords = kw[:max(len(kw) // 2, 1)]
        child.mutation_id = f"crossover_g{self.generation + 1}"
        return child

    def _mutate(self, genome: IndividualGenome, rate: float | None = None) -> None:
        r = rate if rate is not None else self.mutation_rate
        if random.random() < r:
            genome.temperature = max(0, min(2.0, genome.temperature + random.gauss(0, 0.1)))
        if random.random() < r:
            genome.max_iterations = max(1, min(50, genome.max_iterations + random.randint(-3, 3)))
        if random.random() < r:
            genome.reasoning_enabled = not genome.reasoning_enabled
        if random.random() < r:
            genome.parallel_tool_calls = not genome.parallel_tool_calls
        if random.random() < r and genome.system_prompt_keywords:
            idx = random.randint(0, len(genome.system_prompt_keywords) - 1)
            genome.system_prompt_keywords[idx] = random.choice([
                "careful", "fast", "thorough", "simple", "expert", "beginner-friendly"
            ])
        genome.mutation_id = f"mutated_g{self.generation + 1}"

__all__ = ["AgentPopulation", "Individual", "IndividualGenome"]
