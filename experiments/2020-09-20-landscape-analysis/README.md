# 2020-09-20 Landscape Analysis

Our expectations for all these experiments hinge on the hypothesis that, despite the fluctuating environment, the local fitness landscape of plastic organisms remains stable. 

Details

- Experimental design: two phase (Same as 09/03 experiment)
    - First phase runs for 200k updates for all configurations
    - If sensors are not present, automatically run phase 2 for 200k additional updates
    - If sensirs _are_ present, only run the extra 200k updates if perfect plasticity evolved in the first phase 
    - Perfect plasticity = Responding to all rewarded tasks and no punished tasks regardless of which environmen is active
- Environmental change rates: u0 (constant), u3, u10, u30, u100, u300, u1000
- Sensors: sensors+, sensors-
- Questions/analyses
  - Does evolved plasticity place organisms in a stable portion of the fitness landscape?
- Axes of comparison
  - Once the runs complete, we generate all organsism that are one substitution mutation away from the final dominant organism. 
  - These mutants are evaluated in both the environments (A and B)
  - We then calculate the fitness effect of each mutation in each environment
  - Our expectation is that mutants generated from non-plastic organsisms will have more drastic fitness changes between the two environments (moving from A-> B) than plastic organisms
- Number of replicates: 50

Some concerns

- Not all one-step mutants are caused by substitutions, and we should eventually check the other mutational operators too.  
