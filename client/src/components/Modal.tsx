import { useEffect, useId, useRef, type MouseEvent, type ReactNode } from 'react'
import './Modal.css'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

type ModalProps = {
  title: string
  /** `alertdialog` for a decision the user has to answer before continuing. */
  role?: 'dialog' | 'alertdialog'
  /**
   * Change this to move focus back into the dialog - a multi-step dialog
   * passes its current step, so replacing the contents doesn't leave focus
   * on a button that no longer exists.
   */
  focusKey?: string | number
  onClose: () => void
  children: ReactNode
  className?: string
}

/**
 * The one modal in the app. Every dialog goes through it so they all agree
 * on the things a dialog owes a keyboard user: Escape closes, Tab stays
 * inside, focus starts somewhere useful, and focus goes back where it came
 * from on the way out.
 *
 * Mark the element that should receive focus on open with `data-autofocus`;
 * without one, focus lands on the first focusable child.
 */
function Modal({ title, role = 'dialog', focusKey, onClose, children, className }: ModalProps) {
  const titleId = useId()
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    return () => previouslyFocused?.focus?.()
  }, [])

  useEffect(() => {
    const card = cardRef.current
    if (!card) return

    const preferred = card.querySelector<HTMLElement>('[data-autofocus]')
    const first = card.querySelector<HTMLElement>(FOCUSABLE)
    ;(preferred ?? first ?? card).focus()
  }, [focusKey])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const card = cardRef.current
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab' || !card) return

      const focusable = Array.from(card.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (focusable.length === 0) {
        event.preventDefault()
        return
      }

      const firstItem = focusable[0]
      const lastItem = focusable[focusable.length - 1]
      const active = document.activeElement

      if (event.shiftKey && (active === firstItem || active === card)) {
        event.preventDefault()
        lastItem.focus()
      } else if (!event.shiftKey && active === lastItem) {
        event.preventDefault()
        firstItem.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const swallowClickInsideTheCard = (event: MouseEvent) => event.stopPropagation()

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={cardRef}
        className={className ? `modal-card ${className}` : 'modal-card'}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={swallowClickInsideTheCard}
      >
        <h2 id={titleId} className="modal-title">
          {title}
        </h2>
        {children}
      </div>
    </div>
  )
}

export default Modal
