#include "gnss_quality.h"
#include <cstdlib>
#include <iostream>

static void check(bool condition, const char* message) {
    if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}

int main() {
    gnss::Options options;
    options.validate();
    gnss::Quality q;
    q.status_known = true; q.valid_fix = true; q.fix_type = 3;
    q.carr_soln = 2; q.diff_soln = true; q.num_sv = 20; q.p_dop = 1.0;
    q.h_acc = 0.02; q.v_acc = 0.03;
    const auto fixed = gnss::evaluate(q, options);
    check(fixed.accepted && fixed.sigma_xy == 0.1 && fixed.sigma_z == 1.0, "Fixed floors failed");
    q.h_acc = 0.4;
    check(gnss::evaluate(q, options).sigma_xy == 0.4, "Reported accuracy must be respected");
    q.h_acc = 0.02; q.carr_soln = 1;
    const auto floating = gnss::evaluate(q, options);
    check(floating.sigma_xy > fixed.sigma_xy, "Float must have lower information than fixed");
    q.carr_soln = 0;
    const auto single = gnss::evaluate(q, options);
    check(single.sigma_xy > floating.sigma_xy, "Single must have lower information than float");
    q.carr_soln = 2; q.diff_soln = false;
    check(gnss::evaluate(q, options).sigma_xy == single.sigma_xy, "No corrections must not receive fixed weight");
    q.diff_soln = true; q.valid_fix = false;
    check(!gnss::evaluate(q, options).accepted, "Invalid fix must be rejected");
    q.valid_fix = true; q.fix_type = 2;
    check(!gnss::evaluate(q, options).accepted, "2D fix must not enter a 3D factor");
    q.fix_type = 3; q.carr_soln = 3;
    check(!gnss::evaluate(q, options).accepted, "Reserved carrier solution must be rejected");
    q.carr_soln = 2; q.h_acc = 0.0;
    check(gnss::evaluate(q, options).sigma_xy >= single.sigma_xy, "Zero accuracy is unknown, not perfect");
    q.h_acc = std::numeric_limits<double>::quiet_NaN();
    check(std::isfinite(gnss::evaluate(q, options).sigma_xy), "NaN accuracy poisoned covariance");
    q.h_acc = 100.0;
    check(!gnss::evaluate(q, options).accepted, "Excess uncertainty must be rejected, not capped");
    q.h_acc = 0.02; q.num_sv = 4; q.p_dop = 9.0;
    check(gnss::evaluate(q, options).sigma_xy == 0.2, "Correlated indicators inflated more than once");
    q.num_sv = 20; q.p_dop = 1.0; q.status_known = false;
    check(gnss::evaluate(q, options).sigma_xy == single.sigma_xy, "Legacy data falsely promoted to fixed");
    q.status_known = true;
    gnss::Recovery recovery;
    auto d = gnss::evaluate(q, options);
    recovery.apply(0.0, q, options, d);
    check(d.sigma_xy >= floating.sigma_xy, "Recovery started with full fixed weight");
    for (int n = 1; n <= 11; ++n) {
        d = gnss::evaluate(q, options);
        recovery.apply(n * 0.1, q, options, d);
    }
    check(std::abs(d.sigma_xy - fixed.sigma_xy) < 1e-12, "Stable fixed observations did not recover");
    d = gnss::evaluate(q, options);
    recovery.apply(1.3, q, options, d);
    check(std::abs(d.sigma_xy - fixed.sigma_xy) < 1e-12, "Short gap incorrectly reset recovery");
    d = gnss::evaluate(q, options);
    recovery.apply(3.0, q, options, d);
    check(d.sigma_xy >= floating.sigma_xy, "Data gap did not reset recovery");
    q.carr_soln = 0; d = gnss::evaluate(q, options);
    recovery.apply(3.1, q, options, d);
    check(d.sigma_xy == single.sigma_xy, "Degradation must be immediate");
    bool rejected = false;
    options.fixed_sigma_xy = 0.0;
    try { options.validate(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, "Invalid configuration accepted");
    std::cout << "GNSS quality policy checks passed\n";
}
