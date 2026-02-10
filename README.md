# Moho Render Farm

A comprehensive render farm and batch rendering application for **Moho Animation v14**.

Created by **Damian Turkieh**

---

## Features

- **Batch Rendering** - Queue multiple Moho projects and render them sequentially
- **Render Farm** - Master/Slave network system for distributed rendering across multiple PCs
- **Full GUI** - Dark-themed PyQt6 interface with drag-and-drop support
- **CLI Automation** - Complete command-line interface for scripting and pipelines
- **All Moho Render Options** - Format, codec, frame range, layer comps, antialiasing, multithreading, and more
- **Queue Management** - Save/load queues, reorder, retry, duplicate jobs
- **Windows Integration** - Right-click context menu on .moho files to render or add to queue
- **Drag & Drop** - Drag .moho files directly onto the application window

---

## Quick Start

### Installation

```bash
# 1. Clone or download the repository
git clone https://github.com/turkodamian/MohoRenderFarm.git
cd MohoRenderFarm

# 2. Run the installer
install.bat

# Or install manually:
python -m pip install -r requirements.txt
```

### Launch

```bash
# GUI mode (double-click or run)
start.bat

# Or directly
python main.py
```

---

## GUI Usage

The application has 4 main tabs:

### Render Queue Tab
- **Add Projects** - Select one or more .moho files
- **Add Folder** - Scan a folder recursively for Moho projects
- **Start Queue** (F5) - Begin rendering all pending jobs
- **Pause** (F6) - Pause after current job finishes
- **Stop** (F7) - Cancel current render and stop queue
- **Save/Load Queue** - Persist your queue to a JSON file
- **Drag & Drop** - Drag .moho files or folders directly onto the window
- **Right-click** on a job for: Retry, Duplicate, Move Up/Down, Remove, Cancel

### Render Settings Tab
Configure all Moho render options that apply to new jobs added to the queue:

| Setting | Description | Default |
|---------|-------------|---------|
| Format | Output format (MP4, PNG, JPEG, TGA, BMP, PSD, QT, GIF) | MP4 |
| Preset/Codec | Video codec preset (e.g., "MP4 (MPEG4-AAC)") | MP4 (MPEG4-AAC) |
| Output Folder | Destination folder (empty = same as project) | Project folder |
| Frame Range | Custom start/end frames | Entire animation |
| Multi-threaded | Use up to 5 render threads | Yes |
| Half Size | Render at 50% resolution | No |
| Half FPS | Render at 50% frame rate | No |
| Shape Effects | Apply shape effects | Yes |
| Layer Effects | Apply layer effects | Yes |
| Reduced Particles | Use fewer particles | No |
| Antialiased Edges | Smooth edges | Yes |
| Extra-smooth | Extra image quality | No |
| Premultiply Alpha | Premultiply alpha channel | Yes |
| NTSC Safe Colors | Clamp to NTSC-safe range | No |
| Layer Comp | Specific layer comp or AllComps/AllLayerComps | None |
| Add Layer Comp Suffix | Append comp name to filename | No |
| Create Folder for Layer Comp | Subfolder per comp | No |
| Add Format Suffix | Append format name to filename | No |
| Quality (QT only) | 0=Min, 1=Low, 2=Normal, 3=High, 4=Max, 5=Lossless | 3 (High) |
| Pixel Depth (QT only) | 24 or 32 (for alpha channel) | 24 |

### Render Farm Tab
Set up distributed rendering across multiple PCs:

1. **Master PC**: Click "Start as Master" - it will listen for slave connections
2. **Slave PCs**: Enter the master's IP and port, click "Start as Slave"
3. Add jobs to the queue on the master - they'll be distributed to idle slaves

### App Settings Tab
- **Moho.exe Path** - Configure the path to Moho.exe (default: `C:\Program Files\Moho 14\Moho.exe`)
- **Windows Integration** - Register/unregister right-click context menu for .moho files

---

## CLI Usage

### Render Files Directly

```bash
# Render a single file as MP4
python main.py --render "MyScene.moho" --format MP4 --options "MP4 (MPEG4-AAC)"

# Render with custom output folder
python main.py --render "MyScene.moho" -f MP4 -o "C:\output\" --verbose

# Render specific frame range
python main.py --render "MyScene.moho" -f PNG --start 1 --end 100

# Render multiple files
python main.py --render "Scene1.moho" "Scene2.moho" "Scene3.moho" -f MP4

# Render a single frame as PNG
python main.py --render "MyScene.moho" -f PNG --start 50 --end 50

# Render at half size for quick preview
python main.py --render "MyScene.moho" -f MP4 --halfsize yes

# Render all layer comps with separate folders
python main.py --render "MyScene.moho" --layercomp AllComps --createfolderforlayercomps yes

# Render with all options
python main.py --render "MyScene.moho" \
    -f MP4 --options "MP4 (H.265-AAC)" \
    -o "C:\renders\output.mp4" \
    --start 1 --end 200 \
    --multithread yes --halfsize no \
    --shapefx yes --layerfx yes \
    --aa yes --extrasmooth no \
    --premultiply yes --verbose
```

### Queue Management

```bash
# Process a saved queue file
python main.py --queue-file "my_queue.json"

# Open GUI with files pre-loaded in queue
python main.py --add-to-queue "Scene1.moho" "Scene2.moho"
```

### Render Farm (Slave Mode)

