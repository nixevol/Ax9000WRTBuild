FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential clang flex bison g++ gawk gcc-multilib g++-multilib \
    gettext git libncurses5-dev libssl-dev python3 python3-setuptools \
    rsync swig unzip zlib1g-dev file wget curl ca-certificates dwarves \
    llvm python3-pyelftools libpython3-dev aria2 jq qemu-utils ccache \
    rename libelf-dev device-tree-compiler libgmp3-dev libmpc-dev \
    libfuse-dev sudo time xz-utils zstd bc patch gosu && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN if id ubuntu >/dev/null 2>&1; then \
        groupmod -n builder ubuntu && \
        usermod -l builder -d /home/builder -m ubuntu; \
    else \
        useradd -m -u 1000 builder; \
    fi && \
    mkdir -p /workspace /work && \
    chown -R builder:builder /workspace /work

COPY --chmod=0755 scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["bash", "scripts/build.sh"]
