FROM mcr.microsoft.com/devcontainers/python:3.13@sha256:c5c4c77e2919476f2e25998c4d9f73f489f3834197778132975f31a991623746

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
