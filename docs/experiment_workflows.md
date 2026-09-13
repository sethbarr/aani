# Diverse-fungus validation and laboratory handoffs

Build a prospective validation step after candidate discovery: select source-linked
materials, propose a diverse fungal panel, specify what each experiment would
resolve, and prepare the work for a robot or participating laboratory.

For the hackathon, the working deliverable is an offline planner, a structured
study bundle, local handoff drafts for Potato and Emerald, and a water-only
Opentrons protocol. Biological parameters and sample availability remain open.
No biological experiment, lab submission, purchase or message has been made.

## Why a diverse panel

The central question is whether activity suggested by the ant system extends
across fungal lineages and growth forms. Keep the ecological reference while
adding independent comparisons:

| Proposed member | Purpose | Sample route |
|---|---|---|
| Identified ant cultivar | Test the organism implicated by ant substrate selection | Gerardo lab connection; current stocks unconfirmed |
| *Saccharomyces cerevisiae* | Budding-yeast comparison | Identified laboratory or collection strain |
| *Schizosaccharomyces pombe* | Evolutionarily distinct fission-yeast comparison | Laboratory or collection strain; [PomBase](https://www.pombase.org/) is a community reference |
| *Neurospora crassa* | Filamentous ascomycete comparison | [Fungal Genetics Stock Center](https://www.fgsc.net/) is a sourcing lead |
| *Pleurotus ostreatus* | Free-living mushroom-forming basidiomycete comparison | [ATCC 90076](https://www.atcc.org/products/90076) is a catalog example, not a reserved sample |

This is a proposed five-member panel, not a representative sample of the fungal
kingdom. One strain per species cannot establish species-wide susceptibility.
Keep donor-colony identity for cultivar isolates. Later confirmation should
include additional independent isolates as well as repeated runs.

The configuration also lists *Candida albicans*, *Cryptococcus neoformans*, and
*Aspergillus fumigatus* as a separate clinical-relevance expansion for a suitable
specialist laboratory. They are not selected by default. Activity in the model
panel cannot substitute for testing the actual translational targets.

## Cultivar access through Nicole Gerardo

The user identified their postdoctoral connection to Nicole Gerardo as a possible
route. Her [current Emory profile](https://biology.emory.edu/people/bios/faculty/gerardo-nicole.html)
includes fungus-growing ants and associated fungi. That supports approaching the
lab; it does not confirm its current collection or willingness to share.

The first inquiry should ask whether an **identified cultivar isolate** and an
existing assay reference are available, whether the lab would prefer to perform
the cultivar arm, or whether it can refer us to another collaborator. Request
host-ant identity, donor colony and origin, identification evidence, culture
history, and any applicable transfer arrangements. If several independent colony
isolates are available, retain their identities rather than pooling them.

An intact fungus garden would be useful for a later ecological validation arm,
but it is a mixed community with substrate and associated organisms. Do not
interpret a change in that community as a pure-cultivar susceptibility result.
The generated `gerardo_brief.md` is a draft for the user to review; it is not sent.

## Where Potato fits

Potato is a **possible planning partner**, not a confirmed remote lab provider.
Its [product page](https://www.potato.ai/products/) describes literature and
experimental-design tools and advertises early access for assay optimization.
Its [technology page](https://www.potato.ai/technology/) describes structured
protocol planning, quantitative checks, and simulation capabilities. These are
vendor descriptions, not a test of its performance on our assays.

The proposed handoff includes source-linked candidates, the biological question,
organism-specific method gaps, a planning matrix, control requirements and
readout constraints. Ask Potato to help refine the design and protocol drafts.
Verify available account features, supported imports/API, Opentrons export,
remote-lab interoperability and pilot terms before building a direct adapter.
No public API contract or Potato–Emerald integration has been verified.

For the hackathon, download a local `potato_brief.md` alongside the structured
bundle. This keeps the demonstration useful even without partner credentials.
It does not claim that Potato can directly import our JSON schema.

## Remote execution with Emerald or a specialist laboratory

[Emerald's public workflow](https://www.emeraldcloudlab.com/how-it-works/)
describes sample shipment, remotely specified experiments, and returned data.
Its [function documentation](https://www.emeraldcloudlab.com/documentation/functions/)
uses Symbolic Lab Language. Treat this as a distinct execution backend; an
Opentrons file is not evidence of compatibility.

Before submission, the provider needs to confirm strain and material acceptance,
method support for each fungus, suitable instruments, sample specifications,
account access, quote and turnaround. The specialty cultivar arm may be better
run by a collaborating ant laboratory, with the rest of the panel handled
elsewhere. Preserve assay versions and laboratory identities when joining results.

The generated `emerald_brief.md` asks for that feasibility assessment. Pricing
and turnaround remain unknown. Physical execution should follow a reviewed
provider method, not an inferred conversion of a historical paper's conditions.

## What is implemented

```text
source assay records + experiment_panel.json
                    ↓
          prospective study plan
                    ↓
       matrix + illustrative plate layouts
                    ↓
   Potato brief / remote lab brief / cultivar inquiry
                    ↓
      OT-2 water-only placement demonstration
```

Generate the default bundle from the repository root:

```bash
.venv/bin/python -m scripts.plan_experiments
```

Open `results/experiment_planner/index.html`. It is self-contained, works offline,
and provides interactive study, fungal-panel, plate, and partner views. The
existing research evidence browser links to this generated planner.

The defaults select dillapiole (`F003`), caryophyllene epoxide (`F008`), and
kolavenol (`F010`). The last is a source-reported cultivar-null comparator;
that historical null is not extrapolated to the new panel. These are illustrative
materials with source-backed records, not a cross-study potency ranking or
confirmed procurement list. One representative endpoint per material prevents
multiple measurements of one compound from being counted as new candidates.

The study is an activity-profile pilot. To test the predictive value of ant
avoidance prospectively, add a matched accepted-plant arm and prespecify how
materials enter it; neither a source-null compound nor an assay control provides
that comparison by itself.

Change selections by record and fungus IDs without changing the frozen analysis:

```bash
.venv/bin/python -m scripts.plan_experiments \
  --records F003 F008 F010 \
  --fungi attine_cultivar s_cerevisiae s_pombe n_crassa p_ostreatus \
  --output results/experiment_planner
```

The generated plan has a deterministic identity tied to the selected source
snapshots, design, and configuration. Source values stay under `evidence`;
future measurements are blank. The planning CSV is a material–fungus matrix,
not a raw-result import interface. A future result importer must retain actual
well, run, isolate, exposure, method, raw-data URI, QC and measurement provenance.

## Layout and scientific limits

The default illustration uses four unnamed dose slots, three technical wells per
condition, and two planned independent runs. For each material and dose it
reserves treatment wells and matched material-only blanks for readout interference.
Every plate also reserves vehicle/growth, medium-blank, and reference-antifungal
controls. Control identities and suitable solvents remain unresolved; additional
solvent-specific controls may change the layout.

That is 81 occupied wells per fungus/run: 36 treatment, 36 material-only blank,
and 9 common control wells. Five fungi across two runs therefore illustrate ten
plates and 810 occupied wells. Larger candidate panels split across plates with
controls preserved. Seeded placement makes the illustration reproducible; it
does not settle assay-specific edge effects, blocking, or suitability of a
96-well format. Larger dose/replicate groups that cannot fit are rejected.

Actual organism protocols may use different formats and schedules. The plan
leaves strain IDs, doses/units, solvents, media, incubation, readouts, labware,
instrument configuration and lab acceptance unassigned. Do not automate these
steps until the missing experimental specifications have been resolved.

Normalize within each validated assay against its own controls. Keep MIC, IC50,
growth area and damage incidence distinct. Report activity conditional on the
tested isolate, exposure, time and method; do not label untested cells inactive.
Any claim of breadth must include the tested denominator and assay QC. Technical
wells do not increase the count of independent isolates or independent runs.
Growth inhibition alone does not establish fungal killing or clinical utility.

## Robot demonstration

`opentrons_water_demo.py` uses the [Opentrons Python API](https://docs.opentrons.com/python-api/tutorial/)
for an OT-2 with a P300 single GEN2, 300 µL tip rack in slot 1, a NEST 12-channel
15 mL reservoir in slot 2 and NEST 96-well 200 µL flat plate in slot 3. It places
50 µL water into each occupied well of the first illustrative plate, using fresh
tips. Reservoir A1 is labelled for 6 mL water, leaving excess beyond the maximum
4.8 mL transferred to 96 wells. These values describe the water demonstration
only; they are not fungal-assay volumes.

The protocol pauses for the physical deck setup. It does not move or culture
fungi, dispense compounds, perform dilution series, incubate, or read plates.
Its simulation is a test of liquid-handling code and layout capacity, not of
biological feasibility or physical calibration. Simulation status and a hash of
the generated protocol are stored separately in `simulation_report.json`.
Regenerating a bundle resets that report so an old success cannot carry forward.

Use a separate Python 3.12 environment for Opentrons because the repository uses
NumPy 2 while the simulator package currently requires NumPy below 2:

```bash
python3.12 -m venv /tmp/fungal-opentrons-venv
/tmp/fungal-opentrons-venv/bin/python -m pip install opentrons==8.8.2
/tmp/fungal-opentrons-venv/bin/python -m scripts.simulate_experiment_demo
```

The exported default protocol was verified with Opentrons 8.8.2: 81 simulated
dispenses and 409 logged commands, with no robot connected. Use this pinned
version for the OT-2 demonstration; the 9.1.2 simulator directs OT-2 protocols
to the separate [OT-2 software release](https://github.com/Opentrons/opentrons-ot2).

The next implementation step after partner feedback is an adapter for a reviewed
biological method and a validated result importer. Keep the prospective plan and
measurements separate from `config/analysis.json` and the frozen retrospective
analysis protocol.
