FROM ropa-core

COPY src/ropa /src/src/ropa
COPY requirements.txt pyproject.toml /src/
RUN --mount=type=bind,source=.git,target=/src/.git \
    uv pip install /src --no-deps

WORKDIR /src
CMD ["python", "-m", "ropa.scripts.test_ay_not_dead_collector"]
