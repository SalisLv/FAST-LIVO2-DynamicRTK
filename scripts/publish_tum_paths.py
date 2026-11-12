#!/usr/bin/env python3
"""Publish two TUM pose files as latched RViz paths in a shared frame."""

import argparse
import math
from pathlib import Path

import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as RosPath


def load_path(filename, frame_id):
    path = RosPath()
    path.header.frame_id = frame_id
    last_time = -math.inf
    with Path(filename).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            values = [float(value) for value in line.split()]
            if len(values) != 8 or not all(math.isfinite(value) for value in values):
                raise ValueError("{}:{}: invalid TUM pose".format(filename, line_number))
            timestamp, x, y, z, qx, qy, qz, qw = values
            if timestamp <= last_time:
                raise ValueError("{}:{}: timestamps are not increasing".format(filename, line_number))
            last_time = timestamp
            pose = PoseStamped()
            pose.header.frame_id = frame_id
            pose.header.stamp = rospy.Time.from_sec(timestamp)
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.position.z = z
            pose.pose.orientation.x = qx
            pose.pose.orientation.y = qy
            pose.pose.orientation.z = qz
            pose.pose.orientation.w = qw
            path.poses.append(pose)
    if not path.poses:
        raise ValueError("{}: no poses found".format(filename))
    path.header.stamp = path.poses[-1].header.stamp
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--frame-id", default="map")
    args = parser.parse_args(rospy.myargv()[1:])
    before = load_path(args.before, args.frame_id)
    after = load_path(args.after, args.frame_id)
    if len(before.poses) != len(after.poses):
        raise ValueError("before and after trajectories have different frame counts")
    if any(abs(a.header.stamp.to_sec() - b.header.stamp.to_sec()) > 1e-4
           for a, b in zip(before.poses, after.poses)):
        raise ValueError("before and after trajectory timestamps do not align")

    rospy.init_node("trajectory_comparison")
    before_pub = rospy.Publisher("/trajectory/before", RosPath, queue_size=1, latch=True)
    after_pub = rospy.Publisher("/trajectory/after", RosPath, queue_size=1, latch=True)
    before_pub.publish(before)
    after_pub.publish(after)
    rospy.loginfo("Published %d paired TUM poses in frame %s", len(before.poses), args.frame_id)
    rospy.spin()


if __name__ == "__main__":
    main()
