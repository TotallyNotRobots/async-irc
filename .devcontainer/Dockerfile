FROM mcr.microsoft.com/devcontainers/python:3.9@sha256:e97d57202b36aa119090479a1a491f88e42e9a05a60ca3f12f7285a76105d971

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
