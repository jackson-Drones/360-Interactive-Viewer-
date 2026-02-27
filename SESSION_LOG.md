# 360 Virtual Experience - Development Session Log

## Session: 2026-01-30

### Summary
Major feature additions, tech debt cleanup, and documentation updates for the 360 multi-panel viewer.

---

### Features Added

#### 1. Mid-Range Aspect Ratios
- Added three new aspect ratio options between standard and panoramic modes
- **70%** - 70vh height
- **60%** - 60vh height
- **50%** - 50vh height
- CSS classes: `aspect-mid-1`, `aspect-mid-2`, `aspect-mid-3`
- Added "Mid" row in control panel with buttons

#### 2. Pitch Lock Control
- New toggle to lock pitch and prevent any pitch changes
- Affects: mouse drag, touch drag, keyboard (W/S, arrows), panel buttons
- Control panel: "Pitch Lock" toggle
- Default: Off

#### 3. Pitch Sync Control
- Independent pitch synchronization separate from "Link Views"
- Allows pitch to sync across panels even when roll linking is off
- Control panel: "Pitch Sync" toggle
- Default: On

#### 4. Performance Stats Display (Press F)
- Real-time performance monitoring panel (bottom-left corner)
- Displays:
  - **Render FPS** - WebGL rendering frame rate (color-coded: green 55+, yellow 30+, red <30)
  - **Video FPS** - Estimated video playback frame rate
  - **Resolution** - Video dimensions (e.g., 5760x2880)
  - **Buffered** - Percentage of video buffered (color-coded)
  - **Dropped** - Dropped frames count and percentage (color-coded)
- Toggle via 'F' key or Stats button in control panel
- Hidden by default

---

### Tech Debt Cleanup

1. **Removed unused code:**
   - Deleted `originalDefaults` variable (was never used)
   - Removed call to non-existent `updatePlayButton()` method in `onVideoLoaded()`

2. **Added CSS consolidation:**
   - Added `.toggle-btn` class for consistent button styling

3. **Updated keyboard hints:**
   - Added 'F = stats' to the keyboard shortcuts hint

---

### Documentation Updates

#### README.md - Complete Rewrite
- Added all new keyboard shortcuts (1/2/3, C, F, Y)
- Added Touch controls section (mobile support)
- Documented all control panel options:
  - Panels, Aspect, Mid, Pano, Panorama, Link Views
  - Pitch Lock, Pitch Sync, Controls, Sync, Stats
- Added Performance Stats section explaining each metric
- Added Troubleshooting section:
  - Videos not loading
  - Poor performance
  - Videos out of sync
- Updated Technical Notes with implementation details
- Updated system requirements (16GB+ RAM recommended)

---

### Files Modified

| File | Changes |
|------|---------|
| `viewer/multi-view.html` | Added mid-range aspects, pitch lock/sync, performance stats, tech debt cleanup |
| `README.md` | Complete documentation rewrite with all new features |
| `SESSION_LOG.md` | Created this file |

---

### Current Control Panel Structure

```
Panels:     [FL3] [FL2] [FL1]
Aspect:     [Full] [32:9] [21:9] [16:9]
Mid:        [70%] [60%] [50%]
Pano:       [Wide] [Wider] [Ultra] [Cinema]
Panorama:   [On/Off]
Link Views: [On/Off]
Pitch Lock: [On/Off]
Pitch Sync: [On/Off]
Controls:   [On/Off]
Sync:       [On/Off]
Stats:      [On/Off]
Playback:   [Play] [Pause] [Reset] [Sync]
```

---

### Keyboard Shortcuts (Complete List)

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| WASD / Arrows | Pan and tilt |
| Q / E | Roll left/right |
| + / - | Zoom in/out |
| 1 / 2 / 3 | Toggle panels |
| G | Toggle controls panel |
| H | Hide/show all UI |
| P | Toggle panorama mode |
| L | Toggle linked views |
| C | Toggle panel controls |
| F | Toggle performance stats |
| Y | Resync all videos |
| R | Reset all views |

---

### Server Configuration
- **Port:** 8080
- **URL:** http://localhost:8080/viewer/multi-view.html
- **Launch:** `start.bat` or `python server.py 8080`

---

### Known State
- All features working
- Videos load from `/videos/` folder
- Server supports range requests for large files (10GB+)
- Performance stats available for debugging playback issues

---

### Next Session Suggestions
- Consider adding playback speed control
- Consider adding timeline/scrubber
- Consider saving/loading view presets
- Consider adding video quality selector if multiple resolutions available
