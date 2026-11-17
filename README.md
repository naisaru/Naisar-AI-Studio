# Naisar AI Studio

Native Windows desktop AI image generation client, built with PySide6.

**Status: v0.1 MVP.** Includes a native window, checkpoint/LoRA local import, generation through a separately running ComfyUI server, gallery, and GitHub Actions Windows installer.

ComfyUI runtime and model files are not bundled. Civitai.red direct downloads are planned, not yet implemented. Import downloaded `.safetensors` files manually for now.

## Run

Windows, Python 3.11+:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Generate

Install/run ComfyUI locally at `http://127.0.0.1:8188`, ideally with low-VRAM options for RTX 3050 4 GB. Add an SD 1.5 checkpoint to `ComfyUI/models/checkpoints`, optional LoRA files to `ComfyUI/models/loras`. Set those paths in Naisar AI Studio Settings, test connection, and generate. Outputs are saved to `%LOCALAPPDATA%/NaisarAIStudio/gallery`.

## EXE installer

GitHub Actions → Windows Installer → Run workflow. Download the resulting `NaisarAIStudio-Windows-Setup` artifact. Uses PyInstaller + Inno Setup. This executable is unsigned and may trigger a Windows warning.

Generation requests go to the configured ComfyUI endpoint, defaulting to loopback. Do not expose ComfyUI publicly without securing it.