```bash
# Start as headless slave connecting to master
python main.py --slave --master-host 192.168.1.100 --port 5580
```

### Windows Context Menu

```bash
# Register right-click menu for .moho files
python main.py --register-context-menu

# Remove right-click menu
python main.py --unregister-context-menu
```

### All CLI Options

```
--render, -r FILE [FILE ...]    Render Moho project files
--format, -f FORMAT             Output format (JPEG, PNG, MP4, etc.)
--options PRESET                Codec preset (e.g. "MP4 (MPEG4-AAC)")
--output, -o PATH               Output file or folder
--start FRAME                   Start frame number
--end FRAME                     End frame number
--moho-path PATH                Path to Moho.exe
--verbose, -v                   Verbose output
--quiet, -q                     Quiet mode
--log FILE                      Log file path
--multithread yes|no            Multi-threaded rendering
--halfsize yes|no               Half size rendering
--halffps yes|no                Half frame rate
--shapefx yes|no                Shape effects
--layerfx yes|no                Layer effects
--fewparticles yes|no           Reduced particles
--aa yes|no                     Antialiased edges
--extrasmooth yes|no            Extra-smooth images
--premultiply yes|no            Premultiply alpha
--ntscsafe yes|no               NTSC safe colors
--layercomp NAME                Layer comp (or AllComps/AllLayerComps)
--addlayercompsuffix yes|no     Add layer comp suffix to filename
--createfolderforlayercomps yes|no  Create folder per layer comp
--addformatsuffix yes|no        Add format suffix to filename
--quality 0-5                   Quality (QT only)
--depth NUMBER                  Pixel depth (QT only)
--queue-file FILE               Process a saved queue file
--slave                         Start in headless slave mode
--master-host HOST              Master host for slave mode
--port PORT                     Network port (default: 5580)
--register-context-menu         Register Windows right-click menu
--unregister-context-menu       Remove Windows right-click menu
--gui                           Force GUI mode
```

---

## Supported Formats

### Image Formats (sequence output)
| Format | Extension | Notes |
|--------|-----------|-------|
| JPEG | .jpg | Default format |
| PNG | .png | With transparency |
| TGA | .tga | Targa format |
| BMP | .bmp | Bitmap |
| PSD | .psd | Photoshop layers |

### Video Formats (single file output)
| Format | Preset | Notes |
|--------|--------|-------|
| MP4 | MP4 (MPEG4-AAC) | Most compatible |
| MP4 | MP4 (H.265-AAC) | Better compression |
| M4V | M4V (MPEG4-AAC) | Apple compatible |
| MOV | MOV (ProRes alpha-ALAC) | Professional, with alpha |
| MOV | MOV (PNG alpha-PCM) | Lossless with alpha |
| MOV | MOV (MJPEG-AAC) | Motion JPEG |
| MOV | MOV (MPEG4-AAC) | QuickTime MPEG4 |
| AVI | AVI (PNG alpha-PCM) | Lossless with alpha |
| AVI | AVI (MJPEG-PCM) | Motion JPEG |
| AVI | AVI (Raw-PCM) | Uncompressed |
| ASF | ASF (WMV-WMA) | Windows Media |
| GIF | Animated GIF | Animated GIF |

---

## Network Render Farm

### Architecture

```
Master PC (port 5580)
  |
  +-- Slave PC 1 (requests jobs via HTTP)
  +-- Slave PC 2
  +-- Slave PC N
```

### Setup

1. **All PCs** must have Moho 14 installed and this application set up
2. **All PCs** must be able to access the project files (shared network drive recommended)
3. **Master**: Start the app and click "Start as Master" in the Render Farm tab
4. **Slaves**: Start the app (or use `--slave` CLI flag) and connect to the master IP

### API Endpoints (for custom integrations)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/register` | POST | Register a slave node |
| `/api/heartbeat` | POST | Slave heartbeat |
| `/api/get_job` | GET | Request next available job |
| `/api/job_complete` | POST | Report job completion |
| `/api/status` | GET | Get farm status |
| `/api/add_job` | POST | Add a job to the queue |
| `/api/queue` | GET | Get current queue |

---

## Project Structure

```
MohoRenderFarm/
├── main.py                 # Entry point (GUI + CLI)
├── start.bat               # Quick launcher
├── install.bat             # Installer
├── requirements.txt        # Python dependencies
├── src/
│   ├── config.py           # App configuration
│   ├── moho_renderer.py    # Moho CLI wrapper engine
│   ├── render_queue.py     # Queue management
│   ├── gui/
│   │   ├── main_window.py  # Main GUI window
│   │   └── styles.py       # Dark theme styles
│   ├── network/
│   │   ├── master.py       # Render farm master server
│   │   └── slave.py        # Render farm slave client
│   └── utils/
│       └── context_menu.py # Windows registry integration
└── MohoProjects/           # Test projects (gitignored)
```

---

## Requirements

- **Python** 3.10 or higher
- **Moho Pro 14** (or compatible version)
- **Windows** (tested on Windows 10/11)
- **Dependencies**: PyQt6, Flask, requests (installed via `install.bat` or `pip`)

---

## Configuration

Configuration is stored in `%APPDATA%\MohoRenderFarm\config.json` and includes:
- Moho executable path
- Default output directory
- Default format and preset
- Network port settings
- Recent projects and queues

Saved queues are stored in `%APPDATA%\MohoRenderFarm\queues\`.

---

## License

This project is proprietary software created by Damian Turkieh.
