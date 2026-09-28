/**
 * Ingest operator configuration panel body.
 * Reads and writes values directly via the Elyra property controller —
 * the same pattern used in docling-pipelines-ui custom panels.
 *
 * controller.getPropertyValue({ name: PARAM_ID })  → current value
 * controller.updatePropertyValue({ name: PARAM_ID }, value) → write on change
 * (Elyra collects all values and calls applyPropertyChanges on Save)
 *
 * TODO: Update parameters (source_path, max_file_size, max_files, recursive) to match
 * the final IngestOperator metadata once operator metadata is confirmed.
 */

import React from 'react';
import { NumberInput, TextInput, Toggle } from '@carbon/react';

interface IngestPanelBodyProps {
  controller: any;
}

export function IngestPanelBody({ controller }: IngestPanelBodyProps): React.JSX.Element {
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const maxFileSize = (controller?.getPropertyValue?.({ name: 'max_file_size' }) as number | undefined) ?? 100;
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const maxFiles = (controller?.getPropertyValue?.({ name: 'max_files' }) as number | undefined) ?? 1000;
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const sourcePath = (controller?.getPropertyValue?.({ name: 'source_path' }) as string | undefined) ?? '';
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const recursive = (controller?.getPropertyValue?.({ name: 'recursive' }) as boolean | undefined) ?? false;

  return (
    <div>
      <TextInput
        id="source_path"
        labelText="Source path"
        helperText="Path to the source directory or file"
        value={sourcePath}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call
          controller?.updatePropertyValue?.({ name: 'source_path' }, e.target.value);
        }}
      />

      <NumberInput
        id="max_file_size"
        label="Max file size (MB)"
        helperText="Maximum file size to ingest"
        value={maxFileSize}
        min={1}
        max={10000}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onChange={(_e: any, { value }: { value: number | string }) => {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call
          controller?.updatePropertyValue?.({ name: 'max_file_size' }, Number(value));
        }}
      />

      <NumberInput
        id="max_files"
        label="Max files"
        helperText="Maximum number of files to ingest"
        value={maxFiles}
        min={1}
        max={100000}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onChange={(_e: any, { value }: { value: number | string }) => {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call
          controller?.updatePropertyValue?.({ name: 'max_files' }, Number(value));
        }}
      />

      <Toggle
        id="recursive"
        labelText="Recursive scan"
        labelA="Off"
        labelB="On"
        toggled={recursive}
        onToggle={(checked: boolean) => {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call
          controller?.updatePropertyValue?.({ name: 'recursive' }, checked);
        }}
      />
    </div>
  );
}
