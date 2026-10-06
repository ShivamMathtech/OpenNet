FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt ./
COPY core core
COPY apps/node.cpp apps/node.cpp
COPY tests/packet_test.cpp tests/packet_test.cpp
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2 && ctest --test-dir build --output-on-failure
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 libssl3t64 && rm -rf /var/lib/apt/lists/* && useradd -m -u 10001 opennet
WORKDIR /app
COPY --chown=opennet:opennet . .
COPY --from=builder --chown=opennet:opennet /src/build/opennet-node build/opennet-node
USER opennet
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/api/state',timeout=2)"
CMD ["python3","-m","controller.main","--bind","0.0.0.0"]
