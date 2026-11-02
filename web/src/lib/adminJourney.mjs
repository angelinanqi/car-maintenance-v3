export function documentCoverage(documentId, knowledge) {
  return {
    vehicle_ids: (knowledge?.document_vehicles || [])
      .filter((link) => link.document_id === documentId)
      .map((link) => link.vehicle_id),
    category_ids: (knowledge?.document_categories || [])
      .filter((link) => link.document_id === documentId)
      .map((link) => link.category_id),
  };
}

export function documentJourney(document, knowledge) {
  if (document.superseded_by_id)
    return {
      stage: "replaced",
      label: "Replaced",
      next: "View current version",
      color: "gray",
    };
  if (document.published)
    return {
      stage: "available",
      label: "Document published",
      next: "Check availability",
      color: "green",
    };
  if (document.status === "awaiting_index" && document.error)
    return {
      stage: "problem",
      label: "Indexing needs attention",
      next: "View problem",
      color: "red",
    };
  if (["processing", "awaiting_index"].includes(document.status))
    return {
      stage: "preparing",
      label: "Being prepared",
      next: "View progress",
      color: "blue",
    };
  if (document.status === "failed")
    return {
      stage: "problem",
      label: "Needs attention",
      next: "Resolve problem",
      color: "red",
    };
  const coverage = documentCoverage(document.id, knowledge);
  if (
    knowledge &&
    !coverage.vehicle_ids.length &&
    !coverage.category_ids.length
  )
    return {
      stage: "coverage",
      label: "Choose vehicles or topics",
      next: "Continue setup",
      color: "orange",
    };
  if (
    document.status !== "processed" ||
    !document.indexed_revision ||
    document.indexed_revision !== document.source_revision ||
    !document.chunk_count
  ) {
    return {
      stage: "prepare",
      label: "Ready to prepare",
      next: "Continue setup",
      color: "orange",
    };
  }
  if (!document.source_fidelity_verified)
    return {
      stage: "review",
      label: "Ready to check",
      next: "Continue document review",
      color: "orange",
    };
  return {
    stage: "publish",
    label: "Ready to make available",
    next: "Finish update",
    color: "orange",
  };
}

export function coverageNames(documentId, knowledge) {
  if (!knowledge) return [];
  const coverage = documentCoverage(documentId, knowledge);
  return [
    ...knowledge.vehicles
      .filter((vehicle) => coverage.vehicle_ids.includes(vehicle.id))
      .map((vehicle) =>
        [vehicle.name, vehicle.year, vehicle.engine, vehicle.variant]
          .filter(Boolean)
          .join(" · "),
      ),
    ...knowledge.categories
      .filter((category) => coverage.category_ids.includes(category.id))
      .map((category) => category.name),
  ];
}

export function scheduleStatus(status) {
  return (
    {
      draft: "Unfinished draft",
      published: "Available to drivers",
      superseded: "Previous version / taken offline",
    }[status] || status
  );
}

export function serviceInstruction(entry) {
  const rule = entry.rule;
  if (rule.type === "recurring") {
    const intervals = [];
    if (rule.distanceKm)
      intervals.push(`${rule.distanceKm.toLocaleString("en-GB")} km`);
    if (rule.months) intervals.push(`${rule.months} months`);
    return intervals.length
      ? `Every ${intervals.join(" or ")}${intervals.length === 2 ? ", whichever comes first" : ""}.`
      : "Add the interval stated in the manual.";
  }
  if (rule.type === "milestone") {
    const points = [];
    if (rule.distanceMilestones.length)
      points.push(`${rule.distanceMilestones.join(", ")} km`);
    if (rule.monthMilestones.length)
      points.push(`${rule.monthMilestones.join(", ")} months`);
    return points.length
      ? `At ${points.join(" or ")}.`
      : "Add the service points stated in the manual.";
  }
  return rule.conditions || rule.notes || "Describe when this task is needed.";
}

