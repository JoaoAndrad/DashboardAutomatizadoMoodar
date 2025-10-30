Launcher icon and embedding instructions

Place your ICO icon at `launcher/icon.ico` (the file you added). The CI and goreleaser configuration
will include this file in release archives automatically.

If you want the Windows executable to have the icon embedded (so the .exe displays the icon in Explorer),
follow these steps locally or add them to the Windows build step in CI:

1. If you only have PNG, convert it to ICO (requires ImageMagick or similar):

   On Linux/macOS (ImageMagick installed):
   convert launcher/icon.png -define icon:auto-resize=256,128,64,48,32,16 launcher/icon.ico

   On Windows (PowerShell with ImageMagick in PATH):
   magick convert launcher\icon.png -define icon:auto-resize=256,128,64,48,32,16 launcher\icon.ico

2. Generate a .syso resource with rsrc (https://github.com/akavel/rsrc):

   go install github.com/akavel/rsrc@latest
   rsrc -ico launcher/icon.ico -o launcher/icon.syso

3. Build on Windows (the presence of icon.syso will cause the icon to be embedded):

   GOOS=windows GOARCH=amd64 go build -ldflags "-s -w" -o moodar-launcher.exe ./launcher

Notes:

- The CI workflow currently copies `launcher/icon.ico` into the zip archives. To embed the icon into the Windows binary in CI,
  add the rsrc step (and, if needed, ImageMagick) to the Windows build job before `go build`.
- If you want, I can add the ImageMagick/rsrc steps to the GitHub Actions workflow for the Windows build — say the word and I'll update the workflow.
