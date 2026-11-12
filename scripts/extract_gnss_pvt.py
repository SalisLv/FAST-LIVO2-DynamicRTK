#!/usr/bin/env python3
"""Extract the PVT input for replay_gnss_backend in a sourced ROS environment."""
import argparse
from pathlib import Path


def main():
    import rosbag

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag")
    parser.add_argument("output")
    parser.add_argument("--topic", default="/ublox_driver/receiver_pvt")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with rosbag.Bag(args.bag) as bag, output.open("w") as stream:
        stream.write("# unix_time lat lon alt ve vn vd h_acc v_acc fix_type valid_fix diff_soln carr_soln num_sv p_dop vel_acc\n")
        for _, msg, _ in bag.read_messages(topics=[args.topic]):
            timestamp = 315964800.0 + msg.time.week * 604800.0 + msg.time.tow - 18.0
            values = (timestamp, msg.latitude, msg.longitude, msg.altitude,
                      msg.vel_e, msg.vel_n, msg.vel_d, msg.h_acc, msg.v_acc,
                      msg.fix_type, int(msg.valid_fix), int(msg.diff_soln),
                      msg.carr_soln, msg.num_sv, msg.p_dop, msg.vel_acc)
            stream.write(" ".join(format(value, ".15g") for value in values) + "\n")
            count += 1
    if count == 0:
        parser.error("No PVT observations found on the selected topic")
    print(f"Extracted {count} PVT observations to {output}")


if __name__ == "__main__":
    main()
