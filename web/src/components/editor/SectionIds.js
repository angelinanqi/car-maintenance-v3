import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";

// IDs survive heading edits and reordering. Pasting a duplicate assigns a new ID.
export const SectionIds = Extension.create({
  name: "sectionIds",
  addGlobalAttributes() {
    return [
      {
        types: ["heading"],
        attributes: {
          sectionId: {
            default: null,
            parseHTML: (element) => element.getAttribute("data-section-id"),
            renderHTML: (attributes) =>
              attributes.sectionId
                ? { "data-section-id": attributes.sectionId }
                : {},
          },
        },
      },
    ];
  },
  onCreate() {
    this.editor.view.dispatch(
      this.editor.state.tr.setMeta("assignSectionIds", true),
    );
  },
  addProseMirrorPlugins() {
    return [
      new Plugin({
        appendTransaction(transactions, _oldState, state) {
          if (
            !transactions.some(
              (transaction) =>
                transaction.docChanged ||
                transaction.getMeta("assignSectionIds"),
            )
          )
            return null;
          const seen = new Set();
          const transaction = state.tr;
          state.doc.descendants((node, position) => {
            if (node.type.name !== "heading" || node.attrs.level !== 2) return;
            let identity = node.attrs.sectionId;
            if (!identity || seen.has(identity)) {
              identity = crypto.randomUUID();
              transaction.setNodeMarkup(position, undefined, {
                ...node.attrs,
                sectionId: identity,
              });
            }
            seen.add(identity);
          });
          return transaction.docChanged ? transaction : null;
        },
      }),
    ];
  },
});
