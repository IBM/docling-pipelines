/**
 * CommonPropertiesPanelWrapper - Class-based wrapper for Elyra's customPanels
 * This wrapper is required by Elyra's CommonProperties component to render custom panels
 */

import React from 'react';
import { CommonPropertiesPanel } from './CommonPropertiesPanel';

/**
 * Wrapper class for CommonPropertiesPanel
 * Elyra's customPanels expects a class with specific methods
 */
class CommonPropertiesPanelWrapper {
  private parameters: any;
  private controller: any;
  private data: any;

  /**
   * Static ID method required by Elyra
   * This ID is referenced in paramDef JSON files
   */
  static id(): string {
    return 'common_properties_panel';
  }

  /**
   * Constructor receives parameters from Elyra
   */
  constructor(parameters: any, controller: any, data: any) {
    this.parameters = parameters;
    this.controller = controller;
    this.data = data;
  }

  /**
   * Render method called by Elyra to display the panel
   */
  renderPanel(): React.ReactElement {
    return (
      <CommonPropertiesPanel
        parameters={this.parameters}
        controller={this.controller}
        data={this.data}
      />
    );
  }
}

export default CommonPropertiesPanelWrapper;
