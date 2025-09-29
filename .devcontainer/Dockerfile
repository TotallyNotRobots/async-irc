FROM mcr.microsoft.com/devcontainers/python:3.12@sha256:b50c5ea95641cfe6514afc0706e80d671f52e560978765bd9015beb824fecc20

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
