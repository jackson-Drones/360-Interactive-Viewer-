# 360 Virtual Experience Viewer - Technical Specification

## Overview

A web-based multi-panel 360-degree video viewer designed for synchronized panoramic playback of aerial flight line footage. The application renders three concurrent 360° video streams in a seamless 180-degree panoramic view.

---

## System Architecture

### Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **3D Rendering** | Three.js (WebGL) | 0.160.0 |
| **Video Streaming** | HLS.js | 1.5.7 |
| **Backend Server** | Python HTTP Server | 3.x |
| **Frontend** | Vanilla HTML/CSS/JavaScript (ES Modules) | - |

### Application Structure

```
360 virtual experience/
├── server.py              # Python HTTP server with range request support
├── start.bat              # Windows launch script
├── viewer/
│   ├── multi-view.html    # Main 3-panel panorama viewer
│   └── index.html         # Single video viewer
├── videos/
│   ├── flight_line_1.mp4  # Source MP4 (9.7 GB)
│   ├── flight_line_2.mp4  # Source MP4 (9.7 GB)
│   ├── flight_line_3.mp4  # Source MP4 (9.8 GB)
│   └── hls/               # HLS streaming segments
│       ├── flight_line_1/
│       ├── flight_line_2/
│       ├── flight_line_3/
│       ├── night_flight_line_1/
│       ├── night_flight_line_2/
│       └── night_flight_line_3/
└── tools/
    ├── convert_to_hls.py  # HLS conversion utility
    └── stabilizer/        # Video stabilization scripts
```

---

## Video Specifications

### Source Format

| Property | Specification |
|----------|---------------|
| **Format** | Equirectangular MP4 |
| **Aspect Ratio** | 2:1 (equirectangular) |
| **Typical Resolution** | 5760x2880 or 11520x5760 |
| **File Size** | ~9.7 GB per video |
| **Total Storage** | ~29.2 GB (3 day videos) + night videos |

### Streaming Format (HLS)

| Property | Specification |
|----------|---------------|
| **Format** | HTTP Live Streaming (HLS) |
| **Segment Duration** | 10 seconds |
| **Segment Format** | MPEG-TS (.ts) |
| **Playlist Format** | M3U8 |
| **Codec** | Stream copy (no re-encoding) |
| **HLS Flags** | independent_segments |

### Video Sets

| Set | Panel 1 (Left) | Panel 2 (Center) | Panel 3 (Right) |
|-----|----------------|------------------|-----------------|
| **Day** | Flight Line 3 | Flight Line 2 | Flight Line 1 |
| **Night** | Night Flight Line 1 | Night Flight Line 2 | Night Flight Line 3 |

---

## Rendering Engine

### Three.js Configuration

| Component | Specification |
|-----------|---------------|
| **Geometry** | SphereGeometry (500 unit radius) |
| **Sphere Segments** | 48 horizontal, 32 vertical |
| **Camera Type** | PerspectiveCamera |
| **Camera Position** | Origin (0, 0, 0) - inside sphere |
| **Rotation Order** | YXZ (Yaw, Pitch, Roll) |
| **Texture Type** | VideoTexture |
| **Color Space** | sRGB |
| **Antialiasing** | Disabled (performance) |
| **Power Preference** | high-performance |
| **Max Pixel Ratio** | 1.5x |

### Panorama Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Panel FOV** | 60° | Field of view per panel |
| **Total FOV** | 180° | Combined panoramic view (3 × 60°) |
| **Base Yaw** | -945° | Base viewing direction |
| **Panel Offsets** | -60°, 0°, +60° | Left, Center, Right |
| **Pitch Range** | -89° to +89° | Vertical look limits |
| **FOV Range** | 30° to 150° | Zoom limits |

---

## Server Specifications

### HTTP Server

| Feature | Implementation |
|---------|----------------|
| **Server Type** | ThreadedHTTPServer (Python) |
| **Threading** | Multi-threaded (daemon threads) |
| **Default Port** | 8080 |
| **Range Requests** | Full support (HTTP 206) |
| **CORS** | Enabled (Access-Control-Allow-Origin: *) |

### MIME Types

| Extension | MIME Type |
|-----------|-----------|
| `.m3u8` | application/vnd.apple.mpegurl |
| `.ts` | video/mp2t |
| `.mp4` | video/mp4 |

### Logging

| Feature | Specification |
|---------|---------------|
| **Log Location** | `logs/server_YYYYMMDD.log` |
| **Console Level** | INFO |
| **File Level** | DEBUG |
| **Format** | `YYYY-MM-DD HH:MM:SS | LEVEL | message` |

---

## HLS.js Configuration

### Buffer Settings (Per Stream)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **maxBufferLength** | 10s | Buffer ahead |
| **maxMaxBufferLength** | 20s | Maximum buffer |
| **maxBufferSize** | 30 MB | Memory limit per stream |
| **maxBufferHole** | 0.5s | Gap tolerance |
| **backBufferLength** | 10s | Retained playback buffer |
| **startLevel** | -1 | Auto quality selection |

### Error Handling

- Automatic recovery from MEDIA_ERROR
- Non-fatal bufferFullError suppressed (expected with 3 streams)
- Fatal error logging with details

---

## User Interface

### Display Modes

#### Aspect Ratios

