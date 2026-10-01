import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { RequiredParamTooltip } from '@/components/common/RequiredParamTooltip/RequiredParamTooltip';
import type { OperatorFeature } from '@/types';

const requiredAttr: OperatorFeature = {
  type: 'string',
  description: 'Required field',
  required: true,
  default: null,
  available_for_filter: null,
  available_for_vector_db: null,
};

const optionalAttr: OperatorFeature = {
  type: 'string',
  description: 'Optional field',
  required: false,
  default: null,
  available_for_filter: null,
  available_for_vector_db: null,
};

describe('RequiredParamTooltip', () => {
  it('isRequired: true → appends "(required)" to label text', () => {
    render(
      React.createElement(
        RequiredParamTooltip,
        {
          paramId: 'provider',
          nodeAttributes: { provider: requiredAttr },
          definition: 'Choose provider',
        },
        'Provider'
      )
    );
    expect(screen.getByText(/\(required\)/)).toBeDefined();
  });

  it('isRequired: false → no "(required)" indicator', () => {
    render(
      React.createElement(
        RequiredParamTooltip,
        {
          paramId: 'name',
          nodeAttributes: { name: optionalAttr },
          definition: 'Enter name',
        },
        'Name'
      )
    );
    expect(screen.queryByText('(required)')).toBeNull();
  });
});
