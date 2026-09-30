import { vi } from 'vitest';
import React from 'react';

// Minimal stub for @elyra/canvas — it uses window at import time and ships non-ESM bundles.

export const PipelineEditor = vi.fn().mockImplementation(() =>
  React.createElement('div', { 'data-testid': 'elyra-canvas' })
);

export const CanvasController = vi.fn(function CanvasController(this: Record<string, unknown>) {
  this.getFlowDef = vi.fn(() => ({ pipelines: [] }));
  this.getPipeline = vi.fn(() => ({ nodes: [] }));
  this.getNode = vi.fn();
  this.setNodeParameters = vi.fn();
  this.getNodeParameters = vi.fn(() => ({}));
  this.getNodeMessages = vi.fn(() => []);
  this.setNodeLabel = vi.fn();
  this.editActionHandler = vi.fn();
  this.openNotificationPanel = vi.fn();
  this.closeNotificationPanel = vi.fn();
  this.getPropertyValue = vi.fn();
  this.updatePropertyValue = vi.fn();
  this.setSaveButtonDisable = vi.fn();
  this.getPropertyValues = vi.fn(() => ({}));
  this.getLinks = vi.fn(() => []);
  this.getNodes = vi.fn(() => []);
  this.setLinkDecorations = vi.fn();
  this.getD3SelectionId = vi.fn(() => 'svg-id');
  this.zoomToFit = vi.fn();
  this.setNodeDecorations = vi.fn();
  this.setPipelineFlowPalette = vi.fn();
  this.setPipelineFlow = vi.fn();
  this.getPipelineFlow = vi.fn(() => ({ pipelines: [{ nodes: [] }] }));
  this.setSelections = vi.fn();
  this.canUndo = vi.fn(() => false);
  this.canRedo = vi.fn(() => false);
});

export const CommonCanvas = vi.fn().mockImplementation((props: any) => {
  return React.createElement(
    'div',
    { 'data-testid': 'elyra-common-canvas' },
    props?.topPanelContent,
    props?.toolbarConfig?.leftBar?.map((item: any, idx: number) =>
      item.jsx ? React.createElement('div', { key: idx }, item.jsx) : null
    )
  );
});

export const CommonProperties = vi.fn().mockImplementation(() =>
  React.createElement('div', { 'data-testid': 'common-properties' })
);

export const SidePanelModal = vi.fn().mockImplementation(() =>
  React.createElement('div', { 'data-testid': 'side-panel-modal' })
);

// Named re-exports expected by elyra consumers
export const nodeTypeDef = {};
export const CARBON_ICONS = {};
