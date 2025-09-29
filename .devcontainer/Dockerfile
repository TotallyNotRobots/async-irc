FROM mcr.microsoft.com/devcontainers/python:3.8@sha256:13822a0e211e5b99816ce3f44f064ee385f7679eb407f901f19ed5328ad557d0

RUN \
    pipx uninstall mypy \
    && pipx uninstall pylint \
    && pipx uninstall pytest \
    && pipx uninstall flake8 \
    && pipx uninstall black \
    && pipx install commitizen \
    && pip install -U hatch hatch-containers

ENV SHELL=/bin/bash
