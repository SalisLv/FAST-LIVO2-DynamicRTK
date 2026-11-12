# Reuse the existing local FAST-LIVO2 / Ubuntu 20.04 / ROS Noetic image.
FROM fast-livo2:noetic
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeographic-dev libgoogle-glog-dev python3-matplotlib mesa-utils pcl-tools && rm -rf /var/lib/apt/lists/*
COPY .runtime/deps/gtsam /opt/gtsam
RUN cmake -S /opt/gtsam -B /opt/gtsam-build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF -DGTSAM_USE_SYSTEM_EIGEN=ON \
      -DGTSAM_BUILD_TESTS=OFF -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
      -DGTSAM_BUILD_UNSTABLE=OFF -DGTSAM_BUILD_PYTHON=OFF \
    && cmake --build /opt/gtsam-build -j2 \
    && cmake --install /opt/gtsam-build && ldconfig
COPY .runtime/deps/gnss_comm /project/.runtime/deps/gnss_comm
COPY CMakeLists.txt package.xml /project/
COPY include /project/include
COPY src /project/src
COPY config /project/config
COPY launch /project/launch
COPY rviz_cfg /project/rviz_cfg
COPY scripts /project/scripts
COPY docker/build-workspace.sh /project/docker/build-workspace.sh
RUN /project/docker/build-workspace.sh
WORKDIR /rtk_ws
CMD ["sleep", "infinity"]
