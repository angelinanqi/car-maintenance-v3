"use client";

import { useEffect, useState } from 'react';
import { Box, Button, Field, Input, Stack, Text, Textarea, Progress, Image, Flex } from '@chakra-ui/react';
import { Checkbox } from '@/components/ui/checkbox';
import FileUploadField from './FileUploadField';
import { DOCUMENT_MAX_BYTES, IMAGE_MAX_BYTES } from '@/lib/config.mjs';
import { EMERGENCY_MEDIA_ACCEPT, validateEmergencyFile, meaningfulVideoDescription } from '@/lib/emergencyMedia.mjs';

const helper = 'Describe what this video demonstrates and the actions shown. This description helps the AI chatbot find and recommend the correct video when users need assistance.';

export default function EmergencyMediaEditor({ value = [], onChange, upload, legacyImage, removeLegacy }) {
  const [files, setFiles] = useState([]);
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const file = files[0];
  const video = file?.name.toLowerCase().endsWith('.mp4');
  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const update = (id, patch) => onChange(value.map(item => item.id === id ? { ...item, ...patch, reviewed: false } : item));
  async function submit() {
    const invalid = validateEmergencyFile(file);
    if (invalid || (video && !meaningfulVideoDescription(description))) {
      setError(invalid || 'Describe the actual actions shown, using at least six words and 30 characters.'); return;
    }
    setUploading(true); setError('');
    try {
      const { warning, ...item } = await upload(file, description);
      onChange([...value, item]); setFiles([]); setDescription(''); setError(warning || '');
    } catch (cause) { setError(cause.message); }
    finally { setUploading(false); }
  }
  return <Box borderWidth="1px" borderRadius="lg" p={4}><Stack gap={4}>
    <Text fontWeight="semibold">Step images and videos</Text>
    <Text fontSize="sm">Upload supporting media for offline use. Keep all emergency instructions in the written steps. Review descriptions before publishing.</Text>
    <Text fontSize="xs">PNG, JPEG, WebP or GIF up to {Math.floor(IMAGE_MAX_BYTES / 1048576)} MB. MP4 (H.264 video, optional AAC audio) up to {Math.floor(DOCUMENT_MAX_BYTES / 1048576)} MB.</Text>
    <FileUploadField accept={EMERGENCY_MEDIA_ACCEPT} maxFileSize={DOCUMENT_MAX_BYTES} maxFiles={1}
      acceptedFiles={files} disabled={!upload || uploading || value.length >= 10}
      onFileReject={() => setError('File selection rejected. Choose a supported, nonempty file within the upload limits.')}
      onFileChange={details => {
        const selected = details.acceptedFiles[0];
        const invalid = selected ? validateEmergencyFile(selected) : '';
        setFiles(invalid ? [] : details.acceptedFiles); setError(invalid); setDescription('');
      }} />
    {!upload && <Text fontSize="xs">Save this step before uploading its files.</Text>}
    {preview && (video ? <video src={preview} controls preload="metadata" style={{ width: '100%', maxHeight: 280 }} />
      : <Image src={preview} alt="Selected image preview" maxH="280px" objectFit="contain" />)}
    {file && video && <Field.Root required><Field.Label>Video description (Required)</Field.Label>
      <Textarea value={description} maxLength={4000} onChange={event => setDescription(event.target.value)} />
      <Field.HelperText>{helper}</Field.HelperText>
    </Field.Root>}
    {file && <Button type="button" alignSelf="start" disabled={uploading || (video && !meaningfulVideoDescription(description))} onClick={submit}>Upload {video ? 'video' : 'image'}</Button>}
    {uploading && <Progress.Root value={null} size="sm"><Progress.Label>Uploading file{!video ? ' and generating a draft description' : ''}…</Progress.Label><Progress.Track><Progress.Range /></Progress.Track></Progress.Root>}
    {error && <Text role="alert" color="red.600">{error}</Text>}
    {legacyImage && <Box><Text fontSize="sm">This legacy image link must be replaced with a file upload.</Text><Button type="button" size="xs" variant="outline" onClick={removeLegacy}>Remove legacy image link</Button></Box>}
    {value.map(item => <Box key={item.id} borderWidth="1px" borderRadius="md" p={4}><Stack gap={3}>
      <Flex justify="space-between"><Text fontWeight="semibold">{item.kind === 'video' ? 'Video' : 'Image'}</Text><Button type="button" size="xs" variant="outline" disabled={uploading} onClick={() => onChange(value.filter(row => row.id !== item.id))}>Remove media</Button></Flex>
      {!item.asset_id && <Text color="red.600" fontSize="sm">Replace this external link with a direct file upload.</Text>}
      {item.asset_id && (item.kind === 'video' ? <video src={item.url} controls preload="metadata" style={{ width: '100%', maxHeight: 280 }} /> : <Image src={item.url} alt={item.description || item.title} maxH="280px" objectFit="contain" />)}
      {item.size_bytes && <Text fontSize="xs">{(item.size_bytes / 1048576).toFixed(2)} MB</Text>}
      <Field.Root required><Field.Label>Title / caption</Field.Label><Input maxLength={200} value={item.title} onChange={event => update(item.id, { title: event.target.value })} /></Field.Root>
      <Field.Root required><Field.Label>{item.kind === 'video' ? 'Video description (Required)' : 'Image description'}</Field.Label>
        <Textarea rows={3} maxLength={4000} value={item.description} onChange={event => update(item.id, { description: event.target.value })} />
        <Field.HelperText>{item.kind === 'video' ? helper : 'Check the generated draft against the image, including essential actions and vehicle applicability.'}</Field.HelperText>
      </Field.Root>
      {[['vehicle_context', 'Vehicle applicability (optional)', 500], ['source_reference', 'Source / attribution (optional)', 2000]].map(([key, label, max]) => <Field.Root key={key}><Field.Label>{label}</Field.Label><Input maxLength={max} value={item[key] || ''} onChange={event => update(item.id, { [key]: event.target.value })} /></Field.Root>)}
      <Checkbox checked={item.reviewed} disabled={!item.asset_id || !item.description.trim() || !item.title.trim() || (item.kind === 'video' && !meaningfulVideoDescription(item.description))}
        onCheckedChange={event => onChange(value.map(row => row.id === item.id ? { ...row, reviewed: event.checked === true } : row))}>I reviewed this description for chatbot use</Checkbox>
    </Stack></Box>)}
  </Stack></Box>;
}
