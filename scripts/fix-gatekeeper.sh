#!/bin/bash
# Fix macOS Gatekeeper blocking for Nobody Took Notes
# Run this after moving the app to /Applications

APP_PATH="/Applications/Nobody Took Notes.app"

if [ ! -d "$APP_PATH" ]; then
    echo "App not found at: $APP_PATH"
    echo "Please move 'Nobody Took Notes.app' to /Applications first."
    exit 1
fi

echo "Removing quarantine attribute from Nobody Took Notes..."
xattr -cr "$APP_PATH"

if [ $? -eq 0 ]; then
    echo "Done! You can now open Nobody Took Notes from /Applications."
else
    echo "Failed to remove quarantine. Try running with sudo:"
    echo "  sudo xattr -cr \"$APP_PATH\""
fi
