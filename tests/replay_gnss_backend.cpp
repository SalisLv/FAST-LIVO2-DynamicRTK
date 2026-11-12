// Replay an existing LIVO TUM trajectory against raw PVT observations, without
// rerunning the front end. PVT rows: unix_time lat lon alt ve vn vd hacc vacc
// fix_type valid_fix diff_soln carr_soln num_sv pdop vel_acc.
#include "optimization.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
    ros::init(argc, argv, "gnss_backend_replay");
    std::vector<std::string> args;
    ros::removeROSArgs(argc, argv, args);
    if (args.size() != 5) {
        std::cerr << "Usage: replay_gnss_backend livo.tum pvt.txt output_directory dynamic|fixed\n";
        return 2;
    }
    ros::NodeHandle nh;
    nh.setParam("laserMapping/outputfilepath", args[3]);
    nh.setParam("opt/gnss_quality/enabled", args[4] == "dynamic");
    nh.setParam("gps/gps_en", true);
    optimization backend(nh, false);
    std::ifstream trajectory(args[1]);
    if (!trajectory) return 3;
    std::string line;
    while (std::getline(trajectory, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream row(line);
        double t, x, y, z, qx, qy, qz, qw;
        if (!(row >> t >> x >> y >> z >> qx >> qy >> qz >> qw)) return 4;
        const gtsam::Pose3 pose(gtsam::Rot3(Eigen::Quaterniond(qw, qx, qy, qz).normalized()), gtsam::Point3(x,y,z));
        Eigen::Vector3d velocity = Eigen::Vector3d::Zero();
        if (!backend.keyFrames.empty()) {
            const auto& previous = backend.keyFrames.back();
            const double dt = t - previous.time;
            if (dt <= 0.0) return 5;
            velocity = (pose.translation() - previous.pose.translation()) / dt;
        }
        backend.saveKeyFrameAndFactor(pose, t, velocity, PointCloudXYZRGB::Ptr());
    }
    std::ifstream observations(args[2]);
    if (!observations) return 6;
    while (std::getline(observations, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream row(line);
        gnss_comm::GnssPVTSolnMsg::Ptr p(new gnss_comm::GnssPVTSolnMsg);
        double t;
        int fix, valid, diff, carrier, satellites;
        if (!(row >> t >> p->latitude >> p->longitude >> p->altitude >> p->vel_e >> p->vel_n >> p->vel_d
                  >> p->h_acc >> p->v_acc >> fix >> valid >> diff >> carrier >> satellites >> p->p_dop >> p->vel_acc)) return 7;
        const double gps = t - 315964800.0 + 18.0;
        p->time.week = static_cast<unsigned>(gps / 604800.0);
        p->time.tow = gps - p->time.week * 604800.0;
        p->fix_type = fix; p->valid_fix = valid; p->diff_soln = diff;
        p->carr_soln = carrier; p->num_sv = satellites;
        backend.gpsHandler(p);
    }
    if (backend.keyFrames.empty()) return 8;
    backend.offlineOptimizationTask();
    return backend.is_optimized ? 0 : 9;
}