| Mode | CSS Class | Description |
|------|-----------|-------------|
| Full | (default) | 100vw × 100vh |
| 32:9 | aspect-32-9 | Super ultrawide |
| 21:9 | aspect-21-9 | Ultrawide |
| 16:9 | aspect-16-9 | Widescreen |

#### Mid-Range Letterbox

| Mode | Height | Description |
|------|--------|-------------|
| 70% | 70vh | Slight letterbox |
| 60% | 60vh | Moderate letterbox |
| 50% | 50vh | Half-height |

#### Panoramic Letterbox

| Mode | Height | Description |
|------|--------|-------------|
| Wide | 40vh | Wide strip |
| Wider | 30vh | Wider strip |
| Ultra | 22vh | Ultra-wide strip |
| Cinema | 15vh | Cinematic letterbox |

### Control Panel Features

| Control | Function |
|---------|----------|
| Panel Toggles (FL1/FL2/FL3) | Show/hide individual panels |
| Aspect Buttons | Switch display aspect ratio |
| Panorama Toggle | Seamless borders on/off |
| Link Views | Sync pitch/roll across panels |
| Pitch Lock | Prevent pitch changes |
| Pitch Sync | Sync pitch independently |
| Controls Toggle | Show/hide per-panel controls |
| Sync Toggle | Video synchronization on/off |
| Stats Toggle | Performance monitoring on/off |

### Per-Panel Controls

| Control | Range | Linked |
|---------|-------|--------|
| FOV (Zoom) | 30° - 150° | No |
| Pitch | -89° - +89° | Optional |
| Yaw | Unlimited | No (maintains offset) |
| Roll | Unlimited | Optional |
| Day/Night Toggle | Day/Night | Per-panel |

---

## Input Controls

### Mouse

| Action | Function |
|--------|----------|
| Click + Drag | Pan/Tilt view |
| Scroll Wheel | Zoom (FOV) |

### Touch (Mobile)

| Action | Function |
|--------|----------|
| Single Finger Drag | Pan/Tilt view |
| Pinch | Zoom |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| W / Arrow Up | Look up |
| S / Arrow Down | Look down |
| A / Arrow Left | Look left |
| D / Arrow Right | Look right |
| Q | Roll left |
| E | Roll right |
| +/= | Zoom in |
| -/_ | Zoom out |
| 1 / 2 / 3 | Toggle panels |
| G | Toggle control panel |
| H | Hide/show all UI |
| P | Toggle panorama mode |
| L | Toggle linked views |
| C | Toggle panel controls |
| F | Toggle performance stats |
| Y | Resync all videos |
| R | Reset all views |
| N | Toggle all day/night |
| ` | Toggle debug log |

### Hold-Button Acceleration

| Hold Duration | Speed |
|---------------|-------|
| 0 - 300ms | 1° per tick |
| 300 - 600ms | 2° per tick |
| 600ms - 1s | 4° per tick |
| 1 - 1.5s | 8° per tick |
| 1.5 - 2s | 15° per tick |
| 2s+ | 25° per tick |

---

## Performance Monitoring

### Tracked Metrics

| Metric | Source | Color Coding |
|--------|--------|--------------|
| Render FPS | requestAnimationFrame | Green ≥55, Yellow ≥30, Red <30 |
| Video FPS | VideoPlaybackQuality | Estimated from decoded frames |
| Resolution | video.videoWidth/Height | - |
| Buffered | video.buffered | Green ≥90%, Yellow ≥50%, Red <50% |
| Dropped Frames | getVideoPlaybackQuality() | Green <1%, Yellow <5%, Red ≥5% |

### Sync Monitoring

- Drift check every 5 seconds (when debug enabled)
- Warning at >500ms drift
- Manual resync available (Y key)

---

## System Requirements

### Minimum Requirements

| Component | Specification |
|-----------|---------------|
| **Browser** | Chrome, Firefox, or Edge with WebGL support |
| **RAM** | 16 GB (recommended for 3× 4K streams) |
| **CPU** | Modern multi-core processor |
| **GPU** | WebGL 2.0 capable |
| **Python** | 3.x (for server) |

### Network Requirements

| Scenario | Bandwidth |
|----------|-----------|
| Local playback | N/A (localhost) |
| HLS streaming | ~50-100 Mbps for 3× 4K streams |

---

## Tools & Utilities

### HLS Conversion (convert_to_hls.py)

| Feature | Specification |
|---------|---------------|
| **Dependency** | FFmpeg |
| **Method** | Stream copy (no re-encoding) |
| **Segment Duration** | 10 seconds |
| **Output** | playlist.m3u8 + segment_XXX.ts |

### Video Stabilization (tools/stabilizer/)

| Script | Function |
|--------|----------|
| insta360_parser.py | Parse Insta360 metadata |
| stabilizer.py | Apply stabilization |
| batch_stabilize.py | Batch processing |

---

## File Formats

### Input

- **Video**: MP4 (H.264/H.265) equirectangular projection
- **Source**: Insta360 Studio exports

### Output

- **Streaming**: HLS (M3U8 playlist + TS segments)
- **Logs**: Plain text with timestamps

---

## Version Information

| Component | Version |
|-----------|---------|
| Three.js | 0.160.0 |
| HLS.js | 1.5.7 |
| Python | 3.x |

---

*Generated: 2026-02-04*
