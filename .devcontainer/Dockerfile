FROM mcr.microsoft.com/devcontainers/python:3.13@sha256:b4b3a3f0cf67b787061d77bc4b76cdd37f78cc6829050ed3f7dcb7269a99beb5

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
