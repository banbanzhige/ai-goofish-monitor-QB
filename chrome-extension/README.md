# Xianyu Login State Extractor Chrome Extension

This Chrome extension helps extract complete login state information from Xianyu (Goofish) for use with the monitoring robot.

## Installation

1. Open Chrome and navigate to `chrome://extensions`
2. Enable "Developer mode" in the top right corner
3. Click "Load unpacked" and select the `chrome-extension` directory
4. The extension icon should now appear in your toolbar

## Usage

1. Navigate to [https://www.goofish.com](https://www.goofish.com)
2. Log in to your account
3. Click the extension icon in the toolbar
4. Click "Extract Login State"
5. The complete login state will be displayed - click "Copy to Clipboard" to copy it
6. Save the copied JSON as `xianyu_state.json` in your project directory

## Features

- Extracts all cookies including HttpOnly cookies that are not accessible via JavaScript
- Formats output as JSON compatible with the monitoring robot
- One-click copy to clipboard functionality
- Real-time status feedback

## How It Works

The extension uses the `chrome.cookies` API to access all cookies for the `.goofish.com` domain, including those with the HttpOnly flag set. This bypasses the normal JavaScript security restrictions that prevent access to these cookies.