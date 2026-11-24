Uber Receipt Helper v1.2
Author: Lucio

────────────────────────────────
What this is
────────────────────────────────
A small Windows app that lists your Uber trip history, lets you tick the
trips you need, and downloads their PDF receipts in bulk.

No installation. Just run the exe — no Python or runtime required.

────────────────────────────────
How to use
────────────────────────────────
1. Double-click UberInvoiceTool.exe
   (If Windows shows "Windows protected your PC", click "More info" → "Run anyway".)

2. Pick dates: clicking a date box opens a small calendar.

3. Click "Load trips".
   On first run a separate browser window opens (your normal browser is untouched).
   Sign in to Uber there, come back, and click "Load trips" again.
   The session is stored locally, so you only sign in once.

   ! Keep that browser window open while loading and downloading.
   Closing it breaks the connection and interrupts the download
   (clicking "Load trips" again reopens the window).

4. Click the "Pick" column to tick trips (single click).
   Trips marked Incomplete / Cancelled / 0 amount have no file and cannot be ticked.

5. Choose a folder and click "Download selected".
   Files are named like UberReceipt_2026-11-22_SAR43.27.pdf
   Over 30 files you'll get a confirmation with an estimated time.
   When it finishes, the dialog has an "Open folder" button.

────────────────────────────────
Notes
────────────────────────────────
• Soft limit of 300 trips per load; it asks whether to keep loading older ones.
• Works with Edge / Chrome / Brave / Vivaldi / Chromium. Pick one in the top-right
  "Browser" dropdown, or leave it on Auto.
• Everything stays on your machine: the app talks to Uber directly,
  no third-party server involved.
• Amounts and dates come from the trip list, not read back from the PDF.

────────────────────────────────
Currency and receipt types
────────────────────────────────
• The summary bar groups totals by currency (AED is never added to SAR),
  each with a small flag.
• Saudi Arabia: Uber provides a real invoice file (with ZATCA VAT details).
• Other countries (e.g. UAE): there is no invoice file — the app opens the
  receipt popup and uses its "Download PDF" link; only if that is missing does
  it fall back to printing the receipt page. File naming is the same.

────────────────────────────────
Requirements
────────────────────────────────
• Windows 10 / 11 (64-bit)
• One Chromium browser (the built-in Edge is enough)
• Your own Uber account, signed in once

────────────────────────────────
Removing your data
────────────────────────────────
Delete this folder (sign-in state and settings):
  %LOCALAPPDATA%\UberInvoiceTool

Receipts live in the folder you chose, by default:
  Documents\UberReceipts
