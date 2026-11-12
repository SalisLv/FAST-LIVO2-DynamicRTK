# 本机 Docker 运行说明

宿主机为 Ubuntu 26.04；项目在 Ubuntu 20.04 / ROS Noetic 容器运行。
容器名 `fast-livo2-rtk`，工作区 `/rtk_ws`，本项目绑定挂载到 `/project`。
基础镜像复用本机已有的 `fast-livo2:noetic`，依赖提交记录见 `dependencies.lock.json`。

RTK 额外依赖：

- `gnss_comm`：HKUST 官方仓库，生成 `GnssPVTSolnMsg` 等消息；它还需要 `libgoogle-glog-dev`。
- GTSAM 4.2：源码构建，使用系统 Eigen，关闭 `march=native`。
- `libgeographic-dev` 1.50.1：经纬度转换到局部坐标。
- `ros-noetic-eigen-conversions`：基础镜像已安装。
- `python3-matplotlib`：项目的时间对齐绘图脚本需要，README 未单独列出。

基础镜像包含 Eigen 3.3.7、OpenCV 4.2、PCL 1.10、README 指定的 Sophus `a621ff` 和作者的 `rpg_vikit`。
项目自带 Livox ROS 消息头，离线播放不需要连接 GNSS 接收机或启动硬件驱动。

## 运行

在项目目录的第一个终端启动建图节点和独显 RViz：

```bash
./docker/run.sh launch
```

另一个终端播放官方数据：

```bash
./docker/run.sh play -r 0.7
```

播放结束后，回到第一个终端按 Enter，触发 RTK 后端优化。
等待出现 `[Offline Optimization] Finished.` 后再按 Ctrl+C 退出。
结果写入宿主机 `output/HH-LVGO-01-gpu-limited/`，包括 `TUM/`、`global_pcd/` 和 `debug/`。
`launch` 默认挂载 WSLg 图形套接字与 `/dev/dxg`，选择 NVIDIA 独显渲染 RViz。为适应本机约 8 GB 的 WSL 内存，它启用局部地图滑动，并将 RViz 点云显示保留时间设为 2 秒。若只需原始参数的无界面运行，使用 `./docker/run.sh headless`，结果写入 `output/HH-LVGO-01/`。

