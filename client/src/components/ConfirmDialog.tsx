import type { ReactNode } from 'react'
import Modal from './Modal'
import './ConfirmDialog.css'

type ConfirmDialogProps = {
  title: string
  message?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** Styles the confirm button as destructive, for actions like logging out. */
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal title={title} role="alertdialog" onClose={onCancel} className="confirm-dialog">
      {message && <div className="confirm-dialog-message">{message}</div>}

      <div className="modal-actions">
        <button type="button" className="secondary-btn" onClick={onCancel}>
          {cancelLabel}
        </button>
        <button
          type="button"
          className={destructive ? 'danger-btn' : 'submit-btn'}
          onClick={onConfirm}
          data-autofocus
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

export default ConfirmDialog
