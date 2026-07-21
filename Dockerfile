ARG BASE_IMAGE=boltz:221
ARG NODE_IMAGE=node:20-bullseye-slim

FROM ${NODE_IMAGE} AS node_runtime

WORKDIR /node-app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="BoltzUI 2.2.1 atom contacts and structure post-processing"
LABEL org.opencontainers.image.description="BoltzUI with atom-contact guidance, neutral-pH hydrogen placement, and Amber14/GBn2 minimization"

ENV BOLTZ_CACHE=/opt/boltz-cache \
    OPENMM_CPU_THREADS=4 \
    OPENMM_PLUGIN_DIR=/usr/local/lib/python3.10/site-packages/OpenMM.libs/lib/plugins \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5173

WORKDIR /workspace/BoltzUI

COPY requirements-postprocess.txt ./
RUN pip install --no-cache-dir -r requirements-postprocess.txt

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /node-app/node_modules ./node_modules
COPY server.js package.json package-lock.json ./
COPY lib ./lib
COPY public ./public
COPY patches ./patches
COPY scripts ./scripts
COPY fixtures ./fixtures
COPY tests ./tests
COPY README.md REQUIREMENTS.md DOCKER_HUB.md ./

RUN set -eux; \
    chmod +x scripts/boltzui_predict.py; \
    ln -s /workspace/BoltzUI/scripts/boltzui_predict.py /usr/local/bin/boltzui-predict; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py --check; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py; \
    node scripts/sync-docs.js --check; \
    node --test tests/*.test.js; \
    python -m unittest tests/test_boltz_patch.py tests/test_boltzui_predict.py tests/test_structure_postprocess.py; \
    python -c "import openmm, pdbfixer; print('OpenMM', openmm.__version__, 'PDBFixer', getattr(pdbfixer, '__version__', 'unknown'))"; \
    boltzui-predict --help >/dev/null; \
    boltz --help >/dev/null; \
    node --version; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache path:', cache, 'exists=', cache.exists())"

EXPOSE 5173

ENTRYPOINT ["node"]
CMD ["server.js"]
