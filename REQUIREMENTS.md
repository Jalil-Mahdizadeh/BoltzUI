# Requirements

## Host system

- Docker Desktop with Linux containers enabled.
- NVIDIA GPU support in Docker.
- Recent NVIDIA driver compatible with CUDA 12.8 or newer.
- At least 32 GB system RAM recommended.
- At least 45 GB free disk space for the final cached image and Docker build layers.

OpenMM 8.4.0, its pinned CUDA 12 plugin, PDBFixer 1.12.0, and all Amber XML force-field files are installed directly in `boltzui:221-exact-union`. The post-processor prefers CUDA but automatically uses OpenCL or a four-thread CPU platform when CUDA is unavailable. Energy minimization does not run concurrently with Boltz prediction.

## GPU memory

Boltz 2.2.1 can fill an 8 GB GPU on larger or more aggressive runs. This image patches `max_parallel_samples` to be a true denoiser chunk-size limit; keep it at `1` on small laptop GPUs. The minimal fix still retains diffusion state for all requested samples, so increasing `diffusion_samples` can still increase peak VRAM even when denoiser calls are serial.

`run.sh` only launches the container. Prediction parameters are selected in the dashboard and are not supplied by the launcher.

## Prediction presets

<!-- BEGIN GENERATED PREDICTION PRESETS -->
| Preset | Sampling steps | Step scale | Potentials | Status |
|---|---:|---:|---|---|
| Standard Boltz-2 | 200 | 1.5 | Off | Standard |
| Atom-contact exploration | 400 | 1.0 | On | Experimental |

The atom-contact exploration preset is experimental. Its lower step scale changes the reverse-diffusion update and sample diversity and may interact with inference-time potential guidance; it is not a mathematical guarantee of restraint satisfaction.
<!-- END GENERATED PREDICTION PRESETS -->

On the tested NVIDIA RTX PRO 2000 Blackwell laptop GPU with 8151 MiB VRAM, the largest confirmed successful minimal GPU test was a synthetic 700 amino-acid single-chain input with `msa: empty`, `diffusion_samples=1`, `recycling_steps=1`, `sampling_steps=5`, and `max_parallel_samples=1`. Lengths of 750 amino acids and above failed with a CUDA driver `device not ready` error under the same test settings. Treat this as a laptop-specific safety boundary, not a general Boltz limit.

For the real 495-residue `NusA_open.yaml` input, single-sequence GPU prediction succeeded, but enabling the full local MSA with Boltz's default `max_msa_seqs=8192` failed in the MSA module with CUDA driver `device not ready`. The same input succeeded in a minimal MSA test when MSA use was capped with:

```bash
--max_msa_seqs 5120
--num_subsampled_msa 5120
--max_parallel_samples 1
```

## Build input

The Docker build expects the existing local workflow image `boltzui:221-exact-union` and upgrades that same tag after a successful build. It verifies Boltz 2.2.1 and the existing exact/union patch markers before applying the interface-contact upgrade. Model and molecule caches are inherited from the base image.
