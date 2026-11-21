# Teams attachment collection

In **Collect**, choose **Collect Teams attachments…**. Open a saved assignment linked to its Teams assignment and load the Course Hub class list first.

1. Choose one student, several students, or **Select all students**. Click **Collect selected students**.
2. The app opens Teams once and reads the selected students from the To return and Returned tabs. It checks the saved assignment IDs and selected student before reading each panel. It never types feedback, saves an assessment or Returns work.
3. Expand each attachment result. A supported Word document provides extracted text. Other supported pages provide a viewport screenshot. Restricted, inaccessible or unsupported views are labelled **blocked** or **unreadable**. A screenshot is not proof the entire attachment was read; pictures and embedded files in Word are not extracted.
4. Check the source links and the student's identity. Tick the review checkbox for each student you have checked, then choose **Add reviewed selections to Work** once for the batch. Each student can also be imported separately with **Add extracted text to Work**. All selected identities are validated before any work is changed, and the batch uses one assignment read and one session save. The app appends text with source labels, preserves existing Work, clears an obsolete no-submission finding and saves the session. Changing evidence requires reviewing the assessment again. Screenshot-only results are never turned into text automatically.
5. **Retry incomplete students** creates a read-only job for those students. A retry reuses successful attachments only when the submission ID and attachment names/order still agree; reused results are labelled. To refresh all evidence, collect the selected students again rather than using retry.
6. Reopen the dialog to recover saved results. **Saved attachment collections** lets you return to earlier runs, including results from before a subset retry. Import status is recorded separately for each extracted text attachment. Importing text does not hide screenshots, blocked sources or other previews; incomplete sources stay available for checking and retry. Older student-level delivery marks also leave those previews visible. Identical evidence is not appended twice.

**Stop after current student** preserves that student’s finished result and cancels the remaining students. Cancellation is recorded separately from collection failure; finished results remain available in the saved collection.

“No attachments listed” covers only the inspected Teams attachment list. A missing/unsupported attachment area, a blocked source or a failed student match must not be interpreted as no submission. OneNote and other sources remain separate collection steps.

## Collection efficiency

Each attachment is clicked once. The reader waits for either a popup or an identifiable inline viewer instead of waiting a fixed five seconds for a popup before trying inline content. OneNote collection reuses a loaded tree when it belongs to the same notebook; it still checks the resolved student and section after navigation. Teams and OneNote remain separate collection runs. Actual live-class timing has not been measured for these changes.

## Current limits

The new app integration has synthetic tests, not a live-school verification. The browser reader supports the inspected Teams attachment-tab layout; other layouts fail visibly. It extracts Word document text from supported SharePoint views and otherwise attempts a viewport screenshot. PDF extraction, image transcription, whole-document screenshots, and Code.org dashboard collection are not part of this integration. Downloads that do not expose a supported viewer may require manual collection.

Collection results, names, URLs and screenshots stay in the assignment's existing `.jobs` sidecars under Assessment. The SQLite journal holds job states and student IDs, not collected text or screenshots. Nothing is posted to students. The app must be restarted to load the new endpoint and page script; do that after any active jobs finish.

## Synthetic checks

Use the tools Python environment. Browser tests use a fresh browser profile; the HTTP test uses a temporary HOME and isolated port. They never access Teams.

- `tests/test_collection_batch_ui.py`: batch identity prevalidation, one session save and unchanged unreviewed students.
- `tests/test_collection_efficiency.py`: notebook navigation reuse and popup/inline readiness without fixed waits.
- `tests/test_collection_lifecycle.py`: cancellation and per-attachment import/recovery against a real temporary journal.
- `tests/test_session_ownership.js`: delayed session load/save/status responses, including switching assignments and reopening the same assignment.
- `tests/test_attachment_collection.py`: bounded Word extraction, identity validation, per-student jobs, result privacy, reuse and browser guard.
- `tests/test_attachment_collection_http.py`: actual page/script routes, same-origin protection, queue execution, result recovery and delivery markers with a stand-in reader.
- `tests/test_attachment_collection_ui.py`: one/batch selection, source previews, explicit reviewed import, preserved Work, no-submission clearing, incomplete-only retries, duplicate prevention, destination changes and class switching with mocked jobs.
