FROM mcr.microsoft.com/devcontainers/python:3.14@sha256:43311767f101e1c2a7bd0ecacf2c866f5c42124fc2efe45bb384eb2995ecce4d

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black

RUN pipx install commitizen \
    && pipx install hatch

RUN umask 0002 \
    && mkdir -p ${PIPX_BIN_DIR} \
    && chown -R "vscode:pipx" ${PIPX_HOME} \
    && chmod -R g+r+w "${PIPX_HOME}"

RUN su vscode -c "hatch config set dirs.env.virtual /home/vscode/.virtualenvs"

ENV SHELL=/bin/bash
