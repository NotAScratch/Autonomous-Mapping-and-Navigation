# Autonomous Mapping and Navigation

An open-source research log: teaching a small wheeled robot to **map an unknown room and drive itself around it**, built from scratch by someone who started with zero robotics experience.

This repository is a lab notebook as much as it is code. Every step is recorded here, including the commands we ran, what we learned, what broke and how we fixed it. If you are new to robotics too, you should be able to follow along from the first entry.

> **Status:** Phase 0, setup and hardware inventory. No robot code written yet.

---

## Table of contents

1. [Goals](#goals)
2. [Philosophy: why from scratch?](#philosophy-why-from-scratch)
3. [The robot](#the-robot)
4. [Software environment](#software-environment)
5. [Roadmap](#roadmap)
6. [Research log](#research-log)
7. [Glossary](#glossary)
8. [License](#license)

---

## Goals

By the end of this project the robot should be able to:

1. **Map:** drive around an unknown indoor space and build a 2D map of it.
2. **Localize:** know where it is on that map at any moment.
3. **Navigate:** given a goal on the map, plan a path and drive there without hitting anything.
4. **Explore:** decide for itself where to go next until the whole space is mapped.

Steps 1 and 2 done together are called **SLAM** (Simultaneous Localization And Mapping). Step 3 is **autonomous navigation**.

## Philosophy: why from scratch?

ROS 2 already ships production-quality tools for all of this (`slam_toolbox`, `cartographer`, `Nav2`). Running them on a robot takes an afternoon, but you learn very little about *why* they work.

So the rule here is:

1. **Build it ourselves first.** Write a simple version of each piece (odometry, mapping, scan matching, path planning) to understand the idea.
2. **Then compare against the real tool.** Run the established package on the same data and measure how far off ours is, and why.
3. **Write everything down** in this README.

The vendor's demo code that came with the robot is used only as a reference, never as the solution.

## The robot

A **Yahboom ROSMASTER R2** with an **NVIDIA Jetson Orin NX Super 8 GB** as its onboard computer.

The R2 uses **Ackermann steering**, like a car: the rear wheels drive and the front wheels turn. This matters a lot later on. Unlike a differential-drive robot it **cannot turn on the spot**, so it has a minimum turning radius that odometry, path planning and path following all have to respect.

| Part | What it is | Role in the project |
|------|------------|---------------------|
| **Chassis** | Yahboom ROSMASTER R2, Ackermann steering (rear-wheel drive, front-wheel steering) | Defines how the robot can move (kinematics) |
| **Compute** | NVIDIA Jetson Orin NX 8 GB (Super dev kit), 6 CPU cores, ~150 GB NVMe SSD | Runs everything on board: drivers, SLAM, planning |
| **2D LiDAR** | 2D LiDAR on a CP210x USB-serial adapter (`/dev/rplidar`); the Jetson config says type `4ROS` | Main sensor for mapping: measures distance to walls 360° around the robot |
| **Depth camera** | Orbbec 3D camera (RGB + depth) | Later: 3D / visual SLAM and obstacle detection |
| **Motor driver board** | Yahboom ROS expansion board (CH340 USB-serial, `/dev/myserial`) | Drives the wheel motors, reports wheel encoders and IMU |
| **Extras** | USB webcam, LED matrix, Bluetooth | Not used for now |

*Exact LiDAR model still to be confirmed in Phase 1 by reading its device info.*

## Software environment

What is installed on the Jetson as of the first check (2026-10-05):

| Component | Version |
|-----------|---------|
| OS | Ubuntu 22.04.5 LTS |
| NVIDIA JetPack / L4T | R36.4.3 (JetPack 6.x) |
| Linux kernel | 5.15.148-tegra |
| CUDA | 12.6 |
| ROS 2 | Humble Hawksbill |
| Python | 3.10.12 |
| PyTorch | 2.5.0 (NVIDIA Jetson build) |
| OpenCV | 4.11 |
| Docker | 27.5 |

ROS 2 packages that are already installed and will be used **for comparison later**: `slam_toolbox`, `cartographer_ros`, `nav2_bringup`, `robot_localization`, `sllidar_ros2` (LiDAR driver), `astra_camera` (Orbbec driver).

### How we work

- Code is written on a laptop in this repository and runs on the Jetson.
- The laptop connects to the Jetson over Wi-Fi with SSH (`ssh jetson@<jetson-ip>`).
- All robots and computers in the same ROS 2 "domain" see each other's data. This robot uses `ROS_DOMAIN_ID=28`.

## Roadmap

Each phase ends with something that works on the real robot, plus a write-up in the log.

| Phase | Topic | What we build | Key concepts |
|:-----:|-------|---------------|--------------|
| 0 | Setup | Hardware inventory, SSH, repo | Jetson, Linux, git |
| 1 | Talking to hardware | Read raw LiDAR scans; send wheel commands over serial ourselves | Serial protocols, sensor data |
| 2 | ROS 2 basics | Our own nodes: LiDAR publisher, motor driver, teleop | Nodes, topics, messages, `tf` |
| 3 | Odometry | Estimate robot pose from wheel encoders (+ IMU) | Kinematics, dead reckoning, drift |
| 4 | Mapping with known poses | Occupancy grid map from scans + odometry | Occupancy grids, log-odds, ray casting |
| 5 | Scan matching | Align consecutive scans to correct odometry | ICP, rigid transforms |
| 6 | SLAM | Pose graph with loop closure | Graph optimization, loop closure |
| 7 | Benchmark | Compare our SLAM vs `slam_toolbox` / `cartographer` | Evaluation, error metrics |
| 8 | Localization | Find the robot on a saved map | Particle filter (AMCL) |
| 9 | Path planning | Global planner on the map | A*, costmaps, inflation |
| 10 | Path following | Drive the planned path, avoid obstacles | Pure pursuit, DWA |
| 11 | Exploration | Autonomous frontier-based exploration | Frontiers, decision making |
| 12 | Beyond | Depth camera / visual SLAM | RGB-D, visual features |

## Research log

Newest entries at the bottom. Every entry records **goal → what we did → what we learned → next step**.

### Entry 0: 2026-10-05, first contact with the robot

**Goal:** Check that the Jetson is reachable and find out what hardware and software we actually have before writing any code.

**What we did**

1. **Connected over SSH.** The two saved addresses for the Jetson no longer answered. The robot gets its IP address from the router by DHCP, so the address had changed. We found it again by scanning the local network for devices with port 22 (SSH) open.
   - *Lesson:* reserve a fixed IP for the robot in the router (DHCP reservation), or use its hostname, so this doesn't keep happening.
2. **Checked the system:** OS, JetPack, CUDA, ROS 2, Python packages (see [Software environment](#software-environment)).
   - Commands: `cat /etc/os-release`, `cat /etc/nv_tegra_release`, `nvpmodel -q`, `nvcc --version`, `ls /opt/ros`.
3. **Checked what's plugged in** with `lsusb` and `ls -l /dev/ttyUSB* /dev/video*`.
   - The RPLidar shows up as `/dev/ttyUSB0`, with a friendly alias `/dev/rplidar`.
   - The Orbbec depth camera shows up as two USB devices (color camera + depth sensor).
   - **The motor driver board is missing.** Its USB-serial chip (CH340, USB ID `1a86:7523`) was not listed, so `/dev/myserial` did not exist.
4. **Learned about udev rules.** Linux names USB serial devices `ttyUSB0`, `ttyUSB1`... in whatever order they are plugged in. To get stable names, `/etc/udev/rules.d/` contains rules that match a device by its USB vendor/product ID and create a symlink such as `/dev/rplidar` or `/dev/myserial`. This is why our code should always open `/dev/rplidar`, never `/dev/ttyUSB0`.
5. **Power mode** is `MAXN_SUPER` (maximum performance). Temperatures at idle are around 48–51 °C.

**Problems found**

- Motor driver board not detected on USB, so the robot cannot move yet. Check the USB cable and the battery/power switch.

**Next step:** Get the motor board connected, then start Phase 1: read raw LiDAR data with our own Python script.

## Glossary

Terms are added as they come up in the log.

| Term | Meaning |
|------|---------|
| **SLAM** | Simultaneous Localization And Mapping: building a map while figuring out where you are in it, at the same time |
| **LiDAR** | A spinning laser rangefinder that measures the distance to surrounding objects |
| **ROS 2** | Robot Operating System 2, a framework that lets separate programs (nodes) on a robot exchange data |
| **Jetson** | NVIDIA's small, low-power computer with a GPU, built for robots and edge AI |
| **JetPack / L4T** | NVIDIA's software bundle for the Jetson (Linux for Tegra + CUDA + drivers) |
| **SSH** | Secure Shell: logging into another computer's terminal over the network |
| **DHCP** | How a router hands out IP addresses automatically; the address may change between boots |
| **udev rule** | A Linux rule that gives a USB device a stable name such as `/dev/rplidar` |
| **Ackermann steering** | Car-like steering: front wheels turn, the robot drives along arcs and cannot rotate in place |
| **Odometry** | Estimating how far the robot has moved, e.g. by counting wheel rotations |
| **Occupancy grid** | A map made of small squares, each marked free, occupied or unknown |

## License

[GNU General Public License v3.0](LICENSE). You are free to use, study, share and modify this work, as long as derivatives stay open under the same license.
