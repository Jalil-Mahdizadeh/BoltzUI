# Requirements

## Host system

- Docker Desktop with Linux containers enabled.
- NVIDIA GPU support in Docker.
- Recent NVIDIA driver compatible with CUDA 12.8 or newer.
- At least 32 GB system RAM recommended.
- At least 45 GB free disk space for the final cached image and Docker build layers.

## GPU memory

Boltz 2.2.1 can fill an 8 GB GPU on larger or more aggressive runs. Keep `--max_parallel_samples 1` on small laptop GPUs. Increase `--diffusion_samples` for more samples, but keep them serial unless you have much more VRAM.

The included `run.sh` uses:

```bash
--diffusion_samples 20
--recycling_steps 10
--max_parallel_samples 1
```

For a safer first run on an 8 GB GPU, edit `run.sh` manually:

```bash
--diffusion_samples 1
--recycling_steps 3
--max_parallel_samples 1
```

## Build input

The Docker build expects a local `.boltz/` folder next to the Dockerfile. It must contain:

```text
.boltz/
  boltz2_aff.ckpt
  boltz2_conf.ckpt
  mols.tar
  mols/
```

The `.boltz/` folder is intentionally ignored by Git because it is several gigabytes.
