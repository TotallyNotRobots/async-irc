FROM mcr.microsoft.com/devcontainers/python:3.10@sha256:3bfb22a8819549cab28ebbc7748ac379ce327d79ff22ea024435750613971153

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
