# income-verify-frontend

React (Vite + Tailwind) UI for IncomeVerify. The app calls `/api`, which the Vite dev server proxies to the
backend on :5920 (nginx does the same in the Docker image).

```
npm install
npm run dev     # http://localhost:5921
npm run build
```

Pages:
- `/` applications: verdict badges, filter and search, "Try a sample applicant" (synthetic, runs the real pipeline)
- `/new` new application: applicant, declared employer and income, drag-and-drop documents
- `/applications/:id` live progress (reading → extracting → checking → analysing), verdict card with reasons and
  authenticity score, metrics (verified income, FOIR, EMIs, bounces, balances), salary credits, checks, fraud
  signals, underwriter note, documents, cost and time; approve, re-analyse, export (Excel / JSON), add documents
- `/documents/:id` review: the original page beside its extracted fields. Doubted fields and balance-breaking
  transaction rows are amber with the check that doubts them; edits are saved and the application is re-analysed
- `/stats` documents read, straight-through %, average cost and time, verdict split, eval headline numbers

```
src/App.jsx                       routes, header, theme toggle
src/components/ui.jsx             UI kit (cards, buttons, badges, modal, drop zone)
src/components/feedback.jsx       toasts and confirm dialog
src/components/ApplicationParts.jsx  blocks of the application page
src/components/SamplePicker.jsx   sample applicants
src/lib/                          api, polling, ₹ formatting (Indian grouping), progress stages, field layouts, theme
src/pages/                        one file per route
```

Light and dark themes use CSS variables (`src/index.css`), so components use `bg-surface`, `text-ink` etc. and
switch without `dark:` classes on every element. Pages poll every 2.5 s while something is processing.
