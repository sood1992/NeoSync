# NeoSync Assets

## Required Icons

For building installers, you need to create these icon files:

### macOS: `icon.icns`
Create a 1024x1024 PNG icon, then convert:
```bash
# Create iconset folder
mkdir icon.iconset

# Create required sizes (from your 1024x1024 source)
sips -z 16 16     icon_1024.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon_1024.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon_1024.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon_1024.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon_1024.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon_1024.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon_1024.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon_1024.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon_1024.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon_1024.png --out icon.iconset/icon_512x512@2x.png

# Convert to icns
iconutil -c icns icon.iconset -o icon.icns
```

### Windows: `icon.ico`
Use an online converter or ImageMagick:
```bash
convert icon_1024.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

## Quick Start (No Icons)
The build scripts will work without icons - they'll just use system defaults.