export function parseVideoLinks(text) {
  const ids = text
    .split(/\s+/)
    .filter(Boolean)
    .map((value) => {
      let url;
      try {
        url = new URL(value);
      } catch {
        throw new Error(
          "Paste a complete YouTube link for each video, one per line.",
        );
      }
      if (!["https:", "http:"].includes(url.protocol))
        throw new Error("Use a YouTube web link.");
      const host = url.hostname.toLowerCase();
      let id;
      if (host === "youtu.be") id = url.pathname.slice(1);
      else if (
        ["youtube.com", "www.youtube.com", "m.youtube.com"].includes(host)
      ) {
        id =
          url.pathname === "/watch"
            ? url.searchParams.get("v")
            : /^\/(?:shorts|embed)\/([^/]+)\/?$/.exec(url.pathname)?.[1];
      }
      if (!id || !/^[A-Za-z0-9_-]{11}$/.test(id))
        throw new Error(
          "One of the links is not a recognised YouTube video. Check it and try again.",
        );
      return id;
    });
  return [...new Set(ids)];
}

export function questionHref(question) {
  if (question.vehicle_id) {
    const query = new URLSearchParams({
      vehicle: question.vehicle_id,
      source: question.document_id,
    });
    if (question.schedule_id) query.set("schedule", question.schedule_id);
    if (question.source_page) query.set("page", String(question.source_page));
    return `/admin/schedules?${query}#questions`;
  }
  return `/admin/kb/${question.document_id}#questions`;
}

export function columnExamples(table, column) {
  return table.source.cells
    .filter(
      (cell) => cell.column === column && !cell.header && cell.text.trim(),
    )
    .slice(0, 3)
    .map((cell) => cell.text.trim());
}

export function suggestedNameColumns(table) {
  const headers = table.source.cells.filter(
    (cell) =>
      cell.header &&
      /\b(item|description|operation|component|task)\b/i.test(
        cell.text,
      ),
  );
  return [...new Set(headers.map((cell) => cell.column))];
}

export function scheduleEntryIssues(entry, documents) {
  const rule = entry.rule;
  const source = documents.find(
    (document) => document.id === rule.sourceDocumentId,
  );
  const issues = [];
  if (!entry.itemId) issues.push("Choose a service task.");
  if (!source) issues.push("Choose the reference document.");
  if (source && source.source_type !== "md" && !rule.sourcePage)
    issues.push("Enter the page in the PDF manual.");
  if (source?.source_type === "md" && !(rule.sourceRevision && rule.sourceTableId))
    issues.push("Choose a checked table or recorded section in the reference document.");
  if (rule.type === "recurring" && !(rule.distanceKm || rule.months))
    issues.push("Enter a distance or time interval.");
  if (rule.type === "milestone" &&
      !(rule.distanceMilestones.length || rule.monthMilestones.length))
    issues.push("Enter the service mileages or vehicle ages.");
  if (rule.type === "informational" && !(rule.conditions || rule.notes))
    issues.push("Describe when this task is needed or add guidance.");
  return issues;
}

export function scheduleProgress(entries, documents) {
  const incomplete = entries.filter(
    (entry) => scheduleEntryIssues(entry, documents).length > 0,
  ).length;
  const olderSources = entries.filter(
    (entry) =>
      documents.find((document) => document.id === entry.rule.sourceDocumentId)
        ?.superseded_by_id,
  ).length;
  return { total: entries.length, incomplete, olderSources };
}

export function documentSourceIds(document, documents) {
  const ids = new Set();
  while (document && !ids.has(document.id)) {
    ids.add(document.id);
    document = documents.find(
      (source) => source.id === document.replacement_for_id,
    );
  }
  return ids;
}

export function questionsForSchedule(questions, vehicleId, entries, documents) {
  const sources = new Set(
    entries.flatMap((entry) => [
      ...documentSourceIds(
        documents.find(
          (document) => document.id === entry.rule.sourceDocumentId,
        ),
        documents,
      ),
    ]),
  );
  return questions.filter(
    (question) =>
      question.status === "open" &&
      (question.vehicle_id === vehicleId
        ? !question.item_id ||
          entries.some((entry) => entry.itemId === question.item_id)
        : !question.vehicle_id && sources.has(question.document_id)),
  );
}
