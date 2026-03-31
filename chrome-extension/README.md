# Xianyu Login State Extractor Chrome Extension

This Chrome extension extracts complete login state information from Xianyu (Goofish): cookies + browser environment + headers + storage snapshot.

## Installation

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** and select the `chrome-extension` directory
4. Confirm extension appears in toolbar

## Usage

1. Open [https://www.goofish.com](https://www.goofish.com) and make sure you are logged in
2. Open extension popup
3. Click **1) 采集完整快照**
4. Click **2) 复制账号文件 JSON（推荐）**
5. Save copied JSON into a file like `state/your_account.json`

## Output Types

- Account file JSON (recommended):
  - `display_name`, `created_at`, `cookies`, `env`, `headers`, `page`, `storage`
  - Compatible with auto-login generated account file structure
- Raw snapshot JSON:
  - Direct extracted snapshot from current tab

## Notes

- This extension uses `chrome.cookies` to include HttpOnly cookies.
- If your backend import flow only stores `cookies`, prefer writing this JSON directly into `state/*.json` to keep full snapshot fields.
