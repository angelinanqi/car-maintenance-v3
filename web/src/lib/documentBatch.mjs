export async function uploadDocumentBatch(files, metadata, upload, onProgress) {
  const results = [];
  for (const file of files) {
    onProgress?.({ results: [...results], currentFile: file.name, total: files.length });
    try {
      const document = await upload(file, {
        ...metadata,
        name: files.length === 1 ? metadata.name : file.name,
      });
      results.push({ file, document });
    } catch (error) {
      results.push({ file, error: error.message });
    }
    onProgress?.({ results: [...results], currentFile: "", total: files.length });
  }
  const uploaded = results.filter((result) => result.document);
  const failed = results.filter((result) => result.error);
  if (failed.length) {
    const error = new Error(`${failed.length} file(s) could not be uploaded. ${failed[0].file.name}: ${failed[0].error}`);
    error.uploadedFiles = uploaded.map((result) => result.file);
    error.uploadedDocuments = uploaded.map((result) => result.document);
    throw error;
  }
  return uploaded.map((result) => result.document);
}

export async function applyCoverageBatch(documents, coverage, saveCoverage, onProgress) {
  const results = [];
  for (const document of documents) {
    try {
      await saveCoverage(document.id, coverage);
      results.push({ id: document.id, name: document.name, saved: true });
    } catch (error) {
      results.push({ id: document.id, name: document.name, saved: false, error: error.message });
    }
    onProgress?.([...results]);
  }
  return results;
}