README 指向的[官方 Drive 文件夹](https://drive.google.com/drive/folders/1xun-YL78cbMtyV60uN3FQFsHkkLUWvtJ)现提供 `HH-LVGO-01_compressed.bag`（2,864,805,749 字节）。
`datasets/HH-LVGO-01.bag` 是指向该文件的符号链接；rosbag 可直接读取压缩 bag。
这不会将图像消息改成原始图像，`HH.launch` 中的 image_transport 节点负责图像解码。

## 重新编译

```bash
./docker/run.sh build
```

使用单任务编译控制内存占用。依赖源码保存在 `.runtime/deps/`。
若需要从已有基础镜像重新构建完整镜像：

```bash
docker build -f docker/Dockerfile -t fast-livo2-rtk:noetic .
```

该 Dockerfile 依赖本机的基础镜像和已下载依赖源码，不是脱离本目录即可构建的镜像定义。

数据本地 SHA-256（用于后续检查，非作者发布的校验值）：

```text
85b4846d75543be33d316879ce08b4046e4f781ab4bd3194cf36af073e90e2d3
```

文件 ID：`1Yfs4oVRiYHqsEp8Rsqq97rL_jrsUMhX6`。数据时长 274.144654 秒，66,433 条消息；RTK PVT 共 2,713 条，消息 MD5 与安装的 `gnss_comm` 一致。

## 本机内存适配

原版在完整回放后，将所有关键帧拼接为单个大点云再保存。在本机约 8 GB 内存下，该步骤触发了系统 OOM，映射进程被杀死。
`src/optimization.cpp` 中的 `saveOptimizedGlobalMap()` 现按关键帧变换并顺序写入二进制 PCD，保留原有点、颜色和顺序。
使用多帧旋转/平移与颜色样本核对，导出文件与原先 PCL 拼接保存结果逐字节一致，且 PCL 能重新读取。
第一次尝试的轨迹与时间对齐信息保留在 `output/HH-LVGO-01-first-attempt/`。

运行时仍可见 `pcl::VoxelGrid::applyFilter` 的体素范围警告；本次只修复地图导出的内存峰值，未修改原始滤波参数或估计算法。

## 已验证结果（2026-09-28）

使用 `HH-LVGO-01_compressed.bag` 以原始参数无界面完整回放，触发离线优化，日志出现 `[Offline Optimization] Finished.`。结果保存在 `output/HH-LVGO-01/`。

- LIVO 优化前轨迹：2,737 帧，优化后轨迹：2,737 帧；RTK 对齐轨迹：2,713 帧。
- 优化前、优化后各生成 34,024,202 点的二进制 PCD（每份 544,387,420 字节）。
- 已逐项检查三条轨迹的时间顺序和有限数值、姿态四元数长度，以及两份 PCD 的头部、长度和所有 XYZ 坐标；均通过。
- 输出还包含 `debug/time_alignment.png`。完整验证数据在 `.runtime/logs/output-validation.json`。

启动同步时出现一条 `[ Data Cut ] Throw one image frame!`，运行中 PCL 也持续提示体素范围溢出。二者未阻止完整处理和地图生成；本次未改动预处理和滤波算法，因此不能据此断言地图的测量精度。

如需从头再运行，请先停止当前演示节点，再执行 `launch` 和 `play` 命令；两种模式使用不同的输出目录。

## WSLg 上显示 RViz

`./docker/run.sh launch` 在同一个容器中启动建图节点与 RViz，并通过 WSLg 的 D3D12 驱动选择 NVIDIA 独显。可用 `docker exec fast-livo2-rtk glxinfo -B` 核对实际 OpenGL 渲染器。此默认设置适用于本项目的 Docker 启动命令。

### 独显 RViz 运行

为使完整回放在约 8 GB 的 WSL 内存内运行，GPU 演示使用 `HH_gpu.launch`：启用项目内建的局部地图滑动，并将 RViz 中长期累积的点云改为只保留最近 2 秒。这会改变建图的局部地图管理；此前原始配置的完整无 RViz 结果仍保存在 `output/HH-LVGO-01/`。

从一个没有运行中 `roslaunch` 的容器开始，在两个终端依次运行：

```bash
./docker/run.sh launch
./docker/run.sh play -r 0.7
```

回放结束后，在第一个终端按 Enter 触发 RTK 优化。GPU 模式结果写到 `output/HH-LVGO-01-gpu-limited/`。RViz 使用 `rviz_cfg/fast_livo2_gpu.rviz`；其 OpenGL 渲染器应报告 `D3D12 (NVIDIA GeForce RTX 5060 Laptop GPU)` 和 `Accelerated: yes`。

GPU/RViz 模式完整验证（2026-09-28）：以 `-r 0.7` 播放全部 274 秒数据，日志出现 `[Offline Optimization] Finished.`，RViz 仍在运行。容器内 OpenGL 报告 `D3D12 (NVIDIA GeForce RTX 5060 Laptop GPU)`、`Accelerated: yes`，同时 `/rviz_*` 节点持续订阅 `/cloud_registered`、`/rgb_img` 和 `/path`。这次无 OOM。

结果在 `output/HH-LVGO-01-gpu-limited/`：优化前、后 LIVO 轨迹各 2,737 帧，RTK 轨迹 2,713 帧；两份地图各 34,020,661 点。轨迹数值、时间顺序、PCD 长度与所有 XYZ 坐标均验证通过，详情在 `.runtime/logs/output-validation-gpu.json`。

第一次同时运行原 RViz 配置和完整建图时，长期累积点云使 WSL 内存耗尽，建图进程被 OOM 杀死；GPU 模式使用短暂保留点云和局部地图滑动，已完整跑通。实时可视化运行若再次出现高内存占用，请保留这两项设置。

## 查看和截图全局 PCD 地图

原始 PCD 约有 3400 万点，直接打开会消耗较多内存。以下命令自动保留每 20 个点中的 1 个，生成可视化副本并使用独显打开；原始 PCD 不会改变：

```bash
./docker/run.sh view-pcd after
```

查看优化前地图则使用 `./docker/run.sh view-pcd before`。在点云窗口中拖动鼠标旋转、滚轮缩放，调好视角后按 `j` 保存当前画面为 PNG。截图和抽稀后的 PCD 都位于 `output/HH-LVGO-01-gpu-limited/preview/`。

### 在 RViz 中查看未经抽稀的全局地图

```bash
./docker/run-global-pcd-rviz.sh after
```

该命令在独立的 GPU 容器中启动 `pcl_ros/pcd_to_pointcloud` 和 RViz，直接读取 `global_pcd/after_optimization.pcd`，不启动建图算法，也不改变 PCD。查看优化前地图可将 `after` 改为 `before`。关闭 RViz 或在终端按 Ctrl+C 即可退出；查看器容器会自动删除。如需仅测试界面，可使用 `preview-after` 读取已有抽稀副本。

单独查看地图与轨迹对比模式使用相同的点云显示参数和相机视角；`after` 模式仅隐藏轨迹。这样可以直接比较有、无轨迹时的地图画面。

本机以 34,021,127 点的完整 PCD 验证：RViz 成功订阅 `/global_map`，OpenGL 设备为 NVIDIA GeForce RTX 5060 Laptop GPU，容器稳定占用约 4.1 GiB，未出现 OOM。查看器的内存上限设置为 6 GiB，避免它挤占整个 WSL 实例。完整地图和实时建图同时运行时的总内存尚未验证，建议先单独查看。

### 叠加比较优化前后轨迹

```bash
./docker/run-global-pcd-rviz.sh compare
```

此模式在完整优化后地图上叠加两条 `nav_msgs/Path`：蓝色是 `TUM/livo_trajectory_before.txt`，橙色是 `TUM/opt_trajectory_after.txt`，各 2,737 帧，时间戳一一对应。地图透明度降低以突出轨迹。两条文件记录的是 LIVO/IMU 设备位姿，而非经过相机外参转换后的严格光心轨迹；本数据的 RTK 杠杆臂设为零，因此两条轨迹可直接在同一 `map` 坐标系显示。轨迹间距离只表示优化位姿变化，不能单独证明精度提高。
