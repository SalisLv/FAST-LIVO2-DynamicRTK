#!/usr/bin/env bash
set -euo pipefail
container=fast-livo2-rtk
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! docker container inspect "$container" >/dev/null 2>&1; then
  if [ ! -S /tmp/.X11-unix/X0 ] || [ ! -e /dev/dxg ]; then
    echo 'WSLg X11 socket or GPU device /dev/dxg is unavailable.' >&2
    exit 1
  fi
  docker run -d --name "$container" \
    --gpus all --device /dev/dxg \
    --mount type=bind,source=/tmp/.X11-unix,target=/tmp/.X11-unix,readonly \
    --mount type=bind,source=/usr/lib/wsl,target=/usr/lib/wsl,readonly \
    --mount "type=bind,source=$root,target=/project" \
    -e DISPLAY=:0 -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
    -e GALLIUM_DRIVER=d3d12 -e MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
    -e QT_X11_NO_MITSHM=1 \
    --workdir /rtk_ws fast-livo2-rtk:noetic sleep infinity >/dev/null
fi
if [ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]; then
  docker start "$container" >/dev/null
fi
if [ ! -e /dev/dxg ] || ! docker exec "$container" test -e /dev/dxg; then
  echo "NVIDIA GPU access is unavailable in $container; recreate the container with this script's GPU options." >&2
  exit 1
fi
case "${1:-launch}" in
  launch|gpu)
    output_path=${2:-/project/output/HH-LVGO-01-gpu-limited}
    docker exec -it "$container" bash -lc \
      'source /rtk_ws/devel/setup.bash; export OMP_NUM_THREADS=4; exec roslaunch fast_livo HH_gpu.launch rviz:=true outputfilepath:="$1"' \
      bash "$output_path"
    ;;
  headless)
    docker exec -it "$container" bash -lc \
      'source /rtk_ws/devel/setup.bash; export OMP_NUM_THREADS=4; roslaunch fast_livo HH.launch rviz:=false outputfilepath:=/project/output/HH-LVGO-01'
    ;;
  play)
    shift
    docker exec -it "$container" bash -lc \
      'source /rtk_ws/devel/setup.bash; exec rosbag play /project/datasets/HH-LVGO-01.bag "$@"' bash "$@"
    ;;
  view-pcd)
    case "${2:-after}" in
      before|after) stage=${2:-after} ;;
      *) echo 'Usage: docker/run.sh view-pcd [before|after]' >&2; exit 2 ;;
    esac
    map_dir=/project/output/HH-LVGO-01-gpu-limited
    source_pcd="$map_dir/global_pcd/${stage}_optimization.pcd"
    preview_dir="$map_dir/preview"
    preview_pcd="$preview_dir/${stage}_optimization_1of20.pcd"
    viewer_user="$(id -u):$(id -g)"
    docker exec --user "$viewer_user" "$container" python3 /project/scripts/sample_pcd.py \
      "$source_pcd" "$preview_pcd" --every 20
    docker exec -it --user "$viewer_user" --workdir "$preview_dir" "$container" \
      pcl_viewer "$preview_pcd" -ps 2 -bc 0,0,0
    ;;
  build)
    docker exec "$container" /project/docker/build-workspace.sh
    ;;
  shell)
    docker exec -it "$container" bash -c 'source /rtk_ws/devel/setup.bash; exec bash'
    ;;
  *) echo 'Usage: docker/run.sh {launch|gpu|headless|play [rosbag options]|view-pcd [before|after]|build|shell}' >&2; exit 2 ;;
esac
