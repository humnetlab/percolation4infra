# Percolation-informed infrastructure upgrades

Urban congestion increases travel delay, fuel use, and vehicle emissions. A common response is to replace fixed-time traffic signals with detector-based actuated control, but upgrading an entire signal network is expensive. This project asks a practical planning question: **which intersections should be upgraded first to obtain the largest congestion and emission reductions per dollar?**

We address this question using traffic percolation. During the morning peak, congestion does not spread uniformly across the road network. Instead, scattered congested road sections rapidly merge into a large connected cluster. This transition reveals a small set of structurally important intersections that help connect otherwise separated congested clusters. We identify these intersections with a fragmentation-index criterion and evaluate whether upgrading them from fixed-time to actuated signal control outperforms random upgrades.

The workflow is summarized in below.

![Percolation-informed infrastructure upgrade workflow](fig0_panel.pdf)

In brief, the project:

1. Detects the percolation transition in a simulated urban road network.
2. Builds a dual graph representation of road sections and congestion clusters.
3. Identifies critical intersections whose removal fragments the emerging congested cluster.
4. Compares fixed-time control, random upgrades, critical-intersection upgrades, and full actuation.
5. Quantifies the traffic, emission, and investment benefits of targeted upgrades.

## Repository structure

```text
percolation4infra/
├── fig0_panel.pdf
├── data/
│   └── processed/
│       ├── Actuated_network.parquet
│       ├── bottleneck.parquet
│       ├── Critical_0.1_network.parquet
│       ├── Critical_0.5_network.parquet
│       ├── Critical_1_network.parquet
│       ├── Fix_critical_scaling.parquet
│       ├── Fix_critical_summary.parquet
│       ├── Fix_critical_vector.parquet
│       ├── Fix_network.parquet
│       ├── Random_0.1_network.parquet
│       ├── Random_0.5_network.parquet
│       └── Random_1_network.parquet
└── notebooks/
    ├── fig0.ipynb
    ├── fig1.ipynb
    ├── fig2.ipynb
    ├── fig3.ipynb
    ├── fig4.ipynb
    ├── fig5.ipynb
    ├── process.ipynb
    ├── spinfo.ipynb
    └── utils.py
```

## Data

The processed files in `data/processed/` contain network-level simulation outputs and critical-intersection results.

Control strategies are encoded as:

- `Fix`: fixed-time signal control.
- `Random_*`: randomly selected intersection upgrades.
- `Critical_*`: percolation-informed critical-intersection upgrades.
- `Actuated`: fully actuated signal control.

The suffixes correspond to upgrade levels used in the analysis:

- `0.1`: 10% upgrade coverage.
- `0.5`: 30% upgrade coverage.
- `1`: 50% upgrade coverage.

## Notebooks

- `process.ipynb`: processes simulation outputs and builds analysis tables.
- `fig0.ipynb`: conceptual schematic of the percolation and critical-intersection workflow.
- `fig1.ipynb`: congestion formation and the percolation transition.
- `fig2.ipynb`: identification of critical intersections.
- `fig3.ipynb`: comparison between random and percolation-informed upgrades.
- `fig4.ipynb`: main composite figure for traffic dynamics, emissions, and spatial effects.
- `fig5.ipynb`: investment analysis and diminishing returns.
- `spinfo.ipynb`: supplementary performance information.
- `utils.py`: shared helper functions used by the notebooks.

## Environment

The notebooks use standard scientific Python packages. A minimal environment can be created with:

```bash
conda create -n percolation4infra python=3.11
conda activate percolation4infra
conda install -c conda-forge numpy pandas matplotlib pyarrow jupyter
```

Some notebooks may also use geospatial or network-analysis packages:

```bash
conda install -c conda-forge geopandas shapely networkx contextily
```
