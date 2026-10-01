import { cn } from '../../lib/utils'

function Skeleton({ className, ...props }) {
  return <div aria-hidden className={cn('animate-pulse rounded-md bg-secondary', className)} {...props} />
}

export { Skeleton }
