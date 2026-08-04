FROM ropa-core

COPY src/ropa /src/src/ropa
COPY requirements.txt pyproject.toml /src/
RUN --mount=type=bind,source=.git,target=/src/.git \
    uv pip install /src --no-deps

WORKDIR /src
