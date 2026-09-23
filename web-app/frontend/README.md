# Car App frontend

A Next.js App Router / React / Chakra UI local prototype.

## Run locally

From this directory, with dependencies installed:

    npm run dev

Other commands: npm run lint, npm run build, npm start.

The root URL redirects to /user/home. The sidebar links to Knowledge Base,
Learn Cards, and Emergency. The former manage-category route redirects to
Learn Cards; categories currently use a fixed shared list.

## Prototype behavior

- Documents can be added, renamed, tagged, and removed with confirmation.
  Selected File objects stay in React memory; they are never uploaded.
- Guides can be created, edited, saved as drafts, or marked published locally.
  Tiptap supports formatting, embedded local images, and YouTube links.
- Each emergency playbook has separate steps and checklist state.
  Only the first sample contains authored steps. Contacts and instructions
  are demonstration data.
- Dashboard totals reflect the current local data.
- PrototypeProvider holds this small shared state across client-side navigation.
  Reloading or closing the tab resets everything. There is no browser persistence.

No API, authentication, file storage, document processing, RAG connection, or
chatbot is implemented. YouTube embeds can load external media.

## Manual checks after installing dependencies

1. Add a file, edit its name/tags, cancel another edit, and remove it with confirmation.
2. Reopen the add dialog and confirm its fields and file selection are reset.
3. Create a guide, save a draft, reopen Edit, and confirm the content remains.
4. Publish/unpublish a guide and filter by its category.
5. Edit/add a step and check it in preview; switch playbooks and confirm isolation.
6. Add/edit a contact and verify empty name/phone validation.
7. Navigate Home and check counts, then reload and verify sample data resets.
8. Check sidebar/top navigation, tables, dialogs, and editor on narrow screens.
