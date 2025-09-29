FROM mcr.microsoft.com/devcontainers/python:3.11@sha256:407616a78a9ec3bfbf736feedaf91d6c94e8cd0d2b90663da019c536e67e4ec4

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
