/**
 * Type definitions for operator parameter definitions
 */

export interface Parameter {
  id: string;
  type?: 'string' | 'integer' | 'float' | 'boolean' | 'array' | 'object';
  default?: unknown;
  required?: boolean;
  enum?: string[];
  min?: number;
  max?: number;
}

export interface ParameterInfo {
  parameter_ref: string;
  label?: string;
  description?: string;
  control?: 'textfield' | 'numberfield' | 'checkbox' | 'dropdown' | 'textarea';
}

export interface GroupInfo {
  id: string;
  type: 'customPanel' | 'controls';
  label?: string;
}

export interface UIHints {
  editor_size?: 'small' | 'medium' | 'large';
  id?: string;
  parameter_info?: ParameterInfo[];
  group_info: GroupInfo[];
}

export interface ParameterDef {
  parameters: Parameter[];
  uihints: UIHints;
  current_parameters?: Record<string, unknown>;
  current_ui_parameters?: Record<string, unknown>;
}
