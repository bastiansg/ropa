ARG UV_VERSION=0.11.19
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_source

FROM debian:bookworm-slim

ARG PYTHON_VERSION=3.11
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git-core \
    htop \
    openssh-client \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-distutils \
    python3-setuptools \
    vim \
    zsh \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/tmp/* /var/lib/apt/lists/*

RUN rm /usr/lib/python${PYTHON_VERSION}/EXTERNALLY-MANAGED
RUN update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1
COPY --from=uv_source /uv /uvx /bin/

WORKDIR /tmp

COPY .devcontainer/requirements.txt .
RUN uv pip install -r requirements.txt

RUN rm -rf /tmp/*

WORKDIR /workspace

ENV SHELL=/usr/bin/zsh
RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
