#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/noetic/setup.bash
mkdir -p /rtk_ws/src
ln -sfn /project /rtk_ws/src/FAST-LIVO2-RTK
ln -sfn /project/.runtime/deps/gnss_comm /rtk_ws/src/gnss_comm
if [ ! -d /rtk_ws/src/rpg_vikit ]; then
  cp -a /ws/src/rpg_vikit /rtk_ws/src/
fi
# This dependency overrides CMAKE_CXX_FLAGS, so a workspace flag alone cannot
# disable its AVX allocator. Modify only the workspace copy, not /ws's source.
for vikit_cmake in /rtk_ws/src/rpg_vikit/vikit_common/CMakeLists.txt /rtk_ws/src/rpg_vikit/vikit_ros/CMakeLists.txt; do
  if grep -q -- '-march=native' "$vikit_cmake"; then
    sed -i 's/-march=native/-mtune=native/g' "$vikit_cmake"
  fi
done
mkdir -p /project/Log/pcd /project/Log/result
cd /rtk_ws
# GTSAM is built without AVX. Keep Eigen's dynamic
# allocation ABI compatible across these shared libraries (including on AVX CPUs).
catkin_make -j1 -l2 -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-DEIGEN_MAX_ALIGN_BYTES=16
