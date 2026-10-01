import * as React from 'react'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        outline: 'border-border text-foreground',
        muted: 'border-transparent bg-secondary text-secondary-foreground',
      },
    },
    defaultVariants: { variant: 'outline' },
  },
)

/** Status badge: outline Badge + semantic filled dot, neutral text. */
function Badge({ className, variant, dotClassName, children, ...props }) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dotClassName && <span aria-hidden className={cn('size-1.5 rounded-full', dotClassName)} />}
      {children}
    </span>
  )
}

export { Badge, badgeVariants }
