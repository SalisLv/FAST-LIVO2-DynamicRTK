#pragma once

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace gnss {

// Accuracy estimates are in metres, not variances. Unknown status is used for
// legacy nine-column rtk.txt files; it must never be promoted to an RTK fix.
struct Quality {
    double h_acc = 0.0;
    double v_acc = 0.0;
    double p_dop = 0.0;
    double vel_acc = 0.0;
    int fix_type = -1;
    int carr_soln = -1;
    int num_sv = -1;
    bool valid_fix = true;
    bool diff_soln = false;
    bool status_known = false;
};

struct Options {
    bool enabled = true;
    double accuracy_scale = 1.0;
    double fixed_sigma_xy = 0.10;
    double fixed_sigma_z = 1.0;
    double float_sigma_xy = 0.50;
    double float_sigma_z = 2.0;
    double single_sigma_xy = 2.0;
    double single_sigma_z = 5.0;
    double max_sigma_xy = 20.0;
    double max_sigma_z = 50.0;
    int min_satellites = 8;
    double max_pdop = 3.0;
    double auxiliary_sigma_scale = 2.0;
    double max_time_difference = 0.06;
    double recovery_seconds = 1.0;
    double recovery_gap_seconds = 0.5;
    double huber_k = 2.5;
    double alignment_max_sigma_xy = 1.0;

    void validate() const {
        const double positive[] = {accuracy_scale, fixed_sigma_xy, fixed_sigma_z,
            float_sigma_xy, float_sigma_z, single_sigma_xy, single_sigma_z,
            max_sigma_xy, max_sigma_z, max_pdop, auxiliary_sigma_scale,
            max_time_difference, recovery_gap_seconds, huber_k, alignment_max_sigma_xy};
        for (double value : positive) {
            if (!std::isfinite(value) || value <= 0.0)
                throw std::invalid_argument("GNSS quality parameters must be finite and positive");
        }
        if (!std::isfinite(recovery_seconds) || recovery_seconds < 0.0 || min_satellites < 0 ||
            fixed_sigma_xy > float_sigma_xy || float_sigma_xy > single_sigma_xy ||
            fixed_sigma_z > float_sigma_z || float_sigma_z > single_sigma_z ||
            single_sigma_xy > max_sigma_xy || single_sigma_z > max_sigma_z ||
            auxiliary_sigma_scale < 1.0)
            throw std::invalid_argument("Invalid GNSS quality limits or ordering");
    }
};

struct Decision {
    bool accepted = false;
    double sigma_xy = std::numeric_limits<double>::quiet_NaN();
    double sigma_z = std::numeric_limits<double>::quiet_NaN();
    std::string reason = "unprocessed";
};

inline Decision evaluate(const Quality& q, const Options& options) {
    Decision d;
    if (q.status_known && (!q.valid_fix || (q.fix_type != 3 && q.fix_type != 4))) {
        d.reason = "invalid_fix";
        return d;
    }
    if (q.status_known && (q.carr_soln < 0 || q.carr_soln > 2)) {
        d.reason = "invalid_carrier_status";
        return d;
    }
    // Only a valid differential carrier solution receives the fixed/float floor.
    const int tier = q.status_known && q.diff_soln ? q.carr_soln : 0;
    d.sigma_xy = tier == 2 ? options.fixed_sigma_xy :
                 tier == 1 ? options.float_sigma_xy : options.single_sigma_xy;
    d.sigma_z = tier == 2 ? options.fixed_sigma_z :
                tier == 1 ? options.float_sigma_z : options.single_sigma_z;
    d.reason = !q.status_known ? "unknown_status" :
               tier == 2 ? "fixed" : tier == 1 ? "float" : "single";
    if (!std::isfinite(q.h_acc) || q.h_acc <= 0.0 ||
        !std::isfinite(q.v_acc) || q.v_acc <= 0.0) {
        // Missing accuracy is not a perfect measurement. Use the single floor.
        d.sigma_xy = std::max(d.sigma_xy, options.single_sigma_xy);
        d.sigma_z = std::max(d.sigma_z, options.single_sigma_z);
        d.reason += "_unknown_accuracy";
    }
    if (std::isfinite(q.h_acc) && q.h_acc > 0.0)
        d.sigma_xy = std::max(d.sigma_xy, options.accuracy_scale * q.h_acc);
    if (std::isfinite(q.v_acc) && q.v_acc > 0.0)
        d.sigma_z = std::max(d.sigma_z, options.accuracy_scale * q.v_acc);
    if ((q.num_sv >= 0 && q.num_sv < options.min_satellites) ||
        (std::isfinite(q.p_dop) && q.p_dop > options.max_pdop)) {
        // Apply once: satellite count and DOP are correlated indicators.
        d.sigma_xy *= options.auxiliary_sigma_scale;
        d.sigma_z *= options.auxiliary_sigma_scale;
        d.reason += "_poor_geometry";
    }
    d.accepted = d.sigma_xy <= options.max_sigma_xy && d.sigma_z <= options.max_sigma_z;
    if (!d.accepted) d.reason = "excessive_uncertainty";
    return d;
}

// Degradation is immediate. Following a quality upgrade or a data gap, require
// a continuous interval before giving the upgraded solution its full weight.
class Recovery {
public:
    void apply(double time, const Quality& q, const Options& options, Decision& d) {
        const int tier = !d.accepted ? -1 :
            q.status_known && q.diff_soln && q.carr_soln == 2 &&
            d.sigma_xy < options.float_sigma_xy ? 2 :
            d.sigma_xy < options.single_sigma_xy ? 1 : 0;
        if (std::isfinite(last_time_) &&
            (time - last_time_ > options.recovery_gap_seconds || time <= last_time_)) {
            previous_tier_ = -1;
            stable_since_ = time;
        }
        if (tier != previous_tier_) stable_since_ = time;
        previous_tier_ = tier;
        last_time_ = time;
        if (!d.accepted || tier <= 0 || options.recovery_seconds == 0.0) return;
        const double a = std::min(1.0, std::max(0.0, (time - stable_since_) / options.recovery_seconds));
        if (a < 1.0) {
            const double floor_xy = tier == 2 ? options.float_sigma_xy : options.single_sigma_xy;
            const double floor_z = tier == 2 ? options.float_sigma_z : options.single_sigma_z;
            d.sigma_xy = std::max(d.sigma_xy, floor_xy * (1.0 - a) + d.sigma_xy * a);
            d.sigma_z = std::max(d.sigma_z, floor_z * (1.0 - a) + d.sigma_z * a);
            d.reason += "_recovering";
        }
    }
private:
    double last_time_ = std::numeric_limits<double>::quiet_NaN();
    double stable_since_ = 0.0;
    int previous_tier_ = -1;
};

} // namespace gnss
