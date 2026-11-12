#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
container=fast-livo2-rtk-pcd-rviz
compare=false
rviz_config=/project/rviz_cfg/global_pcd.rviz
case "${1:-after}" in
  after) pcd=/project/output/HH-LVGO-01-gpu-limited/global_pcd/after_optimization.pcd ;;
  before) pcd=/project/output/HH-LVGO-01-gpu-limited/global_pcd/before_optimization.pcd ;;
  preview-after) pcd=/project/output/HH-LVGO-01-gpu-limited/preview/after_optimization_1of20.pcd ;;
  compare)
    pcd=/project/output/HH-LVGO-01-gpu-limited/global_pcd/after_optimization.pcd
    compare=true
    rviz_config=/project/rviz_cfg/trajectory_compare.rviz
    ;;
  *) echo 'Usage: docker/run-global-pcd-rviz.sh [after|before|preview-after|compare]' >&2; exit 2 ;;
esac
if [ ! -f "$root/${pcd#/project/}" ]; then
  echo "PCD file not found: $root/${pcd#/project/}" >&2
  exit 1
fi
if [ ! -S /tmp/.X11-unix/X0 ] || [ ! -e /dev/dxg ]; then
  echo 'WSLg X11 socket or GPU device /dev/dxg is unavailable.' >&2
  exit 1
fi
if docker container inspect "$container" >/dev/null 2>&1; then
  echo "$container already exists. Close its RViz window before starting another map viewer." >&2
  exit 1
fi
docker run --rm --name "$container" \
  --gpus all --device /dev/dxg --memory 6g --memory-swap 7g \
  --mount type=bind,source=/tmp/.X11-unix,target=/tmp/.X11-unix,readonly \
  --mount type=bind,source=/usr/lib/wsl,target=/usr/lib/wsl,readonly \
  --mount "type=bind,source=$root,target=/project,readonly" \
  -e DISPLAY=:0 -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -e GALLIUM_DRIVER=d3d12 -e MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
  -e QT_X11_NO_MITSHM=1 \
  --workdir /rtk_ws fast-livo2-rtk:noetic \
  bash -lc 'source /rtk_ws/devel/setup.bash; exec roslaunch fast_livo view_global_pcd.launch pcd_file:="$1" compare:="$2" rviz_config:="$3"' \
  bash "$pcd" "$compare" "$rviz_config"
