"""example/27_population.py — Population Evolution verification."""
import sys
from chainforge.evolution.population import AgentPopulation, IndividualGenome
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

pop = AgentPopulation(); pop.initialize(size=8)
c("init 8", len(pop.individuals) == 8)
for i, ind in enumerate(pop.individuals): ind.fitness = i / 10.0
sel = pop._tournament_select()
c("tournament", sel.fitness > 0)

g1 = IndividualGenome(temperature=0.3, max_iterations=10, reasoning_enabled=True)
g2 = IndividualGenome(temperature=0.7, max_iterations=20, reasoning_enabled=False)
child = pop._crossover(g1, g2)
c("crossover", child.max_iterations in (10, 20))

pop._mutate(child, rate=1.0)
c("mutation safe", isinstance(child.temperature, float))

pop.evolve([(i, 1.0 - i*0.05) for i in range(8)])
c("gen advanced", pop.generation >= 1)
c("pop size", len(pop.individuals) == 8)
c("best", pop.best_individual is not None)
c("avg fit", pop.avg_fitness > 0)
c("summary", "Generation" in pop.summary())
print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
