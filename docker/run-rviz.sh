#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mapper=fast-livo2-rtk
viewer=fast-livo2-rtk-rviz
if [ ! -S /tmp/.X11-unix/X0 ] || [ ! -e /dev/dxg ]; then
  echo 'WSLg X11 socket or /dev/dxg GPU device is unavailable.' >&2
  exit 1
fi
if [ "$(docker inspect -f '{{.State.Running}}' "$mapper" 2>/dev/null)" != true ]; then
  echo "Mapping container $mapper is not running." >&2
  exit 1
fi
if ! docker exec "$mapper" bash -lc 'source /rtk_ws/devel/setup.bash; rosnode ping -c 1 /laserMapping >/dev/null 2>&1'; then
  echo 'The /laserMapping ROS node is not responding.' >&2
  exit 1
fi
if [ "$(docker inspect -f '{{.State.Running}}' "$viewer" 2>/dev/null)" = true ]; then
  echo "RViz is already running in $viewer."
  exit 0
fi
docker run -d --rm --name "$viewer" \
  --gpus all --device /dev/dxg \
  --network "container:$mapper" \
  --mount type=bind,source=/tmp/.X11-unix,target=/tmp/.X11-unix,readonly \
  --mount type=bind,source=/usr/lib/wsl,target=/usr/lib/wsl,readonly \
  --mount "type=bind,source=$root,target=/project,readonly" \
  -e DISPLAY=:0 -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -e GALLIUM_DRIVER=d3d12 -e MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
  -e QT_X11_NO_MITSHM=1 \
  -e ROS_MASTER_URI=http://127.0.0.1:11311 -e ROS_IP=127.0.0.1 \
  fast-livo2-rtk:noetic \
  bash -lc 'source /opt/ros/noetic/setup.bash; exec rviz -d /project/rviz_cfg/fast_livo2_gpu.rviz'
echo "RViz started in $viewer."
