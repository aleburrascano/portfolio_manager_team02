/**
 * The app's icon set.
 *
 * One file, one drawing style: 20x20 box, 1.5 stroke, round caps, no fills,
 * `currentColor` throughout. Icons are decorative here - every one of them
 * sits beside a text label - so they are hidden from assistive tech and the
 * label does the talking.
 */
import type { ReactElement } from 'react'

export type IconName =
  | 'deposit'
  | 'withdraw'
  | 'stock'
  | 'crypto'
  | 'bond'
  | 'empty'
  | 'search'

const PATHS: Record<IconName, ReactElement> = {
  deposit: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path strokeLinecap="round" d="M10 6.75v6.5M6.75 10h6.5" />
    </>
  ),
  withdraw: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path strokeLinecap="round" d="M6.75 10h6.5" />
    </>
  ),
  stock: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V11m4.5 5.5V6.5M12 16.5v-8m4.5 8V4" />
  ),
  crypto: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6.25v7.5M8 8.25h3.25a1.5 1.5 0 0 1 0 3H8h3.5a1.5 1.5 0 0 1 0 3H8" />
    </>
  ),
  bond: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 3.5h11v13l-2-1.25-2 1.25-2-1.25-2 1.25-3 1.75z" />
      <path strokeLinecap="round" d="M7.5 7h5M7.5 10h5" />
    </>
  ),
  empty: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 11.5 5 4.5h10l2 7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 11.5h3.5l1 2h5l1-2H17v3.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 15z" />
    </>
  ),
  search: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path strokeLinecap="round" d="m13.5 13.5 3 3" />
    </>
  ),
}

function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : 'icon'}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}

export default Icon
