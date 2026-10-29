# Study notes

Hand-drawn-style study notes written alongside the research log. They explain the theory behind each phase so the log entries can focus on what we actually did.

| Chapter | File | What it covers |
|---------|------|----------------|
| 0 | [`chapter-0-ros2-basics.html`](chapter-0-ros2-basics.html) | ROS 2 basics: nodes, topics, messages, QoS, services, actions, parameters, namespaces and remapping, discovery and `ROS_DOMAIN_ID`, launch files, a first node, a CLI cheat sheet and a debugging checklist |
| 1 | [`chapter-1-slam-overview.html`](chapter-1-slam-overview.html) | How SLAM works: the chicken-and-egg problem, the predict/correct loop, drift and loop closure, the three SLAM families, sensors and map types, and running `slam_toolbox` on a ROS 2 robot |
| 2 | [`chapter-2-inside-slam.html`](chapter-2-inside-slam.html) | Inside the machine: the odometry motion model, sensor models and scan matching (ICP, correlative matching), the visual front-end, graph optimisation with Gauss-Newton, loop detection and robust kernels, and evaluating a run (ATE, RPE, `evo`) |

Read them in order: Chapter 0 is the ROS 2 groundwork the SLAM chapters build on.

## How to view them

GitHub shows `.html` files as source code, not as pages. To read a chapter:

- **Download and open it:** open the file on GitHub, click **Download raw file**, and open it in any browser.
- **Or clone the repo** and open the files from `notes/` in a browser.

Each file is self-contained. The handwriting fonts load from Google Fonts, so without internet the pages fall back to a system font. Every page has a light and a dark version and follows your system setting.

## Notes that differ from our robot

The notes are general, and a few examples assume a **differential-drive** robot. Our ROSMASTER R2 uses **Ackermann steering**, so keep these in mind:

- **Chapter 2, motion model:** the formula `Δθ = (d_R − d_L) / b` is for differential drive. On the R2 the heading change comes from the steering angle and the wheelbase (bicycle model: `Δθ = d · tan(δ) / L`).
- **Chapter 1 and Chapter 2 calibration tips:** "measure the wheel spacing" becomes "measure the wheelbase and calibrate the steering angle" for the R2.
- **Chapter 0, obstacle-avoider example:** it stops and sets `angular.z` to turn in place. The R2 can't rotate on the spot, so it needs some forward speed while steering. The example also takes the middle of the `ranges` array as "straight ahead". Our LiDAR's front is at about 303° and its angles run clockwise (see Entry 2), so use the calibrated index instead.
