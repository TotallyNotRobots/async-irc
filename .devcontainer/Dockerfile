FROM mcr.microsoft.com/devcontainers/python:3.14@sha256:43311767f101e1c2a7bd0ecacf2c866f5c42124fc2efe45bb384eb2995ecce4d

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
