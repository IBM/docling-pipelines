import React, { useState } from 'react';
import {
  Button,
  ComposedModal,
  InlineNotification,
  ModalHeader,
  ModalBody,
  ModalFooter,
  TextInput,
  TextArea,
} from '@carbon/react';
import type { CreateFlowFormValues } from '@/types';
import { TagInput } from '../TagInput';
import styles from './CreateFlowTearsheet.module.scss';

export type { CreateFlowFormValues };

interface CreateFlowTearsheetProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (flow: CreateFlowFormValues) => void;
  readonly isLoading?: boolean;
  readonly error?: string | null;
  /** Names of flows that already exist in the project — used for duplicate detection. */
  readonly existingNames?: string[];
}

const EMPTY_FLOW: CreateFlowFormValues = { name: '', description: '', tags: [] };

export function CreateFlowTearsheet({
  open,
  onClose,
  onSubmit,
  isLoading = false,
  error = null,
  existingNames = [],
}: CreateFlowTearsheetProps): React.JSX.Element {
  const [flow, setFlow] = useState<CreateFlowFormValues>(EMPTY_FLOW);
  const [nameInvalid, setNameInvalid] = useState(false);
  const [nameDuplicate, setNameDuplicate] = useState(false);

  const handleClose = (): void => {
    if (isLoading) { return; }
    setFlow(EMPTY_FLOW);
    setNameInvalid(false);
    setNameDuplicate(false);
    onClose();
  };

  const isDuplicate = (name: string): boolean => {
    const trimmed = name.trim();
    if (!trimmed) { return false; }
    return existingNames.some((n) => n.trim().toLowerCase() === trimmed.toLowerCase());
  };

  const handleNameBlur = (): void => {
    if (flow.name.trim() && isDuplicate(flow.name)) {
      setNameDuplicate(true);
    }
  };

  const handleSubmit = (): void => {
    if (!flow.name.trim()) {
      setNameInvalid(true);
      return;
    }
    if (isDuplicate(flow.name)) {
      setNameDuplicate(true);
      return;
    }
    onSubmit(flow);
  };

  return (
    <ComposedModal
      open={open}
      onClose={handleClose}
      size="sm"
      preventCloseOnClickOutside
      containerClassName={styles.modal}
    >
      <ModalHeader title="Create flow" buttonOnClick={handleClose} className={styles.modalHeader} />

      <ModalBody className={styles.modalBody}>
        <div className={styles.formContent}>
          {error && (
            <InlineNotification
              kind="error"
              title="Failed to create flow"
              subtitle={error}
              hideCloseButton
              lowContrast
            />
          )}

          <TextInput
            id="flow-name"
            labelText="Name"
            placeholder="Enter name"
            value={flow.name}
            onChange={(e) => {
              setFlow((prev) => ({ ...prev, name: e.target.value }));
              setNameInvalid(false);
              setNameDuplicate(false);
            }}
            onBlur={handleNameBlur}
            invalid={nameInvalid || nameDuplicate}
            invalidText={
              nameDuplicate
                ? 'A flow with this name already exists. Please choose a unique name.'
                : 'Name is required'
            }
            disabled={isLoading}
          />

          <TextArea
            id="flow-description"
            labelText="Description (optional)"
            placeholder="Enter description"
            value={flow.description}
            onChange={(e) => { setFlow((prev) => ({ ...prev, description: e.target.value })); }}
            rows={5}
            disabled={isLoading}
          />

          <TagInput
            id="flow-tags"
            labelText="Add tags (optional)"
            tags={flow.tags}
            onChange={(tags) => { setFlow((prev) => ({ ...prev, tags })); }}
            helperText="Add tags to make flow easier to find. To add tags, separate them with commas and press Enter."
            disabled={isLoading}
          />
        </div>
      </ModalBody>

      <ModalFooter className={styles.footer}>
        <Button kind="ghost" onClick={handleClose} className={styles.footerCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button kind="primary" onClick={handleSubmit} className={styles.footerCreate} disabled={isLoading || nameDuplicate}>
          {isLoading ? 'Creating...' : 'Create'}
        </Button>
      </ModalFooter>
    </ComposedModal>
  );
}
