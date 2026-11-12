# GNSS 动态权重

离线后端默认启用 `opt/gnss_quality/enabled`。FAST-LIVO2 前端继续按原来的方式估计轨迹，GTSAM 后端根据每次 GNSS 观测的质量设置位置约束。HH、HH GPU 和 AGV 配置中均提供参数。

## 权重规则

精度估计 `h_acc`、`v_acc` 的单位是米。后端近似采用水平各向同性模型，分别计算水平和垂直标准差：

```text
sigma_xy = max(accuracy_scale * h_acc, 当前定位状态的水平标准差下限)
sigma_z  = max(accuracy_scale * v_acc, 当前定位状态的垂直标准差下限)
R = diag(sigma_xy², sigma_xy², sigma_z²)
```

这里是需要实测标定的保守工程模型，不能把接收机的精度估计当作真实误差保证。传入 GTSAM 的 `Sigmas` 是标准差；ROS Odometry 的 `pose.covariance` 保存平方后的方差。

| 状态 | 水平标准差下限 | 垂直标准差下限 |
|---|---:|---:|
| 有效差分固定解 | 0.10 m | 1.0 m |
| 有效差分浮点解 | 0.50 m | 2.0 m |
| 普通定位或状态未知 | 2.0 m | 5.0 m |

固定解的下限保留了原 HH 配置的水平、垂直噪声尺度。数值是第一版起始参数，并非接收机精度指标。

- `valid_fix=false`、不支持的三维定位状态（例如 2D、仅时间定位）、非法载波状态不参与动态融合。
- `diff_soln=false` 时使用普通定位的下限，不能仅凭载波状态取得高权重。
- 精度估计非正、缺失或非有限值时，至少使用普通定位的下限。
- 卫星数少于 `min_satellites`，或 PDOP 大于 `max_pdop` 时，标准差乘以 `auxiliary_sigma_scale`。两者同时出现也只乘一次。
- 标准差超过 `max_sigma_xy / max_sigma_z` 时拒绝观测，不将它截断为一个看起来更好的测量值。
- 质量变差立即降权。状态升级或数据间隔超过 `recovery_gap_seconds`（默认 0.5 s）后，在 `recovery_seconds` 内从更保守的标准差逐渐恢复。
- Huber 核在标准差归一化后的残差上工作，`huber_k` 是无量纲阈值。它降低异常残差的影响；本版不会仅因 GNSS 与 LIVO 的绝对位置相差大，就硬性删除观测。

## 时间匹配与坐标对齐

动态模式使用原始 GNSS 观测，每条观测最多产生一个因子，每个关键帧最多接受一个观测。多个观测匹配同一关键帧时，优先保留预计水平不确定性更小的一个。

观测必须位于 LIVO 时间范围内，与最近关键帧的时间差不超过 `max_time_difference`（默认 0.06 s，适配当前约 10 Hz 数据）。匹配时按 GNSS 各轴速度和时间差额外增加运动不确定性。GNSS 低频数据可以产生稀疏约束；LIVO 关键帧频率改变时，应重新检查这一阈值。`recovery_gap_seconds` 独立控制恢复逻辑中的 GNSS 中断判定，GNSS 低频输入需要相应调大它。

此模式不会对 GNSS 做样条外推，也不会跨失锁区间生成定位约束。它仍沿用原有的速度时间对齐流程。

初始空间对齐优先使用固定解，至少需要六个时间匹配、水平标准差不超过 `alignment_max_sigma_xy` 的观测。优先使用可靠观测开始后的 50 秒，执行加权刚体对齐和 Huber 迭代降权。静止、严格共线或可靠观测不足时，跳过 GNSS 修正并保留 LIVO 轨迹。动态模式对首帧位置使用宽松先验，避免将初始对齐结果当作毫米精度的位置测量。

优化变量使用天线位姿；导出的 LIVO TUM 与地图使用 IMU 位姿，包含配置的 GNSS 杠杆臂转换。

## 输出与切换

新输出：`<outputfilepath>/debug/gnss_quality.csv`。每个保留下来的原始观测占一行，包含状态、接收机精度估计、质量判定、匹配结果、最终各轴标准差、是否参与优化、优化后残差、Huber 权重和各轴信息权重。非法经纬度/时间或首次有效原点建立之前的无效观测会在输入端丢弃。

- `quality_accepted=1` 只表示质量规则允许使用。
- `used=1` 表示经过匹配和成功对齐，实际加入了 GNSS 因子。
- `information_x/y/z` 是最终局部二次近似中的 `robust_weight / sigma²`，不是“GNSS 准确概率”，也不是轨迹修正百分比。
- 没有 GNSS 或对齐失败时，不添加 GNSS 因子。

将 YAML 中的 `opt/gnss_quality/enabled` 改为 `false`，可恢复原来的固定噪声与样条关联路径。其他动态质量参数在该模式下不参与赋权。比较结果时应同时检查时间对齐结果；动态模式的输入筛选可能影响时间偏移估计。

调试文件 `rtk.txt` 保留原先九列，并追加 `fix_type valid_fix diff_soln carr_soln num_sv p_dop vel_acc` 七列。旧九列文件仍能读取，定位状态标记为未知，使用普通定位下限；默认的可靠对齐阈值通常会使仅有旧文件的输入跳过 GNSS 对齐。若需重现固定解分级，应从原始 bag 提取或重新保存完整字段。

## 编译和验证

Docker 构建脚本将工作区的 `EIGEN_MAX_ALIGN_BYTES` 统一为 16，并将容器工作区中 vikit 的 `-march=native` 换成 `-mtune=native`，与当前非 AVX GTSAM 保持 Eigen 分配 ABI 一致。vikit 会覆盖全局 CXX_FLAGS，因此单独传一个全局参数不足以处理它的指令集选项。直接使用 catkin 编译时也应同步这两项设置，并重新编译相关依赖，避免跨库分配/释放崩溃。

常用容器中的代码更新后需要重新编译：

```bash
./docker/run.sh build
```

启用 catkin 测试时，会构建 `test_gnss_quality` 和 `replay_gnss_backend`。前者覆盖质量规则与恢复；后者复用同一条 LIVO TUM，直接运行 GNSS 后端，无需重复运行前端或装载完整地图。

以下命令在已加载 ROS/catkin 环境、有本地 ROS master 的容器中执行：

```bash
rosparam load /project/config/HH-LVGO-GPU.yaml
python3 /project/scripts/extract_gnss_pvt.py \
  /project/datasets/HH-LVGO-01_compressed.bag /project/.runtime/gnss-pvt.txt
rosrun fast_livo test_gnss_quality
printf '\n' | rosrun fast_livo replay_gnss_backend \
  /project/output/HH-LVGO-01-gpu-limited/TUM/livo_trajectory_before.txt \
  /project/.runtime/gnss-pvt.txt /project/output/gnss-dynamic dynamic
```

将末尾的输出目录改成另一个新目录、模式改成 `fixed`，即可比较固定权重版本。回放工具只装载轨迹和 GNSS，不装载点云，所生成 PCD 为空，不是一次完整前端重建的地图。

现有 GNSS 不作为独立真值。轨迹更贴近参与融合的 GNSS、优化残差更小，都不能单独证明绝对定位精度提高。

两种模式的结果分别放在同一个目录的 `fixed/` 和 `dynamic/` 下后，可以生成轨迹、权重与修正量对比图：

```bash
python3 /project/scripts/plot_gnss_quality.py /project/output/gnss-weighting-validation
```
