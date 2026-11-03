"use client";

import { FileUpload } from "@chakra-ui/react";

// Shared selection, filenames, sizes and dropzone styling for document/media uploads.
export default function FileUploadField({ acceptedFiles = [], ...props }) {
  return <FileUpload.Root acceptedFiles={acceptedFiles} minFileSize={1} {...props}>
    <FileUpload.Dropzone w="100%" p={6} border="2px dashed" borderColor="gray.200"
      borderRadius="md" textAlign="center" cursor="pointer">
      <FileUpload.DropzoneContent><FileUpload.Label>
        Drag and drop files here, or click to browse
      </FileUpload.Label></FileUpload.DropzoneContent>
    </FileUpload.Dropzone>
    <FileUpload.HiddenInput />
    <FileUpload.ItemGroup>
      {acceptedFiles.map((file, index) => <FileUpload.Item key={`${file.name}-${index}`} file={file}>
        <FileUpload.ItemName /><FileUpload.ItemSizeText /><FileUpload.ItemDeleteTrigger />
      </FileUpload.Item>)}
    </FileUpload.ItemGroup>
  </FileUpload.Root>;
}
