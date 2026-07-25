# syntax=docker/dockerfile:1

ARG BASE_IMAGE=boltz:221
ARG NODE_IMAGE=node:20-bullseye-slim

FROM ${NODE_IMAGE} AS node_runtime

WORKDIR /node-app
COPY package.json package-lock.json ./
RUN set -eux; \
    npm ci --omit=dev; \
    mkdir -p /node-bundle/usr/local/bin /node-bundle/workspace/BoltzUI; \
    cp /usr/local/bin/node /node-bundle/usr/local/bin/node; \
    cp -a /node-app/node_modules /node-bundle/workspace/BoltzUI/node_modules

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="BoltzUI 2.2.1 stable interface and atom contacts"
LABEL org.opencontainers.image.description="BoltzUI with exact-OR atom contacts, reciprocal literal-heavy-atom CSP interface guidance, clash protection, and structure post-processing"

ENV BOLTZ_CACHE=/opt/boltz-cache \
    OPENMM_CPU_THREADS=4 \
    OPENMM_PLUGIN_DIR=/usr/local/lib/python3.10/site-packages/OpenMM.libs/lib/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5173

WORKDIR /workspace/BoltzUI

RUN --mount=type=bind,from=node_runtime,source=/node-bundle,target=/tmp/node-bundle,ro \
    --mount=type=bind,source=.,target=/tmp/boltzui-source,ro \
    set -eux; \
    cp -a /tmp/node-bundle/. /; \
    cp -a /tmp/boltzui-source/. /workspace/BoltzUI/; \
    pip install --no-cache-dir -r requirements-postprocess.txt; \
    chmod +x scripts/boltzui_predict.py; \
    ln -sfn /workspace/BoltzUI/scripts/boltzui_predict.py /usr/local/bin/boltzui-predict; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py --check; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py --verify-applied; \
    node scripts/sync-docs.js --check; \
    node --test tests/*.test.js; \
    python -m unittest tests/test_boltz_patch.py tests/test_boltzui_predict.py tests/test_structure_postprocess.py; \
    python -c "import openmm, pdbfixer; print('OpenMM', openmm.__version__, 'PDBFixer', getattr(pdbfixer, '__version__', 'unknown'))"; \
    boltzui-predict --help >/dev/null; \
    boltz --help >/dev/null; \
    node --version; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache path:', cache, 'exists=', cache.exists())"; \
    find /workspace/BoltzUI -type f -name '*.pyc' -delete; \
    find /workspace/BoltzUI -type d -name '__pycache__' -empty -delete

EXPOSE 5173

ENTRYPOINT ["node"]
CMD ["server.js"]
