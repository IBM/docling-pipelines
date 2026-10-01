import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TopNotificationBar from '@/components/Canvas/NotificationPanel/TopNotificationBar/TopNotificationBar';

describe('TopNotificationBar', () => {
  it('renders nothing when errorCount and warningCount are both 0', () => {
    const { container } = render(
      <TopNotificationBar errorCount={0} warningCount={0} onViewClick={vi.fn()} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders "Validation failed" title when there are errors', () => {
    render(
      <TopNotificationBar errorCount={2} warningCount={0} onViewClick={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.getByText('Validation failed')).toBeInTheDocument();
  });

  it('renders "Validation warning" title when only warnings exist', () => {
    render(
      <TopNotificationBar errorCount={0} warningCount={3} onViewClick={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.getByText('Validation warning')).toBeInTheDocument();
  });

  it('renders singular error message correctly', () => {
    render(
      <TopNotificationBar errorCount={1} warningCount={0} onViewClick={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.getByText(/1 validation error/)).toBeInTheDocument();
  });

  it('renders plural error + warning message correctly', () => {
    render(
      <TopNotificationBar errorCount={2} warningCount={3} onViewClick={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.getByText(/2 validation errors/)).toBeInTheDocument();
    expect(screen.getByText(/3 warnings/)).toBeInTheDocument();
  });

  it('calls onViewClick when View button is clicked', () => {
    const onViewClick = vi.fn();
    render(
      <TopNotificationBar errorCount={1} warningCount={0} onViewClick={onViewClick} onClose={vi.fn()} />
    );
    fireEvent.click(screen.getByText('View'));
    expect(onViewClick).toHaveBeenCalledOnce();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <TopNotificationBar errorCount={1} warningCount={0} onViewClick={vi.fn()} onClose={onClose} />
    );
    fireEvent.click(screen.getByLabelText('Close notification'));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
